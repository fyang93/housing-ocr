#!/usr/bin/env python
"""测试 OpenRouter API 连接"""

import sys

sys.path.insert(0, "/net/per920a/export/das14a/satoh-lab/yang/repos/housing-ocr")

from src.housing_ocr.ocr import OPENROUTER_API_KEY, OPENROUTER_API_URL, DEFAULT_MODEL
import requests

if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "your_openrouter_api_key_here":
    print("错误: 请在 config.toml 中配置有效的 OpenRouter API Key")
    sys.exit(1)

print(f"OpenRouter API URL: {OPENROUTER_API_URL}")
print(f"Default Model: {DEFAULT_MODEL}")
print(
    f"API Key: {OPENROUTER_API_KEY[:10]}..."
    if OPENROUTER_API_KEY
    else "API Key: 未配置"
)

payload = {
    "model": DEFAULT_MODEL,
    "messages": [{"role": "user", "content": "测试连接，请回复'连接成功'"}],
    "max_tokens": 100,
}

headers = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
}

print("\n正在测试 API 连接...")
try:
    response = requests.post(
        OPENROUTER_API_URL, json=payload, headers=headers, timeout=30
    )
    response.raise_for_status()
    result = response.json()
    content = result["choices"][0]["message"]["content"]
    print(f"API 响应: {content}")
    print("✓ OpenRouter API 连接成功！")
except Exception as e:
    print(f"✗ API 连接失败: {e}")
