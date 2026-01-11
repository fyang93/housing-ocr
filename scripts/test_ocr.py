#!/usr/bin/env python
"""测试 OCR 处理"""

import sys

sys.path.insert(0, "/net/per920a/export/das14a/satoh-lab/yang/repos/housing-ocr")

from src.housing_ocr.ocr import process_document
from pathlib import Path

# 选择一个小的PDF文件进行测试
test_file = Path(
    "/net/per920a/export/das14a/satoh-lab/yang/repos/housing-ocr/uploads/006b8b00a8a34e65.pdf"
)

if not test_file.exists():
    print(f"测试文件不存在: {test_file}")
    sys.exit(1)

print(f"开始测试 OCR 处理...")
print(f"文件: {test_file.name}")
print(f"大小: {test_file.stat().st_size / 1024:.1f} KB")
print("\n正在处理...")

result = process_document(str(test_file))

print("\n=== OCR 结果 ===")
print(result[:500])
print("\n..." if len(result) > 500 else "")
print("\n✓ OCR 处理完成" if "OCR API错误" not in result else "\n✗ OCR 处理失败")
