import asyncio
from typing import Any, cast
import httpx

from src.llm import AllModelsFailedError, LLMExtractor
from src.models import Database
from src.processor import DocumentProcessor


class _FakeDB:
    def __init__(self):
        self.doc = {
            "id": 1,
            "filename": "a.pdf",
            "original_filename": "a.pdf",
            "ocr_status": "done",
            "llm_status": "pending",
            "ocr_text": "dummy ocr text",
        }
        self.updated_status = []

    def get_document(self, doc_id):
        return dict(self.doc)

    def update_llm_status(self, doc_id, status, properties=None, extracted_model=None):
        self.updated_status.append(status)
        self.doc["llm_status"] = status

    def update_ocr_status(self, doc_id, status, ocr_text=None):
        self.doc["ocr_status"] = status

    def increment_retry(self, doc_id):
        return None


class _AlwaysFailExtractor:
    async def extract_properties(self, ocr_text, doc_id=None):
        raise AllModelsFailedError("all failed")


class _SlowExtractor:
    async def extract_properties(self, ocr_text, doc_id=None):
        await asyncio.sleep(0.05)
        return {"_extracted_by_model": "mock", "property_name": "x", "price": 1}


def test_process_document_marks_failed_when_all_models_fail(tmp_path):
    processor = DocumentProcessor.__new__(DocumentProcessor)
    processor.config = {"app": {"upload_dir": str(tmp_path)}}
    fake_db = _FakeDB()
    processor.db = cast(Database, fake_db)
    processor.llm_extractor = cast(LLMExtractor, _AlwaysFailExtractor())
    processor.llm_timeout_seconds = 1

    asyncio.run(processor.process_document(1))

    assert "failed" in fake_db.updated_status


def test_process_document_marks_failed_when_llm_timeout(tmp_path):
    processor = DocumentProcessor.__new__(DocumentProcessor)
    processor.config = {"app": {"upload_dir": str(tmp_path)}}
    fake_db = _FakeDB()
    processor.db = cast(Database, fake_db)
    processor.llm_extractor = cast(LLMExtractor, _SlowExtractor())
    processor.llm_timeout_seconds = 0.01

    asyncio.run(processor.process_document(1))

    assert "failed" in fake_db.updated_status


def test_retry_all_failed_llm_sets_pending_only_for_done_ocr(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    doc_a = db.create_document("a.pdf", "a.pdf")
    doc_b = db.create_document("b.pdf", "b.pdf")

    db.update_ocr_status(doc_a, "done", "ocr")
    db.update_llm_status(doc_a, "failed")

    db.update_ocr_status(doc_b, "pending")
    db.update_llm_status(doc_b, "failed")

    affected = db.retry_all_failed_llm()
    a_after = db.get_document(doc_a)
    b_after = db.get_document(doc_b)
    assert a_after is not None
    assert b_after is not None

    assert affected == 1
    assert a_after["llm_status"] == "pending"
    assert b_after["llm_status"] == "failed"


class _OkResponse:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"property_name":"x","price":1000,"room_layout":"2LDK"}'
                    }
                }
            ]
        }


class _TimeoutThenOkClient:
    def __init__(self):
        self.calls = []

    async def post(self, url, json=None, timeout=None, headers=None):
        assert json is not None
        model = json["model"]
        self.calls.append(model)
        if model == "m1":
            raise httpx.ReadTimeout("timeout", request=httpx.Request("POST", url))
        return _OkResponse()


def test_llm_timeout_switches_to_next_model_and_cools_down():
    extractor = LLMExtractor(
        "k", "https://example.com", ["m1", "m2"], request_timeout_seconds=0.01
    )
    fake_client = _TimeoutThenOkClient()

    async def _fake_get_client():
        return fake_client

    setattr(extractor, "_get_client", cast(Any, _fake_get_client))

    result = asyncio.run(extractor.extract_properties("hello", 1))

    assert result["_extracted_by_model"] == "m2"
    assert fake_client.calls == ["m1", "m2"]
    assert "m1" in extractor.model_cooldown_times
