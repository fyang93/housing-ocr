import hashlib
import shutil
from pathlib import Path

import fitz
import tomli
import tomli_w
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image

from src.models import Database
from src.processor import DocumentProcessor


app = FastAPI(title="Housing OCR")


PROJECT_ROOT = Path(__file__).parent.parent


def load_config():
    config_path = PROJECT_ROOT / "config.toml"
    if not config_path.exists():
        raise FileNotFoundError("配置文件 config.toml 不存在,请先运行 'just setup'")
    with open(config_path, "rb") as f:
        return tomli.load(f)


def save_config(config: dict):
    config_path = PROJECT_ROOT / "config.toml"
    with open(config_path, "wb") as f:
        tomli_w.dump(config, f)


config = load_config()
db = Database(config["app"]["db_path"])


def update_models_callback(models):
    config["llm"]["models"] = list(models)
    save_config(config)


processor = DocumentProcessor(config, db, update_models_callback)


FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


@app.on_event("startup")
async def startup_event():
    import asyncio

    asyncio.create_task(processor.process_queue())


@app.get("/", response_class=HTMLResponse)
async def root():
    frontend_index = FRONTEND_DIST / "index.html"
    if frontend_index.exists():
        with open(frontend_index, encoding="utf-8") as f:
            content = f.read()
        response = HTMLResponse(content=content)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    raise HTTPException(status_code=404, detail="前端资源未找到，请先运行 'just build'")


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):

    upload_dir = Path(config["app"]["upload_dir"])
    upload_dir.mkdir(exist_ok=True)

    file.file.seek(0)
    hash_md5 = hashlib.md5()
    while chunk := file.file.read(8192):
        hash_md5.update(chunk)
    file_hash = hash_md5.hexdigest()
    file.file.seek(0)

    existing_doc = db.get_document_by_hash(file_hash)
    if existing_doc:
        return JSONResponse(
            content={
                "id": existing_doc["id"],
                "filename": existing_doc["original_filename"]
                or existing_doc["filename"],
                "duplicate": True,
                "duplicate_type": "hash",
            }
        )

    file_ext = Path(file.filename).suffix
    saved_filename = f"{file_hash}{file_ext}"
    file_path = upload_dir / saved_filename

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    original_filename = file.filename
    doc_id = db.create_document(saved_filename, original_filename)
    db.update_file_hash(doc_id, file_hash)

    from PIL import Image

    try:
        if file_path.suffix.lower() == ".pdf":
            with fitz.open(file_path) as doc_obj:
                page = doc_obj[0]
                mat = fitz.Matrix(2.0, 2.0)
                pm = page.get_pixmap(matrix=mat, alpha=False)
                width = pm.width
                height = pm.height
        else:
            with Image.open(file_path) as img:
                width, height = img.size
        db.update_image_dimensions(doc_id, width, height)
    except Exception as e:
        print(f"Error getting image dimensions: {e}")

    return JSONResponse(
        content={"id": doc_id, "filename": original_filename, "duplicate": False}
    )


@app.get("/api/documents")
async def get_documents():
    documents = db.get_all_documents()
    return JSONResponse(content={"documents": documents})


