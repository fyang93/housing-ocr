# AGENTS.md - Housing OCR Agent Guidelines

This document provides guidelines for agentic coding systems working in this repository.

---

## Build/Lint/Test Commands

### Essential Commands

```bash
# Install/sync dependencies
just sync

# Start the Flask web application
just run

# Start the vLLM OCR server (required for OCR functionality)
just server

# Stop all services
just stop

# Install package in editable mode
just install

# Clean uploads and processed files
just clean
```

### Running Single Tests

```bash
# Test OCR processing
python scripts/test_ocr.py

# Test OpenRouter API connection
python scripts/test_openrouter.py

# Test vLLM connection
python scripts/test_vllm_connection.py
```

---

## Code Style Guidelines

### Python Version
- Python 3.12 (specified in .python-version)
- Use modern Python features (f-strings, type hints, etc.)

### Imports
Order imports in this sequence:
1. Standard library imports
2. Third-party imports
3. Local application imports

Example:
```python
import os
import hashlib
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify
from sqlalchemy import Column, Integer, String

from .database import get_session, Document
from .ocr import process_document
```

### Naming Conventions

**Functions/Variables:** snake_case
```python
def process_document(file_path: str) -> str:
    extracted_text = ...
```

**Classes:** PascalCase
```python
class QueueManager:
    def __init__(self, ocr_workers: int = 2):
        ...
```

**Constants:** UPPER_CASE
```python
VLLM_API_URL = "http://localhost:8000/v1/chat/completions"
MAX_RETRIES = 3
```

**Private methods:** prefixed with underscore
```python
def _internal_helper(self):
    ...
```

### Type Hints

Use type hints selectively for function signatures and complex types:
```python
from typing import Optional

def process_image(image_path: str, model: Optional[str] = None) -> str:
    ...
```

### Docstrings

Use triple-quoted docstrings (Chinese or English as appropriate):
```python
def load_pending_tasks(self):
    """加载数据库中的待处理任务"""
    session = get_session()
    ...
```

### Error Handling

Database operations must use try-except-rollback pattern:
```python
try:
    session.add(document)
    session.commit()
except Exception as e:
    session.rollback()
    flash(f"Error: {str(e)}")
finally:
    session.close()
```

Retry logic for external APIs:
```python
for attempt in range(MAX_RETRIES):
    try:
        response = requests.post(url, json=payload, timeout=VLLM_API_TIMEOUT)
        response.raise_for_status()
        return result
    except requests.exceptions.ConnectionError:
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY)
            continue
        else:
            return f"Connection failed after {MAX_RETRIES} attempts"
```

### Database Patterns

- Use SQLAlchemy ORM with declarative_base
- Session management via scoped_session pattern
- Always close sessions in finally blocks
- Status fields: "pending", "processing", "completed", "failed"

```python
from sqlalchemy.orm import scoped_session, sessionmaker

SessionFactory = scoped_session(sessionmaker(bind=engine))

def get_session():
    return SessionFactory()
```

### File Paths

Use pathlib.Path for all file operations:
```python
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
UPLOAD_FOLDER = PROJECT_ROOT / "uploads"
file_path = Path(app.config["UPLOAD_FOLDER"]) / filename
```

### Logging

Use print statements with timestamps for queue operations:
```python
print(f"[{datetime.now().strftime('%H:%M:%S')}] OCR处理: {filename}")
```

### Thread Safety

Queue manager uses threading for background workers:
- Daemon threads for workers
- stop_event for graceful shutdown
- current_processing set to prevent duplicate processing

### API Routes

Flask routes follow RESTful patterns:
```python
@app.route("/api/properties", methods=["GET"])
def api_properties():
    ...

@app.route("/api/update_property/<int:doc_id>", methods=["POST"])
def api_update_property(doc_id):
    ...
```

### Configuration

Load from config.toml using tomli:
```python
import tomli

def load_config() -> dict:
    config_path = PROJECT_ROOT / "config.toml"
    with open(config_path, "rb") as f:
        return tomli.load(f)
```

---

## Commit Message Style

Follow conventional commits pattern:
- `fix:` - Bug fixes
- `refactor:` - Code refactoring
- `feat:` - New features

Examples:
- `fix: 修正app.py中的prefecture拼写错误`
- `refactor: 前端代码清理和优化`
- `feat: 实现后台任务队列系统`

---

## Key Files Structure

```
src/housing_ocr/
├── app.py              # Flask application and routes
├── database.py         # SQLAlchemy models and session management
├── ocr.py              # OCR processing and LLM extraction
├── queue_manager.py    # Background task queue management
├── retry_manager.py    # Retry logic for failed tasks
└── templates/
    ├── index.html      # Main UI
    └── document.html   # Document detail view
```

---

## Linting

The project uses Ruff for linting (.ruff_cache directory present). Run Ruff before committing:
```bash
uv run ruff check src/
uv run ruff format src/
```
