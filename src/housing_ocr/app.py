import os
import hashlib
import json
from datetime import datetime
from pathlib import Path
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_from_directory,
    jsonify,
)
from werkzeug.utils import secure_filename
from .database import init_db, get_session, Document
from .ocr import process_document, extract_property_info
from .queue_manager import queue_manager

app = Flask(__name__)
app.secret_key = os.urandom(24)

PROJECT_ROOT = Path(__file__).parent.parent.parent
UPLOAD_FOLDER = PROJECT_ROOT / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}


def allowed_file(filename: str) -> bool:
    if not filename:
        return False
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def calculate_file_hash(file_path: str) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def generate_hashed_filename(original_filename: str, file_hash: str) -> str:
    ext = Path(original_filename).suffix.lower()
    return f"{file_hash[:16]}{ext}"


@app.route("/")
def index():
    session = get_session()
    documents = session.query(Document).order_by(Document.created_at.desc()).all()
    session.close()
    return render_template("index.html", documents=documents)


@app.route("/upload", methods=["POST"])
def upload_file():
    files = request.files.getlist("file")
    llm_model = request.form.get("model", "rednote-hilab/dots.ocr")

    for file in files:
        if not file or not file.filename or not allowed_file(file.filename):
            continue

        session = get_session()
        try:
            filename = file.filename
            original_filename = secure_filename(filename)
            temp_path = Path(app.config["UPLOAD_FOLDER"]) / original_filename
            file.save(str(temp_path))

            file_hash = calculate_file_hash(str(temp_path))
            hashed_filename = generate_hashed_filename(original_filename, file_hash)
            file_path = Path(app.config["UPLOAD_FOLDER"]) / hashed_filename
            temp_path.rename(file_path)

            file_type = Path(original_filename).suffix.lower()[1:]
            file_size = file_path.stat().st_size

            # 创建文档记录，不立即处理
            document = Document(
                original_filename=original_filename,
                hashed_filename=hashed_filename,
                file_path=str(file_path),
                file_type=file_type,
                file_size=file_size,
                file_hash=file_hash,
                status="pending",
                ocr_retry_count=0,
                ocr_status="pending",
                llm_status="pending",
                llm_model=llm_model,
            )

            session.add(document)
            session.commit()

            # 添加到OCR队列
            queue_manager.add_ocr_task(document.id, priority=5, manual=False)

            flash(f"文件已上传，将自动处理: {original_filename}")

        except Exception as e:
            session.rollback()
            flash(f"Error processing {file.filename}: {str(e)}")
        finally:
            session.close()

    return redirect(url_for("index"))


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/document/<int:doc_id>")
def view_document(doc_id):
    session = get_session()
    document = session.query(Document).filter_by(id=doc_id).first()
    session.close()

    if document is None:
        return "Document not found", 404

    return render_template("document.html", document=document)


@app.route("/delete/<int:doc_id>", methods=["POST"])
def delete_document(doc_id):
    session = get_session()
    document = session.query(Document).filter_by(id=doc_id).first()

    if document:
        try:
            file_path_str = str(document.file_path)
            if os.path.exists(file_path_str):
                os.remove(file_path_str)
            session.delete(document)
            session.commit()
            flash("Document deleted successfully")
        except Exception as e:
            session.rollback()
            flash(f"Error: {str(e)}")

    session.close()
    return redirect(url_for("index"))


@app.route("/api/properties")
def api_properties():
    session = get_session()
    query = session.query(Document).filter(Document.status == "processed")

    property_type = request.args.get("property_type")
    prefecture = request.args.get("prefecture")
    city = request.args.get("city")
    min_price = request.args.get("min_price")
    max_price = request.args.get("max_price")

    if property_type:
        query = query.filter(Document.property_type == property_type)
    if prefecture:
        query = query.filter(Document.prefecture == prefecture)
    if city:
        query = query.filter(Document.city == city)
    if min_price:
        query = query.filter(Document.price >= int(min_price))
    if max_price:
        query = query.filter(Document.price <= int(max_price))

    properties = query.order_by(Document.created_at.desc()).all()

    result = []
    for prop in properties:
        result.append(
            {
                "id": prop.id,
                "original_filename": prop.original_filename,
                "property_name": prop.property_name or prop.original_filename,
                "property_type": prop.property_type,
                "address": prop.address,
                "prefecture": prop.prefecture,
                "city": prop.city,
                "room_layout": prop.room_layout,
                "exclusive_area": prop.exclusive_area,
                "price": prop.price,
                "nearest_station": prop.nearest_station,
                "created_at": prop.created_at.strftime("%Y-%m-%d %H:%M"),
                "ocr_status": prop.ocr_status,
                "llm_status": prop.llm_status,
                "ocr_error_message": prop.ocr_error_message,
                "llm_error_message": prop.llm_error_message,
            }
        )

    session.close()
    return jsonify(result)


