from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import urllib.parse
import tomli
import tomli_w
import shutil
import fitz
from models import Database
from processor import DocumentProcessor


app = FastAPI(title="Housing OCR")


PROJECT_ROOT = Path(__file__).parent


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


app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "static"), name="static")


@app.on_event("startup")
async def startup_event():
    import asyncio

    asyncio.create_task(processor.process_queue())


@app.get("/", response_class=HTMLResponse)
async def root():
    template_path = PROJECT_ROOT / "templates" / "index.html"
    with open(template_path, encoding="utf-8") as f:
        content = f.read()
    response = HTMLResponse(content=content)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    upload_dir = Path(config["app"]["upload_dir"])
    upload_dir.mkdir(exist_ok=True)

    filename = f"{file.filename}"
    file_path = upload_dir / filename

    if file_path.exists():
        existing_doc = db.get_document_by_filename(filename)
        if existing_doc:
            return JSONResponse(
                content={
                    "id": existing_doc["id"],
                    "filename": filename,
                    "duplicate": True,
                }
            )

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    doc_id = db.create_document(filename)
    return JSONResponse(
        content={"id": doc_id, "filename": filename, "duplicate": False}
    )


@app.get("/api/documents")
async def get_documents():
    documents = db.get_all_documents()
    return JSONResponse(content={"documents": documents})


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
async def preview_document(doc_id: int):
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    upload_dir = Path(config["app"]["upload_dir"])
    file_path = upload_dir / doc["filename"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    MAX_SIZE = 1400

    if file_path.suffix.lower() == ".pdf":
        from PIL import Image

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

            from io import BytesIO

            img_bytes = BytesIO()
            img.save(img_bytes, format="PNG", optimize=True)
            return Response(content=img_bytes.getvalue(), media_type="image/png")

    from PIL import Image

    img = Image.open(file_path)
    if img.width > MAX_SIZE or img.height > MAX_SIZE:
        ratio = min(MAX_SIZE / img.width, MAX_SIZE / img.height)
        new_width = int(img.width * ratio)
        new_height = int(img.height * ratio)
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    from io import BytesIO

    img_bytes = BytesIO()
    img.save(img_bytes, format="PNG", optimize=True)
    return Response(content=img_bytes.getvalue(), media_type="image/png")


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

    location_id = db.add_location(name)
    return JSONResponse(content={"success": True, "id": location_id})


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


@app.get("/api/station_durations")
async def get_station_durations():
    durations = db.get_all_station_durations()
    return JSONResponse(content={"durations": durations})


@app.get("/api/station_durations/{station_name}")
async def get_station_duration(station_name: str):
    durations = db.get_station_durations(station_name)
    return JSONResponse(content={"durations": durations})


@app.post("/api/station_durations")
async def set_station_duration(request: dict):
    station_name = request.get("station_name", "").strip()
    location_id = request.get("location_id")
    duration = request.get("duration")

    if not station_name:
        raise HTTPException(status_code=400, detail="车站名称不能为空")
    if location_id is None:
        raise HTTPException(status_code=400, detail="位置ID不能为空")
    if duration is None:
        raise HTTPException(status_code=400, detail="时长不能为空")

    db.set_station_duration(station_name, location_id, duration)
    return JSONResponse(content={"success": True})


@app.post("/api/station_durations/batch")
async def set_station_durations_batch(request: dict):
    durations = request.get("durations", [])

    if not isinstance(durations, list):
        raise HTTPException(status_code=400, detail="durations必须是数组")

    for d in durations:
        station_name = d.get("station_name", "").strip()
        location_id = d.get("location_id")
        duration = d.get("duration")

        if not station_name or location_id is None or duration is None:
            continue

        db.set_station_duration(station_name, location_id, duration)

    return JSONResponse(content={"success": True})


@app.delete("/api/station_durations")
async def delete_station_duration(request: dict):
    station_name = request.get("station_name", "").strip()
    location_id = request.get("location_id")

    if not station_name:
        raise HTTPException(status_code=400, detail="车站名称不能为空")
    if location_id is None:
        raise HTTPException(status_code=400, detail="位置ID不能为空")

    db.delete_station_duration(station_name, location_id)
    return JSONResponse(content={"success": True})
