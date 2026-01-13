from PIL import Image
import httpx
import base64
import fitz
from typing import List


class OCRClient:
    def __init__(self, endpoint: str, model: str):
        self.endpoint = endpoint
        self.model = model
        self.client = httpx.Client(timeout=300.0)
        self.max_image_size = 1400
        self.pdf_dpi = 200

    def _resize_image(self, image: Image.Image) -> Image.Image:
        """调整图片尺寸，确保不超过最大限制"""
        width, height = image.size
        if width <= self.max_image_size and height <= self.max_image_size:
            return image

        ratio = min(self.max_image_size / width, self.max_image_size / height)
        new_width = int(width * ratio)
        new_height = int(height * ratio)
        return image.resize((new_width, new_height), Image.LANCZOS)

    def _pdf_to_images(self, pdf_path: str, dpi: int = None) -> List[Image.Image]:
        if dpi is None:
            dpi = self.pdf_dpi
        images = []
        with fitz.open(pdf_path) as doc:
            for page in doc:
                mat = fitz.Matrix(dpi / 72, dpi / 72)
                pm = page.get_pixmap(matrix=mat, alpha=False)
                image = Image.frombytes("RGB", (pm.width, pm.height), pm.samples)
                image = self._resize_image(image)
                images.append(image)
        return images

    def _image_to_base64(self, image: Image.Image) -> str:
        from io import BytesIO

        buffered = BytesIO()
        image.save(buffered, format="PNG", optimize=True)
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return img_str

    def extract_text(self, file_path: str, doc_id: int = None) -> str:
        doc_tag = f"[ID:{doc_id}]" if doc_id else ""
        print(f"{doc_tag} 开始OCR提取...")

        file_path_lower = file_path.lower()

        if file_path_lower.endswith(".pdf"):
            images = self._pdf_to_images(file_path)
            if not images:
                raise Exception("PDF文件为空或无法读取")
            all_text = []
            for i, image in enumerate(images):
                text = self._extract_from_image(image)
                if text:
                    all_text.append(f"[Page {i + 1}]\n{text}")
            result = "\n\n".join(all_text)
            print(f"{doc_tag} OCR完成 ({len(result)} 字符)")
            return result
        else:
            image = Image.open(file_path)
            image = self._resize_image(image)
            result = self._extract_from_image(image)
            print(f"{doc_tag} OCR完成 ({len(result) if result else 0} 字符)")
            return result

    def _extract_from_image(self, image: Image.Image) -> str:
        img_base64 = self._image_to_base64(image)
        prompt = """Please output the layout information from the PDF image, including each layout element's category, and the corresponding text content within. IMPORTANT: Extract ALL text content from the image, including headers, titles, small text, and any other text near the edges of the document.

1. Layout Categories: The possible categories are ['Caption', 'Footnote', 'List-item', 'Page-footer', 'Page-header', 'Title', 'Table', 'Text'].

2. Text Extraction & Formatting Rules:
   - Table: Format its text as HTML.
   - All Others (Text, Title, etc.): Format their text as Markdown.

3. Constraints:
   - The output text must be the original text from the image, with no translation.
   - All layout elements must be sorted according to human reading order.
   - CRITICAL: Ensure ALL text is captured, including headers, footers, and any small text near document edges.

4. Final Output: The entire output must be a single JSON object.
"""

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{img_base64}"},
                        },
                    ],
                }
            ],
            "temperature": 0.1,
        }

        try:
            response = self.client.post(
                f"{self.endpoint}/chat/completions", json=payload
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            raise Exception(f"OCR请求失败: {str(e)}")

    def close(self):
        self.client.close()
