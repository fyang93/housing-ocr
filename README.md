# Housing OCR System

房产文档 OCR 系统，使用 dots.ocr 从 PDF、JPG 和 PNG 文件中提取文本，并使用 LLM 抽取房产关键信息。

## 功能特点

- 上传 PDF、JPG、PNG 文件进行 OCR 识别
- 使用 dots.ocr 模型进行高精度文本提取
- 使用 OpenRouter API (Gemini 2.0 Flash、Kimi、DeepSeek R1、Qwen 3) 抽取房产关键信息
- 固定导航栏，支持模型切换和文件上传
- 房产筛选功能（类型、地区、价格）
- 点击卡片查看详情（文档预览、OCR 文本、LLM 抽取信息）
- 日本单位自动转换（畳→1.62m²、坪→3.3m²）
- 基于哈希的文件名存储
- SQLite 数据库文档跟踪

## 安装与配置

### 1. 安装依赖

```bash
uv sync
```

### 2. 配置 OpenRouter API（可选但推荐）

编辑 `config.toml` 文件，添加你的 OpenRouter API Key：

```toml
[openrouter]
api_key = "你的OpenRouter API Key"
```

访问 https://openrouter.ai/ 获取免费的 API Key。

**注意**：如果未配置 API Key，OCR 功能仍可正常工作，但将跳过房产信息抽取。

### 3. 启动服务

```bash
# 启动 vLLM 服务器（用于 OCR）
just server

# 在另一个终端启动 Web 应用
just run
```

### 4. 测试服务

```bash
# 测试 vLLM 连接
uv run python scripts/test_vllm_connection.py

# 测试 OCR 处理
uv run python scripts/test_ocr.py

# 测试 OpenRouter 连接（需要先配置 API Key）
uv run python scripts/test_openrouter.py
```

**注意**：OCR 处理具有自动重试机制（最多3次，每次间隔5秒），如果 vLLM 服务器暂时不可用，会自动重试。

## 使用说明

1. 打开浏览器访问 http://localhost:5000
2. 在导航栏选择 LLM 模型（默认为 Gemini 2.0 Flash）
3. 点击"上传文件"按钮，选择房产文档
4. 系统自动进行 OCR 识别和房产信息抽取
5. 使用筛选器查找特定房产
6. 点击房产卡片查看详情（文档预览、OCR 文本、LLM 抽取的完整信息）

## 可用 LLM 模型

- **google/gemini-2.0-flash-exp:free** (默认) - Gemini 2.0 Flash
- **moonshotai/kimi-k2:free** - Kimi K2
- **deepseek/deepseek-r1-0528:free** - DeepSeek R1
- **qwen/qwen3-4b:free** - Qwen 3 4B

所有模型均为免费版。

## 房产信息抽取字段

系统自动抽取以下 29 个房产字段：
- 房产类型、名称、房间号
- 地址（都道府県、区市町村、町名）
- 现状、引渡日期、装修信息
- 建成年份、构造、楼层信息
- 房间布局、朝向
- 价格（万元）、管理费、修缮基金
- 各类面积（专有、土地、建筑、阳台）
- 交通信息（最近车站、线路、徒步时间）
- 停车场、购物、宠物政策等

详细说明请查看 [OPENROUTER_SETUP.md](OPENROUTER_SETUP.md)。
