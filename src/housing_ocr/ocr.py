import base64
import json
import re
import requests
from pathlib import Path
from typing import Optional
import tomli
import time


VLLM_API_URL = "http://localhost:8000/v1/chat/completions"
VLLM_API_TIMEOUT = 300
MAX_RETRIES = 3
RETRY_DELAY = 5


def load_config() -> dict:
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    config_path = PROJECT_ROOT / "config.toml"
    if config_path.exists():
        with open(config_path, "rb") as f:
            return tomli.load(f)
    return {
        "openrouter": {"api_key": "", "base_url": "https://openrouter.ai/api/v1"},
        "models": {
            "default": "google/gemini-2.0-flash-exp:free",
            "available": [
                "google/gemini-2.0-flash-exp:free",
                "moonshotai/kimi-k2:free",
                "deepseek/deepseek-r1-0528:free",
                "qwen/qwen3-4b:free",
            ],
        },
    }


CONFIG = load_config()
OPENROUTER_API_URL = CONFIG["openrouter"]["base_url"] + "/chat/completions"
OPENROUTER_API_KEY = CONFIG["openrouter"]["api_key"]
DEFAULT_MODEL = CONFIG["models"]["default"]
AVAILABLE_MODELS = CONFIG["models"]["available"]
PROMPT = """请输出PDF图片中的布局信息，包括每个布局元素的边界框、类别以及边界框内的对应文本内容。

1. 边界框格式: [x1, y1, x2, y2]

2. 布局类别: 可能的类别有['Caption', 'Footnote', 'Formula', 'List-item', 'Page-footer', 'Page-header', 'Picture', 'Section-header', 'Table', 'Text', 'Title']。

3. 文本提取与格式化规则:
    - 图片(Picture): 对于'Picture'类别，文本字段应省略
    - 公式(Formula): 将其文本格式化为LaTeX
    - 表格(Table): 将其文本格式化为HTML
    - 其他所有类别(Text, Title等): 将其文本格式化为Markdown

4. 约束条件:
    - 输出文本必须是图片中的原始文本，不能翻译
    - 所有布局元素必须按人类阅读顺序排序

5. 最终输出: 整个输出必须是一个单一的JSON对象"""


