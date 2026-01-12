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
        self.pdf_dpi = 300

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
        prompt = """Extract structured information from this Japanese real estate document.

CRITICAL: You MUST identify and extract ALL of the following fields if present:

1. property_type - 物件種別 (マンション/一戸建て/土地 etc.)
2. property_name - 物件名称
3. address - 住所 (including 都道府県, 市区町村, 番地)
4. prefecture - 都道府県
5. city - 市区町村
6. land_rights - 権利形態 (所有権/借地権)
7. current_status - 現況 (空室/居住中 etc.)
8. handover_date - 引渡可能時期
9. build_year - 築年月 (year in Western calendar, e.g., 2001)
10. structure - 構造 (RC造/ SRC造/ 木造 etc.)
11. total_floors - 総戸数 or 階数
12. floor_number - 所在階
13. room_layout - 間取タイプ (1LDK/2LDK/3LDK etc.)
14. orientation - 向き (南/北/東/西 etc.)
15. price - 価格 in 万円
16. management_fee - 管理費 (月額〇〇円)
17. repair_fee - 修繕積立金 (月額〇〇円)
18. exclusive_area - 専有面積 in m²
19. balcony_area - バルコニー面積 in m²
20. stations - Array of nearest stations [{name, line, walking_minutes}]
21. parking - 駐車場
22. pet_policy - ペット飼育 (可/不可)
23. corner_room - 角部屋 (角部屋/中住戶)

IMPORTANT NOTES:
- 権利形態 is usually labeled "所有権" or "借地権"
- 用途地域 is critical - find "第一種住居地域", "第二種住居地域", "準工業地域", "商業地域", etc.
- 構造 often includes RC造, SRC造, 木造, 鉄骨造
- 築年月 may be formatted as "2001年7月" or similar
- Extract ALL numbers with their units

Output Format:
Extract the information as structured JSON. If a field is not found, set it to null.

Example:
{
    "property_type": "マンション",
    "property_name": "〇〇マンション",
    "address": "東京都渋谷区...",
    "prefecture": "東京都",
    "city": "渋谷区",
    "land_rights": "所有権",
    "用途地域": "第一種住居地域",
    "build_year": 2001,
    "structure": "RC造",
    ...
}"""

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
