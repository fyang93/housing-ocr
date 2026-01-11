#!/usr/bin/env python3

import base64
from io import BytesIO
from pathlib import Path
from typing import List

import httpx
import fitz
from PIL import Image

PDF_PATH = Path("uploads/藤和シティホームズ板橋ADVANTIA.pdf")
VLLM_API_URL = "http://localhost:8000/v1/chat/completions"
MODEL = "Qwen/Qwen2-VL-7B-Instruct"


def test_pdf_to_images():
    print("=" * 60)
    print("测试1: PDF转图片")
    print("=" * 60)
    try:
        images = []
        with fitz.open(str(PDF_PATH)) as doc:
            for page in doc:
                mat = fitz.Matrix(300 / 72, 300 / 72)
                pm = page.get_pixmap(matrix=mat, alpha=False)
                image = Image.frombytes("RGB", (pm.width, pm.height), pm.samples)

                width, height = image.size
                if width > 1550 or height > 1550:
                    ratio = min(1550 / width, 1550 / height)
                    new_width = int(width * ratio)
                    new_height = int(height * ratio)
                    image = image.resize((new_width, new_height), Image.LANCZOS)

                images.append(image)

        print(f"✓ PDF转换成功，共 {len(images)} 页")
        for i, img in enumerate(images[:3]):
            print(f"  页 {i + 1}: {img.size[0]}x{img.size[1]} 像素")

        return images
    except Exception as e:
        print(f"✗ PDF转换失败: {e}")
        return None


def test_image_encoding(images: List[Image.Image]):
    print("\n" + "=" * 60)
    print("测试2: 图片Base64编码")
    print("=" * 60)

    encoded_images = []
    for i, img in enumerate(images[:3]):
        try:
            buffer = BytesIO()
            img.save(buffer, format="PNG", optimize=True)
            buffer.seek(0)
            img_base64 = base64.b64encode(buffer.read()).decode("utf-8")
            img_size = len(img_base64)
            print(f"✓ 页 {i + 1}: Base64编码成功，大小: {img_size / 1024:.1f}KB")
            encoded_images.append(img_base64)
        except Exception as e:
            print(f"✗ 页 {i + 1}: 编码失败: {e}")

    return encoded_images


def test_ocr_english_prompt(encoded_images: List[str]):
    print("\n" + "=" * 60)
    print("测试3: OCR (英文prompt)")
    print("=" * 60)

    if not encoded_images:
        print("✗ 没有编码的图片可供测试")
        return

    try:
        prompt = "Extract all text from this image. Return the text exactly as shown."

        payload = {
            "model": MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{encoded_images[0]}"
                            },
                        },
                    ],
                }
            ],
            "temperature": 0.1,
            "max_tokens": 4096,
        }

        print(f"发送请求到: {VLLM_API_URL}")
        with httpx.Client(timeout=120.0) as client:
            response = client.post(f"{VLLM_API_URL}/chat/completions", json=payload)

        if response.status_code == 200:
            result = response.json()
            ocr_text = result["choices"][0]["message"]["content"]
            print(f"✓ OCR调用成功")
            print(f"\n前500个字符:")
            print("-" * 60)
            print(ocr_text[:500])
            print("-" * 60)

            lines = ocr_text.split("\n")
            unique_lines = list(dict.fromkeys(lines))
            if len(unique_lines) < len(lines) * 0.8:
                print(f"\n⚠ 警告: 检测到大量重复内容！")
                print(f"  总行数: {len(lines)}, 唯一行数: {len(unique_lines)}")

            return ocr_text
        else:
            print(f"✗ OCR调用失败: HTTP {response.status_code}")
            print(f"  响应: {response.text[:500]}")
            return None

    except httpx.ConnectError:
        print("✗ 无法连接到vLLM服务器")
        print("  请确保运行: just server")
        return None
    except Exception as e:
        print(f"✗ OCR调用异常: {e}")
        return None


