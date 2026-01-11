#!/usr/bin/env python
"""测试 vLLM OCR API 连接"""

import sys

sys.path.insert(0, "/net/per920a/export/das14a/satoh-lab/yang/repos/housing-ocr")

from src.housing_ocr.ocr import VLLM_API_URL, VLLM_API_TIMEOUT
import requests

print(f"vLLM API URL: {VLLM_API_URL}")
print(f"Timeout: {VLLM_API_TIMEOUT}秒")

print("\n正在测试 vLLM 连接...")
try:
    models_url = VLLM_API_URL.replace("/chat/completions", "/models")
    response = requests.get(models_url, timeout=10)
    response.raise_for_status()
    result = response.json()
    print(f"✓ vLLM 服务器连接成功！")
    print(f"  可用模型: {[m['id'] for m in result.get('data', [])]}")
except requests.exceptions.ConnectionError as e:
    print(f"✗ 无法连接到 vLLM 服务器 ({VLLM_API_URL})")
    print(f"  请确保 vLLM 服务器正在运行: just server")
    sys.exit(1)
except requests.exceptions.RequestException as e:
    print(f"✗ 连接错误: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ 连接错误: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ 连接错误: {e}")
    sys.exit(1)
