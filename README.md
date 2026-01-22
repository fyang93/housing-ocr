# Housing OCR

日本房产文档智能解析系统 - 从 PDF/图片自动提取结构化数据

## 快速开始

```bash
# 1. 安装依赖
just sync

# 2. 配置
cp config.example.toml config.toml
# 编辑 config.toml：
#   - 设置 OpenRouter API Key
#   - 生成安全访问令牌：just token（自动更新 config.toml）

# 3. 启动服务 (两个终端)
# 终端 1: 启动 OCR 服务
just ocr

# 终端 2: 选择以下任一模式
# 开发模式（推荐）：前后端同时运行，热重载
just dev    # 访问 http://localhost:8080?token=your-access-token

# 生产模式：先构建前端，再启动后端（使用静态文件）
just build && just run    # 访问 http://localhost:8080?token=your-access-token
```

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
host = "0.0.0.0"
port = 8080  # 生产模式端口（just run）
upload_dir = "./uploads"
db_path = "./data.db"
access_token = "your-secret-token-here"  # 设置为强密码
```

**访问方式**：
- 所有请求必须在 URL 中包含 `?token=your-access-token`
- 例如：`http://localhost:8080?token=your-secret-token-here`
- 没有 token 的请求将返回空响应（防止扫描）

**端口说明**：
- `just dev`：前端 8080，后端 8081（开发模式）
- `just run`：8080（生产模式，前后端统一端口）

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
├── data/                   # 数据目录
├── config.example.toml     # 配置示例
├── justfile                # 命令行任务
└── pyproject.toml
```

## 命令

```bash
just default     # 显示所有可用命令
just sync        # 安装 Python 依赖
just token       # 生成安全访问令牌（自动更新 config.toml）
just ocr         # 启动 vLLM OCR 模型服务（需要 GPU）
just run         # 启动后端 API 服务（生产模式，自动使用已构建的前端静态文件，端口 8080）
just build       # 构建前端为静态文件（部署前使用）
just dev         # 启动完整开发环境：前端开发服务器 (http://localhost:8080) + 后端 (http://localhost:8081)
```

### 安全令牌生成

运行 `just token` 命令生成加密安全的访问令牌：

```bash
just token
```

**安全特性**：
- 使用 Python `secrets` 模块（加密安全）
- 8 字符长度（包含大小写字母、数字和特殊字符）
- 不可预测，抵抗字典攻击和暴力破解
- 自动更新 `config.toml`
- 显示完整的访问 URL（带 token）

**示例输出**：
```
Generated token (8 characters):
  aB3!xK9p
```

## License

MIT
