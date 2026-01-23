from PIL import Image
import httpx
import base64
import fitz
import asyncio
from typing import List


class OCRClient:
    def __init__(self, endpoint: str, model: str):
        self.endpoint = endpoint
        self.model = model
        self._client: httpx.AsyncClient | None = None
        self.max_image_size = 1400
        self.pdf_dpi = 200

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=300.0)
        return self._client

    def _resize_image(self, image: Image.Image) -> Image.Image:
        """Resize image to ensure it doesn't exceed maximum size."""
        width, height = image.size
        if width <= self.max_image_size and height <= self.max_image_size:
            return image

        ratio = min(self.max_image_size / width, self.max_image_size / height)
        new_width = int(width * ratio)
        new_height = int(height * ratio)
        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    def _pdf_to_images(self, pdf_path: str, dpi: int = 200) -> List[Image.Image]:
        images = []
        with fitz.open(pdf_path) as doc:
            for page in doc:
                mat = fitz.Matrix(dpi / 72, dpi / 72)
                pm = page.get_pixmap(matrix=mat, alpha=False)
                image = Image.frombytes("RGB", (pm.width, pm.height), pm.samples)
                image = self._resize_image(image)
                images.append(image.copy())
        return images

    def _image_to_base64(self, image: Image.Image) -> str:
        from io import BytesIO

        buffered = BytesIO()
        image.save(buffered, format="PNG", optimize=True)
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return img_str

    async def extract_text(self, file_path: str, doc_id: int | None = None) -> str:
        doc_tag = f"[ID:{doc_id}]" if doc_id else ""
        print(f"{doc_tag} 开始OCR提取...")

        file_path_lower = file_path.lower()

        if file_path_lower.endswith(".pdf"):
            # PDF parsing is blocking - run in executor
            loop = asyncio.get_event_loop()
            images = await loop.run_in_executor(None, self._pdf_to_images, file_path)
            if not images:
                raise Exception("PDF文件为空或无法读取")
            all_text = []
            for i, image in enumerate(images):
                text = await self._extract_from_image(image)
                if text:
                    all_text.append(f"[Page {i + 1}]\n{text}")
            result = "\n\n".join(all_text)
            print(f"{doc_tag} OCR完成 ({len(result)} 字符)")
            return result
        else:
            # Image opening is blocking - run in executor
            loop = asyncio.get_event_loop()
            image = await loop.run_in_executor(
                None, self._open_and_resize_image, file_path
            )
            result = await self._extract_from_image(image)
            print(f"{doc_tag} OCR完成 ({len(result) if result else 0} 字符)")
            return result

    def _open_and_resize_image(self, file_path: str) -> Image.Image:
        with Image.open(file_path) as img:
            resized = self._resize_image(img)
            # Copy the image to ensure data is independent of the closed file
            return resized.copy()

    async def _extract_from_image(self, image: Image.Image) -> str:
        img_base64 = self._image_to_base64(image)
        prompt = """Please output layout information from PDF image, including each layout element's category, and corresponding text content within. IMPORTANT: Extract ALL text content from image, including headers, titles, small text, and any other text near edges of document.

1. Layout Categories: The possible categories are ['Caption', 'Footnote', 'List-item', 'Page-footer', 'Page-header', 'Title', 'Table', 'Text'].

2. Text Extraction & Formatting Rules:
   - Table: Format its text as HTML.
   - All Others (Text, Title, etc.): Format their text as Markdown.

3. Constraints:
   - The output text must be original text from image, with no translation.
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

        client = await self._get_client()
        try:
            response = await client.post(
                f"{self.endpoint}/chat/completions", json=payload
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            raise Exception(f"OCR请求失败: {str(e)}")

    async def close(self):
        if self._client:
            await self._client.aclose()