@app.get("/api/preview-info/{doc_id}")
async def get_preview_info(doc_id: int):
    """获取文档预览信息，包括尺寸和方向"""
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    upload_dir = Path(config["app"]["upload_dir"])
    file_path = upload_dir / doc["filename"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")


    try:
        if file_path.suffix.lower() == ".pdf":
            with fitz.open(file_path) as doc_obj:
                page = doc_obj[0]
                mat = fitz.Matrix(2.0, 2.0)
                pm = page.get_pixmap(matrix=mat, alpha=False)
                width = pm.width
                height = pm.height
        else:
            with Image.open(file_path) as img:
                width, height = img.size

        orientation = "landscape" if width > height else "portrait"

        return JSONResponse(
            content={"width": width, "height": height, "orientation": orientation}
        )
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/api/documents/{doc_id}")
async def get_document(doc_id: int):
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return JSONResponse(content=doc)


@app.post("/api/documents/{doc_id}/update")
async def update_document(doc_id: int, properties: dict):
    db.update_llm_status(doc_id, "done", properties)
    return JSONResponse(content={"success": True})


@app.post("/api/documents/{doc_id}/favorite")
async def toggle_favorite(doc_id: int):
    favorite = db.toggle_favorite(doc_id)
    return JSONResponse(content={"success": True, "favorite": favorite})


@app.delete("/api/documents/{doc_id}")
async def delete_document(doc_id: int):
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    upload_dir = Path(config["app"]["upload_dir"])
    file_path = upload_dir / doc["filename"]

    db.delete_document(doc_id, str(file_path))
    return JSONResponse(content={"success": True})


@app.post("/api/documents/{doc_id}/retry_llm")
async def retry_llm(doc_id: int):
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    db.reset_llm_status(doc_id)
    return JSONResponse(content={"success": True})


@app.post("/api/documents/{doc_id}/retry_ocr")
async def retry_ocr(doc_id: int):
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    db.reset_ocr_status(doc_id)
    return JSONResponse(content={"success": True})


@app.get("/api/models")
async def get_models():
    return JSONResponse(content={"models": config["llm"].get("models", [])})


@app.post("/api/models")
async def add_model(model: dict):
    model_name = model.get("name", "").strip()
    if not model_name:
        raise HTTPException(status_code=400, detail="模型名称不能为空")

    if "llm" not in config:
        config["llm"] = {}
    if "models" not in config["llm"]:
        config["llm"]["models"] = []

    new_models = list(config["llm"]["models"])
    if model_name in new_models:
        raise HTTPException(status_code=400, detail="模型已存在")

    new_models.append(model_name)
    config["llm"]["models"] = new_models
    save_config(config)

    processor.llm_extractor.models = list(new_models)

    return JSONResponse(content={"success": True, "models": new_models})


@app.post("/api/models/delete")
async def delete_model(request: dict):
    model_name = request.get("name", "").strip()
    if not model_name:
        raise HTTPException(status_code=400, detail="模型名称不能为空")

    if "llm" not in config or "models" not in config["llm"]:
        raise HTTPException(status_code=404, detail="模型不存在")

    models = list(config["llm"]["models"])
    if model_name not in models:
        raise HTTPException(status_code=404, detail="模型不存在")

    if len(models) <= 1:
        raise HTTPException(status_code=400, detail="至少保留一个模型")

    models.remove(model_name)
    config["llm"]["models"] = models
    save_config(config)

    processor.llm_extractor.models = list(models)

    return JSONResponse(content={"success": True, "models": models})


@app.post("/api/models/reorder")
async def reorder_models(request: dict):
    models = request.get("models", [])
    if not models:
        raise HTTPException(status_code=400, detail="模型列表不能为空")

    if "llm" not in config:
        config["llm"] = {}
    config["llm"]["models"] = list(models)
    save_config(config)

    processor.llm_extractor.models = list(models)

    return JSONResponse(content={"success": True, "models": models})


@app.post("/api/documents/cleanup")
async def cleanup_documents():
    """删除所有非收藏的文档"""
    upload_dir = Path(config["app"]["upload_dir"])

    all_docs = db.get_all_documents()
    unfavorited = [d for d in all_docs if d.get("favorite") != 1]

    deleted_count = 0
    for doc in unfavorited:
        file_path = upload_dir / doc["filename"]
        db.delete_document(doc["id"], str(file_path))
        deleted_count += 1

    return JSONResponse(content={"success": True, "deleted_count": deleted_count})


@app.get("/api/preview/{doc_id}")
async def preview_document(doc_id: int, thumbnail: bool = False):
    """获取文档预览，支持缩略图模式"""
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    upload_dir = Path(config["app"]["upload_dir"])
    file_path = upload_dir / doc["filename"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    import io

    if thumbnail:
        # 生成缩略图 (宽度300px，保持宽高比)
        max_width = 300

        if file_path.suffix.lower() == ".pdf":
            with fitz.open(file_path) as doc_obj:
                page = doc_obj[0]
                mat = fitz.Matrix(2.0, 2.0)
                pm = page.get_pixmap(matrix=mat, alpha=False)
                img_bytes = pm.tobytes("ppm")
                img = Image.open(io.BytesIO(img_bytes))
        else:
            img = Image.open(file_path)

        # 计算缩略图尺寸
        ratio = max_width / img.width
        new_height = int(img.height * ratio)

        # 生成缩略图
        img.thumbnail((max_width, new_height), Image.Resampling.LANCZOS)

        # 转换为JPEG (质量85，平衡质量和速度)
        buffer = io.BytesIO()
        img.convert("RGB").save(buffer, format="JPEG", quality=85, optimize=True)

        # 返回缩略图
        buffer.seek(0)
        return Response(
            content=buffer.getvalue(),
            media_type="image/jpeg",
            headers={
                "Cache-Control": "public, max-age=3600",
                "Content-Disposition": f'inline; filename="thumb_{doc["filename"]}.jpg"',
            },
        )
    else:
        # 返回原图 (有尺寸限制)
        MAX_SIZE = 1400

        if file_path.suffix.lower() == ".pdf":
            with fitz.open(file_path) as doc_obj:
                page = doc_obj[0]
                mat = fitz.Matrix(2.0, 2.0)
                pm = page.get_pixmap(matrix=mat, alpha=False)
                img = Image.frombytes("RGB", (pm.width, pm.height), pm.samples)

                if img.width > MAX_SIZE or img.height > MAX_SIZE:
                    ratio = min(MAX_SIZE / img.width, MAX_SIZE / img.height)
                    new_width = int(img.width * ratio)
                    new_height = int(img.height * ratio)
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=90, optimize=True)
            buffer.seek(0)
            return Response(content=buffer.getvalue(), media_type="image/jpeg")

        img = Image.open(file_path)
        if img.width > MAX_SIZE or img.height > MAX_SIZE:
            ratio = min(MAX_SIZE / img.width, MAX_SIZE / img.height)
            new_width = int(img.width * ratio)
            new_height = int(img.height * ratio)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        img.convert("RGB").save(buffer, format="JPEG", quality=90, optimize=True)
        buffer.seek(0)
        return Response(content=buffer.getvalue(), media_type="image/jpeg")


@app.on_event("shutdown")
def shutdown_event():
    processor.close()


@app.get("/api/locations")
async def get_locations():
    locations = db.get_all_locations()
    return JSONResponse(content={"locations": locations})


@app.post("/api/locations")
async def add_location(request: dict):
    name = request.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="位置名称不能为空")

    location = db.add_location(name)
    return JSONResponse(content={"success": True, "location": location})


