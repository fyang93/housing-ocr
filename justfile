# 显示所有可用命令
default:
    @just --list

# 同步 Python 依赖
sync:
    uv sync

# 启动 vLLM OCR 模型服务（需要 GPU）
ocr:
    uv run vllm serve rednote-hilab/dots.ocr \
        --trust-remote-code \
        --async-scheduling \
        --gpu-memory-utilization 0.95

# 启动后端 API 服务
# 生产模式：会自动使用已构建的前端静态文件
run:
    uv run uvicorn src.app:app --reload --port 8080

# 构建前端为静态文件（部署前使用）
build:
    cd frontend && bun run build

# 启动完整开发环境：同时运行前端开发服务器和后端
dev:
    @echo "启动后端服务 (http://localhost:8081)..."
    @uv run uvicorn src.app:app --reload --port 8081 &
    @echo "启动前端开发服务器 (http://localhost:8080)..."
    @cd frontend && bun run dev

# 生成新的安全访问令牌
# 用法: just token        # 默认 8 字符
#       just token 16     # 16 字符
token length="8":
    @uv run python scripts/generate_token.py {{length}}
