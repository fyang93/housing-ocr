import threading
import time
from datetime import datetime
from typing import Optional
from .database import get_session, Document
from .ocr import process_document, extract_property_info


class OCRRetryManager:
    """后台OCR重试管理器"""

    def __init__(self, check_interval: int = 300, max_retries: int = 3):
        """
        初始化重试管理器

        Args:
            check_interval: 检查间隔（秒），默认5分钟
            max_retries: 最大重试次数
        """
        self.check_interval = check_interval
        self.max_retries = max_retries
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.current_processing = set()  # 当前正在处理的文档ID

    def is_ocr_failed(self, extracted_text: str) -> bool:
        """判断OCR是否失败"""
        if not extracted_text:
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
        return any(keyword in extracted_text.lower() for keyword in failed_keywords)

    def get_failed_documents(self):
        """获取需要重试的文档"""
        session = get_session()
        try:
            documents = (
                session.query(Document)
                .filter(Document.ocr_retry_count < self.max_retries)
                .all()
            )

            failed_docs = []
            for doc in documents:
                if doc.id not in self.current_processing and self.is_ocr_failed(
                    doc.extracted_text or ""
                ):
                    failed_docs.append(doc)

            return failed_docs
        finally:
            session.close()

    def process_document_retry(self, doc_id: int) -> bool:
        """处理单个文档的重试"""
        session = get_session()
        try:
            document = session.query(Document).filter_by(id=doc_id).first()
            if not document:
                return False

            # 检查是否已经在处理
            if doc_id in self.current_processing:
                return False

            self.current_processing.add(doc_id)
            print(
                f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始重试OCR: {document.original_filename} (第{document.ocr_retry_count + 1}次)"
            )

            # 重新处理OCR
            extracted_text = process_document(str(document.file_path))

            # 检查是否成功
            if self.is_ocr_failed(extracted_text):
                # 失败，增加重试计数
                document.ocr_retry_count += 1
                document.extracted_text = extracted_text
                session.commit()
                print(
                    f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] OCR重试失败: {document.original_filename} (已重试{document.ocr_retry_count}次)"
                )
                success = False
            else:
                # 成功，重置重试计数并抽取房产信息
                document.ocr_retry_count = 0
                document.extracted_text = extracted_text
                document.status = "processed"

                # 抽取房产信息
                property_info = extract_property_info(
                    extracted_text, document.llm_model
                )
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

                session.commit()
                print(
                    f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] OCR重试成功: {document.original_filename}"
                )
                success = True

            return success

        except Exception as e:
            session.rollback()
            print(
                f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] OCR重试异常: {document.original_filename} - {str(e)}"
            )
            return False
        finally:
            self.current_processing.discard(doc_id)
            session.close()

    def run_retry_loop(self):
        """运行重试循环"""
        print(
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] OCR重试管理器已启动，检查间隔: {self.check_interval}秒"
        )

        while self.running:
            try:
                failed_docs = self.get_failed_documents()

                if failed_docs:
                    print(
                        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 发现 {len(failed_docs)} 个需要重试的文档"
                    )

                    for doc in failed_docs:
                        if not self.running:
                            break
                        self.process_document_retry(doc.id)
                        time.sleep(5)  # 每个文档之间间隔5秒
                else:
                    print(
                        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 没有需要重试的文档，等待下次检查..."
                    )

            except Exception as e:
                print(
                    f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 重试循环异常: {str(e)}"
                )

            # 等待下次检查
            for _ in range(self.check_interval):
                if not self.running:
                    break
                time.sleep(1)

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] OCR重试管理器已停止")

    def start(self):
        """启动重试管理器"""
        if self.running:
            print("OCR重试管理器已在运行")
            return

        self.running = True
        self.thread = threading.Thread(target=self.run_retry_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """停止重试管理器"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=10)


# 全局重试管理器实例
retry_manager = OCRRetryManager(check_interval=300, max_retries=3)
