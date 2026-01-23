import asyncio
from pathlib import Path
from src.models import Database
from src.ocr import OCRClient
from src.llm import LLMExtractor
import tomli_w


class DocumentProcessor:
    def __init__(self, config: dict, db: Database, update_models_callback=None):
        self.config = config
        self.db = db
        self.ocr_client = OCRClient(config["ocr"]["endpoint"], config["ocr"]["model"])
        self._shutdown_event = asyncio.Event()

        def _update_models_callback(models):
            config["llm"]["models"] = list(models)
            config_path = Path(__file__).parent / "config.toml"
            with open(config_path, "wb") as f:
                tomli_w.dump(config, f)

        callback = update_models_callback or _update_models_callback

        self.llm_extractor = LLMExtractor(
            config["llm"]["api_key"],
            config["llm"]["base_url"],
            config["llm"]["models"],
            update_config_callback=callback,
        )

    def _get_display_filename(self, doc: dict) -> str:
        return doc.get("original_filename") or doc.get("filename", "unknown")

    async def process_document(self, doc_id: int):
        doc = self.db.get_document(doc_id)
        if not doc:
            return

        upload_dir = Path(self.config["app"]["upload_dir"])
        image_path = upload_dir / doc["filename"]

        try:
            print(
                f"[ID:{doc_id}] 当前状态 - OCR: {doc['ocr_status']}, LLM: {doc['llm_status']}"
            )
            # Reset stuck processing states
            if doc["ocr_status"] == "processing":
                print(f"[ID:{doc_id}] 检测到OCR处理中状态，重置为pending重试")
                self.db.update_ocr_status(doc_id, "pending")
                doc["ocr_status"] = "pending"
            if doc["llm_status"] == "processing":
                print(f"[ID:{doc_id}] 检测到LLM处理中状态，重置为pending重试")
                self.db.update_llm_status(doc_id, "pending")
                doc["llm_status"] = "pending"

            if doc["ocr_status"] in ["pending", "processing"]:
                if doc["ocr_status"] == "pending":
                    print(
                        f"[ID:{doc_id}] {self._get_display_filename(doc)} 开始OCR处理..."
                    )
                    print(f"[ID:{doc_id}] 文件路径: {image_path}")
                    self.db.update_ocr_status(doc_id, "processing")
                else:
                    print(
                        f"[ID:{doc_id}] {self._get_display_filename(doc)} 继续OCR处理..."
                    )

                try:
                    print(f"[ID:{doc_id}] 调用OCR API...")
                    ocr_text = await self.ocr_client.extract_text(
                        str(image_path), doc_id
                    )
                    print(f"[ID:{doc_id}] OCR API调用完成")

                    if not ocr_text or len(ocr_text.strip()) == 0:
                        print(f"[ID:{doc_id}] OCR返回空文本，保持pending状态待重试")
                        self.db.update_ocr_status(doc_id, "pending")
                    else:
                        self.db.update_ocr_status(doc_id, "done", ocr_text)
                        print(f"[ID:{doc_id}] OCR完成 ({len(ocr_text)} 字符)")
                except Exception as ocr_error:
                    print(f"[ID:{doc_id}] OCR调用失败: {str(ocr_error)}")
                    self.db.update_ocr_status(doc_id, "pending")
                    raise ocr_error

            if doc["ocr_status"] == "done" and doc["llm_status"] in [
                "pending",
                "failed",
            ]:
                current_doc = self.db.get_document(doc_id)
                if not current_doc:
                    print(f"[ID:{doc_id}] 文档不存在，跳过")
                    return

                ocr_text = current_doc.get("ocr_text", "") or ""

                if not ocr_text or len(ocr_text.strip()) == 0:
                    print(f"[ID:{doc_id}] OCR文本为空，OCR状态重置为pending待重试")
                    self.db.update_ocr_status(doc_id, "pending")
                    self.db.update_llm_status(doc_id, "pending", None)
                    return

                print(
                    f"[ID:{doc_id}] {self._get_display_filename(current_doc)} 开始LLM提取..."
                )
                self.db.update_llm_status(doc_id, "processing")
                print(f"[ID:{doc_id}] llm_status已更新为processing，准备调用LLM...")

                properties = await self.llm_extractor.extract_properties(
                    ocr_text, doc_id
                )
                print(f"[ID:{doc_id}] LLM调用完成，开始更新数据库...")
                extracted_model = properties.pop("_extracted_by_model", None)
                self.db.update_llm_status(doc_id, "done", properties, extracted_model)
                print(f"[ID:{doc_id}] LLM提取完成 (模型: {extracted_model})")

        except Exception as e:
            import traceback

            print(f"[ID:{doc_id}] ==========================================")
            print(f"[ID:{doc_id}] 处理失败: {str(e)}")
            print(f"[ID:{doc_id}] 错误类型: {type(e).__name__}")
            traceback.print_exc()
            print(f"[ID:{doc_id}] ==========================================")
            self.db.increment_retry(doc_id)

            current_doc = self.db.get_document(doc_id)
            if current_doc:
                if current_doc["ocr_status"] == "processing":
                    self.db.update_ocr_status(doc_id, "pending")
                elif current_doc["llm_status"] == "processing":
                    self.db.update_llm_status(doc_id, "pending")

    async def process_queue(self):
        print("后台处理器已启动...")
        print("开始监听待处理文档...")
        max_concurrent = 3
        semaphore = asyncio.Semaphore(max_concurrent)
        active_tasks = set()

        async def process_with_semaphore(doc_id, filename):
            async with semaphore:
                print(f"[ID:{doc_id}] 开始处理: {filename}")
                try:
                    await self.process_document(doc_id)
                    print(f"[ID:{doc_id}] 处理完成")
                except Exception as e:
                    print(f"[ID:{doc_id}] 处理失败: {str(e)}")
                    import traceback

                    traceback.print_exc()

                    self.db.increment_retry(doc_id)

                    current_doc = self.db.get_document(doc_id)
                    if current_doc:
                        if current_doc["ocr_status"] == "processing":
                            self.db.update_ocr_status(doc_id, "pending")
                        elif current_doc["llm_status"] == "processing":
                            self.db.update_llm_status(doc_id, "pending")

        while not self._shutdown_event.is_set():
            try:
                pending_docs = self.db.get_pending_documents()
                if pending_docs:
                    print(f"[PROCESSOR] 发现 {len(pending_docs)} 个待处理文档")

                for doc in pending_docs:
                    doc_id = doc["id"]
                    filename = self._get_display_filename(doc)
                    task = asyncio.create_task(process_with_semaphore(doc_id, filename))
                    active_tasks.add(task)
                    task.add_done_callback(active_tasks.discard)

                if active_tasks:
                    done, _ = await asyncio.wait(
                        active_tasks, timeout=1.0 if not pending_docs else None
                    )
                elif not pending_docs:
                    await asyncio.sleep(1)

            except Exception as e:
                print(f"队列处理出错: {str(e)}")
                import traceback

                traceback.print_exc()
                await asyncio.sleep(1)

        print("[PROCESSOR] 接收到关闭信号，等待任务完成...")
        if active_tasks:
            await asyncio.wait(active_tasks)
        print("[PROCESSOR] 所有任务已完成，处理器已关闭")

    async def close(self):
        await self.ocr_client.close()
        await self.llm_extractor.close()