def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def process_image(image_path: str, model: Optional[str] = None) -> str:
    base64_image = encode_image(image_path)

    payload = {
        "model": model or "rednote-hilab/dots.ocr",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    },
                ],
            }
        ],
        "max_tokens": 16384,
        "temperature": 0.1,
    }

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(
                VLLM_API_URL, json=payload, timeout=VLLM_API_TIMEOUT
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except requests.exceptions.ConnectionError as e:
            if attempt < MAX_RETRIES - 1:
                print(
                    f"OCR连接失败，{RETRY_DELAY}秒后重试 ({attempt + 1}/{MAX_RETRIES})..."
                )
                time.sleep(RETRY_DELAY)
            else:
                return f"OCR API错误: 无法连接到vLLM服务器 ({VLLM_API_URL})，请确认'just server'已启动"
        except requests.exceptions.Timeout as e:
            if attempt < MAX_RETRIES - 1:
                print(
                    f"OCR超时，{RETRY_DELAY}秒后重试 ({attempt + 1}/{MAX_RETRIES})..."
                )
                time.sleep(RETRY_DELAY)
            else:
                return f"OCR API错误: 请求超时"
        except requests.exceptions.RequestException as e:
            return f"OCR API错误: {e}"

    return f"OCR API错误: 未知错误"


def process_pdf(pdf_path: str) -> str:
    from pdf2image import convert_from_path
    import tempfile

    text_parts = []

    try:
        images = convert_from_path(pdf_path, dpi=200)

        for i, image in enumerate(images):
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                image.save(tmp.name, "JPEG")
                try:
                    page_text = process_image(tmp.name)
                    text_parts.append(f"--- 第 {i + 1} 页 ---\n{page_text}")
                except Exception as e:
                    text_parts.append(f"--- 第 {i + 1} 页 ---\n错误: {e}")
                finally:
                    Path(tmp.name).unlink()

        return "\n\n".join(text_parts)

    except Exception as e:
        return f"PDF处理错误: {e}"


def process_document(file_path: str) -> str:
    if not Path(file_path).exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    file_ext = Path(file_path).suffix.lower()

    if file_ext == ".pdf":
        return process_pdf(file_path)
    elif file_ext in [".jpg", ".jpeg", ".png"]:
        return process_image(file_path)
    else:
        return f"不支持的文件类型: {file_ext}"


def convert_japanese_units(text: str) -> str:
    text = re.sub(
        r"(\d+(?:\.\d+)?)\s*畳",
        lambda m: str(round(float(m.group(1)) * 1.62, 2)) + "m²",
        text,
    )
    text = re.sub(
        r"(\d+(?:\.\d+)?)\s*坪",
        lambda m: str(round(float(m.group(1)) * 3.3, 2)) + "m²",
        text,
    )
    return text


PROPERTY_EXTRACTION_PROMPT = """请从以下文本中提取房产的关键信息，并以JSON格式输出。

需要提取的字段包括：
- property_type: 房产类型（如：公寓、一户建、土地等）
- property_name: 房产名称
- room_number: 房间号
- address: 完整地址
- prefecture: 都道府県
- city: 区市町村
- town: 町名
- current_status: 现状（如：空置、已售、租赁中等）
- handover_date: 引渡日期
- is_renovated: 是否新装修（是/否）
- renovation_date: 装修结束日期
- year_built: 建成年份（整数年份）
- structure: 构造（如：钢筋混凝土、木结构、钢结构等）
- total_floors: 总楼层数（整数）
- floor_number: 所在楼层数（整数）
- room_layout: 房间布局（如：1LDK、2LDK、3LDK等）
- orientation: 朝向（如：南、东、西南等）
- price: 售价（整数，单位：万円）
- management_fee: 管理费（整数，单位：円/月）
- repair_fund: 修缮基金（整数，单位：円/月）
- exclusive_area: 专有面积（浮点数，单位：m²）
- land_area: 土地面积（浮点数，单位：m²）
- building_area: 建筑面积（浮点数，单位：m²）
- balcony_area: 阳台面积（浮点数，单位：m²）
- nearest_station: 最近车站名称
- nearest_line: 最近车站线路
- walking_time: 到最近车站徒步时长（整数，单位：分钟）
- multiple_stations: 多车站可用（是/否）
- has_parking: 是否有停车场（是/否）
- shopping_nearby: 周边购物设施
- pets_allowed: 是否可以养宠物（是/否）

注意事项：
1. 如果某字段在文本中没有对应信息，设为null
2. 数字字段只返回数字，不要包含单位
3. 售价单位是万円，管理费和修缮基金单位是円/月
4. 面积单位是m²（已将畳、坪等日本单位转换为m²）
5. 输出必须是有效的JSON格式

原始文本：
{}"""


def extract_property_info(text: str, model: Optional[str] = None) -> dict:
    if not OPENROUTER_API_KEY:
        print("警告: 未配置OpenRouter API Key，跳过房产信息抽取")
        return {}

    prompt = PROPERTY_EXTRACTION_PROMPT.format(text)

    payload = {
        "model": model or DEFAULT_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt}],
            }
        ],
        "max_tokens": 8192,
        "temperature": 0.1,
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            OPENROUTER_API_URL, json=payload, headers=headers, timeout=300
        )
        response.raise_for_status()
        result = response.json()
        content = result["choices"][0]["message"]["content"]

        json_match = re.search(r"\{[\s\S]*\}", content)
        if json_match:
            return json.loads(json_match.group())
        return {}
    except Exception as e:
        print(f"LLM提取错误: {e}")
        return {}
    except Exception as e:
        print(f"LLM提取错误: {e}")
        return {}
