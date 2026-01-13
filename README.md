# Housing OCR

日本房产文档智能解析系统 - 从 PDF/图片自动提取结构化数据

## 快速开始

```bash
# 1. 安装依赖
just sync

# 2. 配置 API Key
cp config.example.toml config.toml
# 编辑 config.toml，设置 OpenRouter API Key

# 3. 启动服务 (两个终端)
just ocr    # OCR 服务
just run    # Web 应用
```

访问 http://localhost:8080

## 功能特性

- **多格式支持**：PDF、PNG、JPG
- **自动提取**：价格、面积、地址、车站、房间布局等 20+ 属性
- **智能重试**：OCR/LLM 失败自动切换模型重试
- **可视化编辑**：文档预览 + OCR 文本 + 属性编辑
- **筛选收藏**：按价格、面积、类型等多维度筛选
- **车站时长**：记录到常用位置的通勤时间

## 架构

```
上传文档 → SQLite → OCR (vLLM) → LLM (OpenRouter) → 结构化数据
                ↓
          后台异步处理
```

## 配置

`config.toml`:
```toml
[llm]
api_key = "sk-or-..."
base_url = "https://openrouter.ai/api/v1"
models = ["google/gemini-2.0-flash-exp:free"]

[ocr]
endpoint = "http://localhost:8000/v1"
model = "rednote-hilab/dots.ocr"

[app]
port = 8080
upload_dir = "./uploads"
db_path = "./data.db"
```

## 提取的属性

| 类别 | 属性 |
|------|------|
| 基本信息 | 类型、名称、地址、都道府县、区市町村 |
| 建筑信息 | 建成年份、构造、总楼层、所在楼层、朝向 |
| 房间布局 | 布局类型、专有面积、阳台面积 |
| 价格信息 | 售价、管理费、修缮积立金 |
| 交通配套 | 最近车站、步行时长、停车场、宠物政策 |

单位自动转换：畳 (×1.62) → m²，坪 (×3.3) → m²

## 技术栈

- **Python 3.12** + **uv**
- **FastAPI** (Web框架)
- **SQLite** (数据库)
- **vLLM** (OCR推理)
- **OpenRouter** (LLM API)
- **Vue 3 + TypeScript + Vite** (前端)
- **TailwindCSS 4** (UI样式)
- **Bun** (前端包管理)

## 项目结构

```
housing-ocr/
├── src/
│   ├── app.py              # FastAPI 应用和路由
│   ├── models.py           # 数据库模型
│   ├── ocr.py              # OCR 客户端
│   ├── llm.py              # LLM 提取逻辑
│   └── processor.py        # 后台处理队列
├── frontend/               # Vue 3 前端项目
│   ├── src/                # 前端源代码
│   ├── dist/               # 构建产物
│   ├── package.json
│   └── vite.config.ts
├── config.example.toml     # 配置示例
├── justfile                # 命令行任务
└── pyproject.toml
```

## 命令

```bash
just sync    # 安装 Python 依赖
just ocr     # 启动 OCR 服务
just run     # 启动 Web 服务
just build   # 构建前端
just dev     # 同时启动前后端开发服务器
```

## License

MIT