def test_ocr_japanese_prompt(encoded_images: List[str]):
    print("\n" + "=" * 60)
    print("测试4: OCR (日文prompt)")
    print("=" * 60)

    if not encoded_images:
        print("✗ 没有编码的图片可供测试")
        return

    try:
        prompt = """この画像からすべてのテキストを抽出してください。画像に表示されている通りのテキストを正確に返してください。"""

        payload = {
            "model": MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{encoded_images[0]}"
                            },
                        },
                    ],
                }
            ],
            "temperature": 0.1,
            "max_tokens": 4096,
        }

        print(f"发送请求到: {VLLM_API_URL}")
        with httpx.Client(timeout=120.0) as client:
            response = client.post(f"{VLLM_API_URL}/chat/completions", json=payload)

        if response.status_code == 200:
            result = response.json()
            ocr_text = result["choices"][0]["message"]["content"]
            print(f"✓ OCR调用成功")
            print(f"\n前500个字符:")
            print("-" * 60)
            print(ocr_text[:500])
            print("-" * 60)

            lines = ocr_text.split("\n")
            unique_lines = list(dict.fromkeys(lines))
            if len(unique_lines) < len(lines) * 0.8:
                print(f"\n⚠ 警告: 检测到大量重复内容！")
                print(f"  总行数: {len(lines)}, 唯一行数: {len(unique_lines)}")

            return ocr_text
        else:
            print(f"✗ OCR调用失败: HTTP {response.status_code}")
            return None

    except Exception as e:
        print(f"✗ OCR调用异常: {e}")
        return None


def test_detailed_prompt(encoded_images: List[str]):
    print("\n" + "=" * 60)
    print("测试5: OCR (详细prompt)")
    print("=" * 60)

    if not encoded_images:
        print("✗ 没有编码的图片可供测试")
        return

    try:
        prompt = """Extract all text from this image in a line-by-line fashion. For each line of text in the image:
1. Identify the exact text content
2. Note its position (if meaningful)
3. Report it once only
Do not repeat lines. If you see the same phrase appearing multiple times, only report it once with a note like "(appears X times)".
Return the text exactly as shown, organized by lines from top to bottom."""

        payload = {
            "model": MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{encoded_images[0]}"
                            },
                        },
                    ],
                }
            ],
            "temperature": 0.1,
            "max_tokens": 4096,
        }

        print(f"发送请求到: {VLLM_API_URL}")
        with httpx.Client(timeout=120.0) as client:
            response = client.post(f"{VLLM_API_URL}/chat/completions", json=payload)

        if response.status_code == 200:
            result = response.json()
            ocr_text = result["choices"][0]["message"]["content"]
            print(f"✓ OCR调用成功")
            print(f"\n前500个字符:")
            print("-" * 60)
            print(ocr_text[:500])
            print("-" * 60)

            lines = ocr_text.split("\n")
            unique_lines = list(dict.fromkeys(lines))
            if len(unique_lines) < len(lines) * 0.8:
                print(f"\n⚠ 警告: 检测到大量重复内容！")
                print(f"  总行数: {len(lines)}, 唯一行数: {len(unique_lines)}")
            else:
                print(f"\n✓ 内容唯一性良好 ({len(unique_lines)}/{len(lines)})")

            return ocr_text
        else:
            print(f"✗ OCR调用失败: HTTP {response.status_code}")
            return None

    except Exception as e:
        print(f"✗ OCR调用异常: {e}")
        return None


def main():
    print("开始诊断OCR问题\n")

    if not PDF_PATH.exists():
        print(f"✗ PDF文件不存在: {PDF_PATH}")
        return

    print(f"PDF文件: {PDF_PATH}")
    print(f"文件大小: {PDF_PATH.stat().st_size / 1024:.1f}KB\n")

    images = test_pdf_to_images()

    if images:
        encoded = test_image_encoding(images)

        if encoded:
            test_ocr_english_prompt(encoded)
            test_ocr_japanese_prompt(encoded)
            test_detailed_prompt(encoded)

    print("\n" + "=" * 60)
    print("诊断完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
