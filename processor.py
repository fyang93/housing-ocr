import asyncio
from pathlib import Path
from models import Database
from ocr import OCRClient
from llm import LLMExtractor
import tomli_w


class DocumentProcessor:
    def __init__(self, config: dict, db: Database, update_models_callback=None):
        self.config = config
        self.db = db
        self.ocr_client = OCRClient(config["ocr"]["endpoint"], config["ocr"]["model"])

        def _update_models_callback(models):
            config["llm"]["models"] = models
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

    async def process_document(self, doc_id: int):
        doc = self.db.get_document(doc_id)
        if not doc:
            return

        upload_dir = Path(self.config["app"]["upload_dir"])
        image_path = upload_dir / doc["filename"]

        try:
            if doc["ocr_status"] == "pending":
                print(f"[ID:{doc_id}] {doc['filename']} 开始OCR处理...")
                self.db.update_ocr_status(doc_id, "processing")

                ocr_text = await asyncio.to_thread(
                    self.ocr_client.extract_text, str(image_path), doc_id
                )

                if not ocr_text or len(ocr_text.strip()) == 0:
                    print(f"[ID:{doc_id}] OCR返回空文本，保持pending状态待重试")
                    self.db.update_ocr_status(doc_id, "pending")
                else:
                    self.db.update_ocr_status(doc_id, "done", ocr_text)
                    print(f"[ID:{doc_id}] OCR完成 ({len(ocr_text)} 字符)")

            if doc["ocr_status"] == "done" and (
                doc["llm_status"] == "pending" or doc["llm_status"] == "processing"
            ):
                doc = self.db.get_document(doc_id)
                ocr_text = doc.get("ocr_text", "") or ""

                if not ocr_text or len(ocr_text.strip()) == 0:
                    print(f"[ID:{doc_id}] OCR文本为空，OCR状态重置为pending待重试")
                    self.db.update_ocr_status(doc_id, "pending")
                    self.db.update_llm_status(doc_id, "pending", None)
                    return

                print(f"[ID:{doc_id}] {doc['filename']} 开始LLM提取...")
                self.db.update_llm_status(doc_id, "processing")

                properties = await asyncio.to_thread(
                    self.llm_extractor.extract_properties, ocr_text, doc_id
                )
                extracted_model = properties.pop("_extracted_by_model", None)
                self.db.update_llm_status(doc_id, "done", properties, extracted_model)
                print(f"[ID:{doc_id}] LLM提取完成 (模型: {extracted_model})")

        except Exception as e:
            print(f"[ID:{doc_id}] {doc['filename']} 处理失败: {str(e)}")
            import traceback

            traceback.print_exc()
            self.db.increment_retry(doc_id)

            current_doc = self.db.get_document(doc_id)
            if current_doc:
                if current_doc["ocr_status"] == "processing":
                    self.db.update_ocr_status(doc_id, "pending")
                elif current_doc["llm_status"] == "processing":
                    self.db.update_llm_status(doc_id, "pending")

    async def process_queue(self):
        print("后台处理器已启动...")
        while True:
            try:
                pending_docs = self.db.get_pending_documents()
                if pending_docs:
                    print(f"发现 {len(pending_docs)} 个待处理文档")
                for doc in pending_docs:
                    try:
                        await self.process_document(doc["id"])
                    except Exception as e:
                        print(f"处理文档 {doc['id']} 时出错: {str(e)}")
                        import traceback

                        traceback.print_exc()
            except Exception as e:
                print(f"队列处理出错: {str(e)}")
                import traceback

                traceback.print_exc()

            await asyncio.sleep(1)

    def close(self):
        self.ocr_client.close()
        self.llm_extractor.close()