@app.route("/api/property/<int:doc_id>")
def api_property_detail(doc_id):
    session = get_session()
    document = session.query(Document).filter_by(id=doc_id).first()
    session.close()

    if not document:
        return jsonify({"error": "Document not found"}), 404

    return jsonify(
        {
            "id": document.id,
            "original_filename": document.original_filename,
            "hashed_filename": document.hashed_filename,
            "file_type": document.file_type,
            "file_size": document.file_size,
            "extracted_text": document.extracted_text,
            "llm_model": document.llm_model,
            "property_type": document.property_type,
            "property_name": document.property_name,
            "room_number": document.room_number,
            "address": document.address,
            "prefure": document.prefecture,
            "city": document.city,
            "town": document.town,
            "current_status": document.current_status,
            "handover_date": document.handover_date,
            "is_renovated": document.is_renovated,
            "renovation_date": document.renovation_date,
            "year_built": document.year_built,
            "structure": document.structure,
            "total_floors": document.total_floors,
            "floor_number": document.floor_number,
            "room_layout": document.room_layout,
            "orientation": document.orientation,
            "price": document.price,
            "management_fee": document.management_fee,
            "repair_fund": document.repair_fund,
            "exclusive_area": document.exclusive_area,
            "land_area": document.land_area,
            "building_area": document.building_area,
            "balcony_area": document.balcony_area,
            "nearest_station": document.nearest_station,
            "nearest_line": document.nearest_line,
            "walking_time": document.walking_time,
            "multiple_stations": document.multiple_stations,
            "has_parking": document.has_parking,
            "shopping_nearby": document.shopping_nearby,
            "pets_allowed": document.pets_allowed,
            "created_at": document.created_at.strftime("%Y-%m-%d %H:%M"),
        }
    )


@app.route("/api/models")
def api_models():
    from .ocr import AVAILABLE_MODELS, DEFAULT_MODEL

    models = []
    model_names = {
        "google/gemini-2.0-flash-exp:free": "Gemini 2.0 Flash (免费)",
        "moonshotai/kimi-k2:free": "Kimi K2 (免费)",
        "deepseek/deepseek-r1-0528:free": "DeepSeek R1 (免费)",
        "qwen/qwen3-4b:free": "Qwen 3 4B (免费)",
    }

    for model in AVAILABLE_MODELS:
        base_name = model_names.get(model, model)
        suffix = " (默认)" if model == DEFAULT_MODEL else ""
        models.append(
            {
                "id": model,
                "name": f"{base_name}{suffix}",
            }
        )

    return jsonify(models)


@app.route("/api/reocr/<int:doc_id>", methods=["POST"])
def api_reocr(doc_id):
    session = get_session()
    document = session.query(Document).filter_by(id=doc_id).first()

    if not document:
        session.close()
        return jsonify({"error": "Document not found"}), 404

    try:
        # 重置OCR状态
        document.ocr_status = "pending"
        document.ocr_priority = 1  # 手动触发，最高优先级
        document.ocr_retry_count = 0
        document.ocr_error_message = None
        document.llm_status = "pending"  # OCR重置后，LLM也需要重新处理
        session.commit()

        # 添加到OCR队列（高优先级）
        queue_manager.add_ocr_task(doc_id, priority=1, manual=True)

        session.close()
        return jsonify({"success": True, "message": "OCR任务已加入队列（高优先级）"})

    except Exception as e:
        session.rollback()
        session.close()
        return jsonify({"error": str(e)}), 500


@app.route("/api/retry_llm/<int:doc_id>", methods=["POST"])
def api_retry_llm(doc_id):
    session = get_session()
    document = session.query(Document).filter_by(id=doc_id).first()

    if not document:
        session.close()
        return jsonify({"error": "Document not found"}), 404

    try:
        # 重置LLM状态
        document.llm_status = "pending"
        document.llm_priority = 1  # 手动触发，最高优先级
        document.llm_error_message = None
        session.commit()

        # 添加到LLM队列（高优先级）
        queue_manager.add_llm_task(doc_id, priority=1, manual=True)

        session.close()
        return jsonify(
            {"success": True, "message": "LLM提取任务已加入队列（高优先级）"}
        )

    except Exception as e:
        session.rollback()
        session.close()
        return jsonify({"error": str(e)}), 500


@app.route("/api/update_property/<int:doc_id>", methods=["POST"])
def api_update_property(doc_id):
    session = get_session()
    document = session.query(Document).filter_by(id=doc_id).first()

    if not document:
        session.close()
        return jsonify({"error": "Document not found"}), 404

    try:
        # 从请求体获取更新字段
        data = request.json

        # 更新房产信息字段
        for field in [
            "property_type",
            "property_name",
            "room_number",
            "address",
            "prefecture",
            "city",
            "town",
            "current_status",
            "handover_date",
            "is_renovated",
            "renovation_date",
            "year_built",
            "structure",
            "total_floors",
            "floor_number",
            "room_layout",
            "orientation",
            "price",
            "management_fee",
            "repair_fund",
            "exclusive_area",
            "land_area",
            "building_area",
            "balcony_area",
            "nearest_station",
            "nearest_line",
            "walking_time",
            "multiple_stations",
            "has_parking",
            "shopping_nearby",
            "pets_allowed",
        ]:
            if field in data:
                setattr(document, field, data[field])

        # 标记为手动编辑
        document.llm_status = "manual_edit"

        session.commit()
        session.close()
        return jsonify({"success": True, "message": "房产信息已更新"})

    except Exception as e:
        session.rollback()
        session.close()
        return jsonify({"error": str(e)}), 500


init_db()

# 启动队列管理器
queue_manager.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
