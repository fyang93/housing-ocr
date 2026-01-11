import threading
import queue
import time
from datetime import datetime
from typing import Optional, Callable
from .database import get_session, Document
from .ocr import process_document, extract_property_info


class Task:
    """任务基类"""

    def __init__(self, doc_id: int, priority: int = 5, manual: bool = False):
        self.doc_id = doc_id
        self.priority = priority
        self.manual = manual  # 是否手动触发
        self.created_at = datetime.utcnow()

    def __lt__(self, other):
        # 优先级越小越高，手动触发优先
        if self.manual != other.manual:
            return self.manual > other.manual
        return self.priority < other.priority


class QueueManager:
    """后台任务队列管理器"""

    def __init__(self, ocr_workers: int = 2, llm_workers: int = 2):
        """
        初始化队列管理器

        Args:
            ocr_workers: OCR worker数量
            llm_workers: LLM worker数量
        """
        self.ocr_queue = queue.PriorityQueue()
        self.llm_queue = queue.PriorityQueue()
        self.running = False
        self.ocr_threads = []
        self.llm_threads = []
        self.ocr_workers = ocr_workers
        self.llm_workers = llm_workers
        self.current_processing = set()  # 当前正在处理的文档ID
        self.stop_event = threading.Event()

    def add_ocr_task(self, doc_id: int, priority: int = 5, manual: bool = False):
        """添加OCR任务"""
        task = Task(doc_id, priority, manual)
        self.ocr_queue.put(task)

    def add_llm_task(self, doc_id: int, priority: int = 5, manual: bool = False):
        """添加LLM任务"""
        task = Task(doc_id, priority, manual)
        self.llm_queue.put(task)

    def process_ocr_task(self, task: Task):
        """处理OCR任务"""
        doc_id = task.doc_id
        session = get_session()

        try:
            document = session.query(Document).filter_by(id=doc_id).first()
            if not document:
                return

            # 检查是否已在处理
            if doc_id in self.current_processing:
                return

            # 检查LLM是否已完成（避免重复处理）
            if document.ocr_status == "completed":
                return

            self.current_processing.add(doc_id)
            document.ocr_status = "processing"
            document.ocr_last_attempt = datetime.utcnow()
            session.commit()

            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] OCR处理: {document.original_filename} (优先级: {task.priority})"
            )

            # 执行OCR
            extracted_text = process_document(str(document.file_path))

            # 检查是否成功
            if self.is_ocr_failed(extracted_text):
                # 失败
                document.ocr_status = "failed"
                document.ocr_error_message = extracted_text[:500]
                document.ocr_retry_count += 1

                # 重试逻辑
                if document.ocr_retry_count < 3:
                    print(
                        f"[{datetime.now().strftime('%H:%M:%S')}] OCR失败，稍后重试: {document.original_filename} (已重试{document.ocr_retry_count}次)"
                    )
                    # 延迟后重新加入队列
                    time.sleep(30)  # 等待30秒
                    document.ocr_status = "pending"
                    self.add_ocr_task(doc_id, priority=3, manual=False)
                else:
                    print(
                        f"[{datetime.now().strftime('%H:%M:%S')}] OCR达到最大重试次数: {document.original_filename}"
                    )
            else:
                # 成功
                document.ocr_status = "completed"
                document.ocr_error_message = None
                document.ocr_retry_count = 0
                document.extracted_text = extracted_text
                document.status = "processed"

                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] OCR成功: {document.original_filename}"
                )

                # 自动触发LLM提取
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] 添加LLM任务: {document.original_filename}"
                )
                self.add_llm_task(doc_id, priority=5, manual=False)

            session.commit()

        except Exception as e:
            session.rollback()
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] OCR异常: {doc_id} - {str(e)}"
            )
            if document:
                document.ocr_status = "failed"
                document.ocr_error_message = str(e)
                session.commit()
        finally:
            self.current_processing.discard(doc_id)
            session.close()

    def process_llm_task(self, task: Task):
        """处理LLM任务"""
        doc_id = task.doc_id
        session = get_session()

        try:
            document = session.query(Document).filter_by(id=doc_id).first()
            if not document:
                return

            # 检查是否已在处理
            if doc_id in self.current_processing:
                return

            # 检查是否手动编辑中
            if document.llm_status == "manual_edit":
                return

            # 检查OCR是否完成
            if document.ocr_status != "completed":
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] OCR未完成，跳过LLM: {document.original_filename}"
                )
                return

            # 检查是否已完成
            if document.llm_status == "completed" and not task.manual:
                return

            self.current_processing.add(doc_id)
            document.llm_status = "processing"
            document.llm_last_attempt = datetime.utcnow()
            session.commit()

            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] LLM处理: {document.original_filename} (优先级: {task.priority})"
            )

            # 执行LLM提取
            property_info = extract_property_info(
                document.extracted_text, document.llm_model
            )

            if property_info:
                # 成功
                document.llm_status = "completed"
                document.llm_error_message = None

                # 更新房产信息
                document.property_type = property_info.get("property_type")
                document.property_name = property_info.get("property_name")
                document.room_number = property_info.get("room_number")
                document.address = property_info.get("address")
                document.prefecture = property_info.get("prefecture")
                document.city = property_info.get("city")
                document.town = property_info.get("town")
                document.current_status = property_info.get("current_status")
                document.handover_date = property_info.get("handover_date")
                document.is_renovated = property_info.get("is_renovated")
                document.renovation_date = property_info.get("renovation_date")
                document.year_built = property_info.get("year_built")
                document.structure = property_info.get("structure")
                document.total_floors = property_info.get("total_floors")
                document.floor_number = property_info.get("floor_number")
                document.room_layout = property_info.get("room_layout")
                document.orientation = property_info.get("orientation")
                document.price = property_info.get("price")
                document.management_fee = property_info.get("management_fee")
                document.repair_fund = property_info.get("repair_fund")
                document.exclusive_area = property_info.get("exclusive_area")
                document.land_area = property_info.get("land_area")
                document.building_area = property_info.get("building_area")
                document.balcony_area = property_info.get("balcony_area")
                document.nearest_station = property_info.get("nearest_station")
                document.nearest_line = property_info.get("nearest_line")
                document.walking_time = property_info.get("walking_time")
                document.multiple_stations = property_info.get("multiple_stations")
                document.has_parking = property_info.get("has_parking")
                document.shopping_nearby = property_info.get("shopping_nearby")
                document.pets_allowed = property_info.get("pets_allowed")

                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] LLM成功: {document.original_filename}"
                )
            else:
                # 失败
                document.llm_status = "failed"
                document.llm_error_message = "LLM提取失败或无API Key"
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] LLM失败: {document.original_filename}"
                )

            session.commit()

        except Exception as e:
            session.rollback()
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] LLM异常: {doc_id} - {str(e)}"
            )
            if document:
                document.llm_status = "failed"
                document.llm_error_message = str(e)
                session.commit()
        finally:
            self.current_processing.discard(doc_id)
            session.close()

    def ocr_worker_loop(self, worker_id: int):
        """OCR Worker循环"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] OCR Worker {worker_id} 已启动")

        while not self.stop_event.is_set():
            try:
                task = self.ocr_queue.get(timeout=1)
                if task is None:
                    break

                self.process_ocr_task(task)
                self.ocr_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] OCR Worker {worker_id} 异常: {str(e)}"
                )

        print(f"[{datetime.now().strftime('%H:%M:%S')}] OCR Worker {worker_id} 已停止")

    def llm_worker_loop(self, worker_id: int):
        """LLM Worker循环"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] LLM Worker {worker_id} 已启动")

        while not self.stop_event.is_set():
            try:
                task = self.llm_queue.get(timeout=1)
                if task is None:
                    break

                self.process_llm_task(task)
                self.llm_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] LLM Worker {worker_id} 异常: {str(e)}"
                )

        print(f"[{datetime.now().strftime('%H:%M:%S')}] LLM Worker {worker_id} 已停止")

    def load_pending_tasks(self):
        """加载数据库中的待处理任务"""
        session = get_session()
        try:
            # 加载待OCR的文档
            pending_ocr = (
                session.query(Document).filter(Document.ocr_status == "pending").all()
            )

            for doc in pending_ocr:
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] 加载待OCR任务: {doc.original_filename}"
                )
                self.add_ocr_task(doc.id, doc.ocr_priority, manual=False)

            # 加载待LLM的文档（OCR已完成）
            pending_llm = (
                session.query(Document)
                .filter(
                    Document.llm_status == "pending", Document.ocr_status == "completed"
                )
                .all()
            )

            for doc in pending_llm:
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] 加载待LLM任务: {doc.original_filename}"
                )
                self.add_llm_task(doc.id, doc.llm_priority, manual=False)

            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] 已加载 {len(pending_ocr)} 个OCR任务, {len(pending_llm)} 个LLM任务"
            )

        finally:
            session.close()

    def start(self):
        """启动队列管理器"""
        if self.running:
            print("队列管理器已在运行")
            return

        self.running = True
        self.stop_event.clear()

        # 加载待处理任务
        self.load_pending_tasks()

        # 启动OCR Workers
        for i in range(self.ocr_workers):
            thread = threading.Thread(
                target=self.ocr_worker_loop, args=(i,), daemon=True
            )
            thread.start()
            self.ocr_threads.append(thread)

        # 启动LLM Workers
        for i in range(self.llm_workers):
            thread = threading.Thread(
                target=self.llm_worker_loop, args=(i,), daemon=True
            )
            thread.start()
            self.llm_threads.append(thread)

        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] 队列管理器已启动 (OCR: {self.ocr_workers}, LLM: {self.llm_workers})"
        )

    def stop(self):
        """停止队列管理器"""
        self.stop_event.set()
        self.running = False

        # 等待所有Worker停止
        for thread in self.ocr_threads + self.llm_threads:
            thread.join(timeout=5)

        print(f"[{datetime.now().strftime('%H:%M:%S')}] 队列管理器已停止")

    def is_ocr_failed(self, text: str) -> bool:
        """判断OCR是否失败"""
        if not text:
            return True
        failed_keywords = [
            "OCR API错误",
            "OCR API error",
            "无法连接",
            "Connection refused",
            "Max retries exceeded",
            "超时",
            "timeout",
        ]
        return any(keyword in text.lower() for keyword in failed_keywords)


# 全局队列管理器实例
queue_manager = QueueManager(ocr_workers=1, llm_workers=1)
