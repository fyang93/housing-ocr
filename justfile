# 显示所有可用命令
default:
    @just --list

# 同步项目依赖
sync:
    uv sync

# 创建配置文件
setup:
    @test -f config.toml || cp config.example.toml config.toml
    @mkdir -p uploads
    @mkdir -p static templates
    @echo "✓ 配置完成,请编辑 config.toml 设置API key"

# 启动OCR服务
ocr:
    uv run vllm serve rednote-hilab/dots.ocr \
        --trust-remote-code \
        --async-scheduling \
        --gpu-memory-utilization 0.95

# 启动Web应用
run:
    uv run uvicorn app:app --reload --port 8080

# 清理数据和临时文件
clean:
    rm -rf uploads/* data.db __pycache__

# Lint检查
lint:
    uv run ruff check src/

# Format代码
fmt:
    uv run ruff format src/
