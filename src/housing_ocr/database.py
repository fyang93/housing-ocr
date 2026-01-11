from datetime import datetime
from pathlib import Path
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    BigInteger,
    Float,
)
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session

Base = declarative_base()

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATABASE_PATH = PROJECT_ROOT / "database" / "ocr.db"


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    original_filename = Column(String(500), nullable=False)
    hashed_filename = Column(String(64), unique=True, nullable=False)
    file_path = Column(String(1000), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    file_hash = Column(String(64), nullable=False)
    extracted_text = Column(Text, nullable=True)
    status = Column(String(50), default="pending")
    ocr_retry_count = Column(Integer, default=0)

    ocr_status = Column(String(20), default="pending")
    ocr_priority = Column(Integer, default=5)
    ocr_error_message = Column(Text, nullable=True)
    ocr_last_attempt = Column(DateTime, nullable=True)

    llm_status = Column(String(20), default="pending")
    llm_priority = Column(Integer, default=5)
    llm_error_message = Column(Text, nullable=True)
    llm_last_attempt = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    llm_model = Column(String(100), nullable=True)

    property_type = Column(String(100), nullable=True)
    property_name = Column(String(200), nullable=True)
    room_number = Column(String(50), nullable=True)
    address = Column(String(500), nullable=True)
    prefecture = Column(String(50), nullable=True)
    city = Column(String(100), nullable=True)
    town = Column(String(100), nullable=True)
    current_status = Column(String(100), nullable=True)
    handover_date = Column(String(50), nullable=True)
    is_renovated = Column(String(10), nullable=True)
    renovation_date = Column(String(50), nullable=True)
    year_built = Column(Integer, nullable=True)
    structure = Column(String(100), nullable=True)
    total_floors = Column(Integer, nullable=True)
    floor_number = Column(Integer, nullable=True)
    room_layout = Column(String(50), nullable=True)
    orientation = Column(String(50), nullable=True)
    price = Column(Integer, nullable=True)
    management_fee = Column(Integer, nullable=True)
    repair_fund = Column(Integer, nullable=True)
    exclusive_area = Column(Float, nullable=True)
    land_area = Column(Float, nullable=True)
    building_area = Column(Float, nullable=True)
    balcony_area = Column(Float, nullable=True)
    nearest_station = Column(String(200), nullable=True)
    nearest_line = Column(String(200), nullable=True)
    walking_time = Column(Integer, nullable=True)
    multiple_stations = Column(String(10), nullable=True)
    has_parking = Column(String(10), nullable=True)
    shopping_nearby = Column(Text, nullable=True)
    pets_allowed = Column(String(10), nullable=True)

    def __repr__(self):
        return f"<Document {self.original_filename} -> {self.hashed_filename}>"

    @staticmethod
    def calculate_file_hash(file_path: str) -> str:
        import hashlib

        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    @staticmethod
    def generate_hashed_filename(original_filename: str, file_hash: str) -> str:
        ext = Path(original_filename).suffix.lower()
        return f"{file_hash[:16]}{ext}"


DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
engine = create_engine(DATABASE_URL, echo=False)
SessionFactory = scoped_session(sessionmaker(bind=engine))


def init_db():
    Base.metadata.create_all(engine)


def get_session():
    return SessionFactory()
