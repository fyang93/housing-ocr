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

## 安全

应用包含完整的安全功能：

### IP地理位置过滤（可配置）
- 使用MaxMind GeoIP2数据库检测客户端IP所在国家
- 可配置允许的国家列表（ISO 3166-1 alpha-2格式）
- 下载地址：https://dev.maxmind.com/geoip/geolite2-free-geolocation-data
- 放置在：`data/` 目录
- 或在 `config.toml` 中配置自定义路径和允许的国家
- 如果数据库不可用，则允许所有IP（安全回退）

**配置示例**：
```toml
[security]
# 允许的国家代码列表（ISO 3166-1 alpha-2）
allowed_countries = ["JP"]  # 仅日本
allowed_countries = ["JP", "US", "CN", "KR"]  # 多个国家
allowed_countries = []  # 允许所有国家（禁用地理过滤）
allowed_countries = ["*"]  # 允许所有国家
```

### 路径遍历防护
- 检测并阻止包含路径遍历模式的请求（`../`、`..\\`、URL编码变体）
- 记录可疑尝试用于黑名单
- 自动对具有可疑活动的IP进行黑名单处理

### IP黑名单
- 手动IP黑名单
- 超过可疑活动阈值后自动封禁（默认：3次尝试）
- 可配置封禁时长（默认：24小时）
- 内存持久化存储

### 速率限制
- 每IP每分钟限制请求数（默认：60请求/分钟）
- 内存滑动窗口算法
- 超过限制时返回HTTP 429

### 安全头
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- X-XSS-Protection: 1; mode=block
- Referrer-Policy: strict-origin-when-cross-origin
- Content-Security-Policy: 对资源加载的严格控制
- Strict-Transport-Security (HSTS)：强制HTTPS（使用HTTPS时）
- Permissions-Policy：控制浏览器功能

### 配置

所有安全功能可在 `config.toml` 中配置：

```toml
[security]
# Enable security features
enable_security_headers = true
enable_hsts = true
enable_csp = true

# IP geolocation filtering
enable_ip_geolocation = true
geoip_database_path = "./data/GeoLite2-Country.mmdb"

# Allowed country codes (ISO 3166-1 alpha-2)
# Examples:
#   ["JP"] - Japan only
#   ["JP", "US", "CN", "KR"] - Multiple countries
#   [] or ["*"] - Allow all countries (disable geolocation)
allowed_countries = ["JP"]

# Path traversal protection
enable_path_traversal_protection = true

# IP blacklist
enable_ip_blacklist = true
auto_ban_suspicious_ips = true
auto_ban_threshold = 3
ban_duration = 86400

# Rate limiting
enable_rate_limiting = true
requests_per_minute = 60

# CORS
enable_cors = true
allow_origins = ["*"]
allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
allow_headers = ["*"]
```

生产环境请将 `allow_origins` 改为特定域名而非 `"*"`。