@app.delete("/api/locations/{location_id}")
async def delete_location(location_id: int):
    db.delete_location(location_id)
    return JSONResponse(content={"success": True})


@app.post("/api/locations/{location_id}/display")
async def update_location_display(location_id: int, request: dict):
    show_in_tag = request.get("show_in_tag", 0)
    db.update_location_display(location_id, show_in_tag)
    return JSONResponse(content={"success": True})


@app.post("/api/locations/reorder")
async def reorder_locations(request: dict):
    location_ids = request.get("location_ids", [])
    if not location_ids:
        raise HTTPException(status_code=400, detail="位置列表不能为空")

    db.reorder_locations(location_ids)
    return JSONResponse(content={"success": True})


@app.get("/api/travel-times")
async def get_travel_times():
    import time

    start = time.time()
    durations = db.get_all_travel_times()
    elapsed = time.time() - start
    print(
        f"get_travel_times completed in {elapsed:.3f}s, returned {len(durations)} records"
    )
    return JSONResponse(content={"travel_times": durations})


@app.post("/api/travel-times/batch")
async def set_travel_times_batch(request: dict):
    durations = request.get("travel_times", [])

    if not isinstance(durations, list):
        raise HTTPException(status_code=400, detail="travel_times必须是数组")

    for d in durations:
        station_name = d.get("station_name", "").strip()
        location_id = d.get("location_id")
        duration = d.get("duration")

        if not station_name or location_id is None or duration is None:
            continue

        db.set_travel_time(station_name, location_id, duration)
    return JSONResponse(content={"success": True})
