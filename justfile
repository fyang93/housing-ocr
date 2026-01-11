export PROJECT_DIR := "/net/per920a/export/das14a/satoh-lab/yang/repos/housing-ocr"

default:
    @echo "Housing OCR - 可用命令:"
    @echo "  just sync          - 安装依赖"
    @echo "  just run           - 启动 Flask 应用"
    @echo "  just server        - 启动 vLLM 服务器"
    @echo "  just stop          - 停止所有服务"

run:
    cd {{PROJECT_DIR}} && uv run python -m housing_ocr.app

server:
	uv run vllm serve rednote-hilab/dots.ocr --trust-remote-code --async-scheduling --gpu-memory-utilization 0.95

stop:
    docker stop dots-ocr-server 2>/dev/null || true
    docker rm dots-ocr-server 2>/dev/null || true

sync:
    cd {{PROJECT_DIR}} && uv sync

install:
    cd {{PROJECT_DIR}} && uv pip install -e .

clean:
    rm -rf {{PROJECT_DIR}}/uploads/* {{PROJECT_DIR}}/processed/*
