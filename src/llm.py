import httpx
from typing import Dict, Any, Optional
import json
import time
import re

ERA_START_YEARS = {
    "明治": 1868,
    "大正": 1912,
    "昭和": 1926,
    "平成": 1989,
    "令和": 2019,
}

ERA_PATTERNS = [
    (r"令和(\d+)年?", 2019),
    (r"平成(\d+)年?", 1989),
    (r"昭和(\d+)年?", 1926),
    (r"大正(\d+)年?", 1912),
    (r"明治(\d+)年?", 1867),
]


def convert_japanese_era_to_western(era_text: str) -> str:
    """将日本年号转换为西历年"""
    if not era_text:
        return era_text

    for pattern, base_year in ERA_PATTERNS:
        match = re.search(pattern, era_text)
        if match:
            era_year = int(match.group(1))
            western_year = base_year + era_year - 1
            return str(western_year)

    return era_text


def _convert_era_in_properties(properties: Dict[str, Any]) -> Dict[str, Any]:
    """转换属性中的日本年号为西历年"""
    if "build_year" in properties and properties["build_year"]:
        properties["build_year"] = convert_japanese_era_to_western(
            str(properties["build_year"])
        )
    return properties


class LLMExtractor:
    def __init__(
        self, api_key: str, base_url: str, models: list, update_config_callback=None
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.models = models
        self.update_config_callback = update_config_callback
        self.client = httpx.Client(timeout=120.0)
        self.rate_limit_cooldown = 60
        self.model_429_times = {}

    def _extract_json(self, text: str) -> dict:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            json_str = text[start:end]
            return json.loads(json_str)
        raise ValueError("无法从响应中提取JSON")

    def extract_properties(
        self, ocr_text: str, doc_id: Optional[int] = None
    ) -> Dict[str, Any]:
        doc_tag = f"[ID:{doc_id}]" if doc_id else ""
        print(f"{doc_tag} LLM提取中... ({len(ocr_text)} 字符)")
        if not self.models:
            raise Exception(f"{doc_tag} 没有可用的模型，请在模型管理中添加模型")

        prompt = f"""Extract structured information from following Japanese real estate document.

Text content:
{ocr_text}

Fields to extract:
1. property_type: Property type (マンション/一戸建て/土地 etc.)
2. property_name: Property name
3. address: Full address including room number
4. prefecture: Prefecture (東京都/大阪府 etc.)
5. city: City/District (渋谷区/大阪市 etc.)
6. land_rights: Land rights (所有権/借地権 etc.)
7. current_status: Current status (空室/居住中 etc.)
8. handover_date: Handover date
9. build_year: Year built (Western calendar, e.g., 2015)
10. structure: Structure (RC造/木造/S造 etc.)
11. total_floors: Total floors
12. floor_number: Floor number
13. room_layout: Room layout (1LDK/2LDK/3LDK etc.)
14. orientation: Orientation (南/北/東/西 etc.)
15. price: Price in 万円 (e.g., 5000)
16. management_fee: Monthly management fee in 円
17. repair_fee: Monthly repair fund in 円
18. exclusive_area: Exclusive area in m²
19. balcony_area: Balcony area in m² (if available)
20. stations: Array of all nearest stations with WALKING distance only. Each station object contains: name (station name), lines (array of train line names), walking_minutes (walking time in minutes). If same station has multiple lines, combine them into ONE station object with multiple lines in the array.
21. parking: Parking availability
22. pet_policy: Pet policy
23. corner_room: Whether it's a corner room (角部屋). Set to null if not mentioned

Important:
- Convert units: 畳→m²(×1.62), 坪→m²(×3.3)
- Set null if field is not found
- **stations: ONLY include stations with WALKING distance (徒歩). EXCLUDE any stations with 直通/乗換/バス/電車 or other non-walking transport methods**
- For stations, look for keywords like "徒歩〇分" or "歩〇分". Common patterns: "駅名 徒歩5分", "〇〇駅 歩5分"
- If distance is described as "直通5分", "乗換5分", "バス5分" etc., DO NOT include it in stations array
- **CRITICAL: If the same station appears with multiple train lines, merge them into ONE station object with lines as an array. Do NOT create duplicate station entries.**
- stations should be an array of objects with lines as array, e.g., [{{"name": "渋谷", "lines": ["山手線", "銀座線", "半蔵門線"], "walking_minutes": 5}}]
- Return ONLY JSON, no other text
- Ensure valid JSON format

Example response:
{{
    "property_type": "マンション",
    "property_name": "〇〇コーポ",
    "address": "東京都渋谷区円山町28-14 305",
    "price": 5800,
    "exclusive_area": 65.8,
    "room_layout": "2LDK",
    "build_year": 2018,
    "stations": [
        {{"name": "渋谷", "lines": ["山手線", "銀座線", "半蔵門線"], "walking_minutes": 5}},
        {{"name": "表参道", "lines": ["銀座線", "千代田線"], "walking_minutes": 8}},
        {{"name": "原宿", "lines": ["山手線"], "walking_minutes": 10}}
    ],
    "parking": "空無 (月額23,000円/台)"
}}

Example of what NOT to include in stations:
- "池袋 直通5分" ❌ (this is direct train connection, not walking)
- "新宿 バス10分" ❌ (this is bus, not walking)
- "渋谷 乗換5分" ❌ (this is transfer time, not walking)
- "表参道 徒歩8分" ✅ (this is walking distance, INCLUDE this)

Example of correct station merging:
Input text mentions:
- "渋谷駅(山手線) 徒歩5分"
- "渋谷駅(銀座線) 徒歩5分"
- "渋谷駅(半蔵門線) 徒歩5分"

Correct output:
{{"name": "渋谷", "lines": ["山手線", "銀座線", "半蔵門線"], "walking_minutes": 5}}

Incorrect output (DO NOT do this):
[
    {{"name": "渋谷", "lines": ["山手線"], "walking_minutes": 5}},
    {{"name": "渋谷", "lines": ["銀座線"], "walking_minutes": 5}},
    {{"name": "渋谷", "lines": ["半蔵門線"], "walking_minutes": 5}}
]"""

        for model in self.models[:]:
            if model in self.model_429_times:
                last_429 = self.model_429_times[model]
                if time.time() - last_429 < self.rate_limit_cooldown:
                    remaining = int(self.rate_limit_cooldown - (time.time() - last_429))
                    print(f"模型 {model} 冷却中，剩余 {remaining} 秒，跳过...")
                    continue

            try:
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 4096,
                }

                response = self.client.post(
                    self.base_url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "HTTP-Referer": "http://localhost:8080",
                        "X-Title": "Housing OCR",
                    },
                )
                response.raise_for_status()
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                properties = self._extract_json(content)
                properties["_extracted_by_model"] = model
                properties = _convert_era_in_properties(properties)

                print(f"{doc_tag} 模型 {model} 返回:")
                print(f"  {json.dumps(properties, ensure_ascii=False, indent=2)}")

                meaningful_count = sum(
                    1
                    for v in properties.values()
                    if v is not None
                    and v != ""
                    and not (isinstance(v, str) and v.startswith("_"))
                )
                if meaningful_count < 3:
                    print(
                        f"{doc_tag} 有效字段不足 ({meaningful_count}个)，尝试下一个模型..."
                    )
                    continue

                print(f"{doc_tag} 提取成功")
                return properties
            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code if hasattr(e, "response") else None
                if status_code == 429:
                    print(f"{doc_tag} 模型 {model} 触发速率限制，记录冷却时间...")
                    self.model_429_times[model] = time.time()
                    continue
                else:
                    print(f"{doc_tag} 模型 {model} HTTP错误 {status_code}: {str(e)}")
                    continue
            except ValueError as e:
                print(f"{doc_tag} 模型 {model} JSON解析失败: {str(e)}")
                continue
            except Exception as e:
                print(f"{doc_tag} 模型 {model} 提取失败: {str(e)}")
                continue

        raise Exception(f"{doc_tag} 所有模型均失败，已尝试: {', '.join(self.models)}")

    def remove_failed_model(self, model_name: str):
        """移除失败的模型"""
        if model_name in self.models:
            self.models.remove(model_name)
            print(f"已移除失败模型: {model_name}")
            if self.update_config_callback:
                self.update_config_callback(list(self.models))

    def close(self):
        self.client.close()
