# AGENTS.md

This file provides guidelines for AI agents working in this repository.

## Project Overview

Housing OCR is a Japanese real estate document intelligent parsing system. It extracts structured data (price, area, address, station, room layout, etc.) from PDFs and images.

## Build, Lint, and Test Commands

### Python Backend

```bash
# Install Python dependencies
just sync

# Run backend (development with auto-reload on port 8080)
just run

# Run linter (ruff)
uv run ruff check src/
uv run ruff check src/ --fix  # Auto-fix issues

# Run tests
uv run pytest tests/
uv run pytest tests/ -v  # Verbose output

# Run a single test
uv run pytest tests/test_file.py::TestClass::test_method

# Run tests matching a pattern
uv run pytest tests/ -k "test_name_pattern"
```

### Frontend

```bash
# Install frontend dependencies (Bun)
cd frontend && bun install

# Run frontend dev server (port 8080)
cd frontend && bun run dev

# Build frontend for production
just build
cd frontend && bun run build

# Type check frontend
cd frontend && npx vue-tsc --noEmit
```

### Full Development Environment

```bash
# Start both frontend and backend dev servers
just dev
```

## Code Style Guidelines

### Python (Backend)

- **Formatting**: Use ruff for formatting and linting. Run `uv run ruff check src/ --fix` before committing.
- **Type Hints**: Use type hints for all function signatures. Import from `typing` (e.g., `Optional`, `Dict`, `Any`, `List`).
- **Imports**: Use absolute imports from `src` package (e.g., `from src.models import Database`). Sort imports alphabetically within groups.
- **Naming**:
  - Classes: `PascalCase` (e.g., `Database`, `DocumentProcessor`)
  - Functions/variables: `snake_case` (e.g., `get_document`, `upload_dir`)
  - Constants: `UPPER_SNAKE_CASE` (e.g., `MAX_SIZE`, `PROJECT_ROOT`)
  - Private methods: prefix with `_` (e.g., `_init_db`)
- **Docstrings**: Use triple quotes `"""` for all public functions and classes. Include Args and Returns sections.
- **Line Length**: Max 120 characters.
- **Error Handling**:
  - Use `HTTPException` for API errors with meaningful detail messages
  - Use try/except blocks for operations that may fail (file I/O, database, image processing)
  - Log errors with `print(f"Error: {e}")` or let exceptions propagate in background tasks
- **Database**: Use `sqlite3.Row` for row_factory. Always close connections explicitly. Use parameterized queries (`?` placeholders) to prevent SQL injection.

### TypeScript/Vue (Frontend)

- **Formatting**: Follow Vue 3 + TypeScript conventions. Use Vite's default formatting.
- **Type Hints**: Define interfaces for props, API responses, and complex objects.
- **Naming**: `PascalCase` for components, `camelCase` for variables/functions.
- **Components**: Use Composition API with `<script setup>`.
- **Styling**: Use TailwindCSS 4 utility classes. Keep components self-contained.

### General

- **Language**: All code, comments, and commit messages in English (or Japanese for user-facing strings per project convention).
- **Configuration**: Store secrets in `config.toml`, never commit to git.
- **File Structure**:
  ```
  src/
    ├── app.py          # FastAPI routes
    ├── models.py       # Database class
    ├── ocr.py          # OCR client
    ├── llm.py          # LLM extraction
    └── processor.py    # Async queue processor
  frontend/
    ├── src/            # Vue components
    ├── dist/           # Built assets
    └── vite.config.ts
  ```

## Architecture Notes

- **Backend**: FastAPI on Python 3.12+ with SQLite database
- **OCR**: vLLM serving `rednote-hilab/dots.ocr` model at `http://localhost:8000/v1`
- **LLM**: OpenRouter API for structured data extraction (configurable models)
- **Async Processing**: Documents are queued and processed asynchronously by `DocumentProcessor`
- **Frontend**: Vue 3 SPA served by FastAPI in production, Vite dev server in development

## Common Patterns

### Adding a New API Endpoint

```python
@app.get("/api/newendpoint")
async def new_endpoint(param: int):
    """Description of what this endpoint does."""
    result = db.get_data(param)
    if not result:
        raise HTTPException(status_code=404, detail="Not found")
    return JSONResponse(content={"data": result})
```

### Database Operations

```python
def get_data(self, doc_id: int) -> Optional[Dict[str, Any]]:
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM table WHERE id = ?", (doc_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None
```

### Background Processing

```python
from src.processor import DocumentProcessor

async def process_queue():
    while True:
        # process pending items
        await asyncio.sleep(1)
```
