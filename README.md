# Housing OCR

日本房产文档智能解析系统 - 从 PDF/图片到结构化数据,全自动。

---

## 核心理念

**简单即美**: 上传文档 → 后台处理 → 获取结构化数据。无需复杂配置,开箱即用。

## 技术栈

- **Python 3.12** + **uv** (依赖管理)
- **FastAPI** (Web框架)
- **SQLite** (数据库,零配置)
- **VLLM** (OCR推理服务)
- **OpenRouter** (LLM API)
- **TailwindCSS** (中文UI)

## 快速开始

```bash
# 1. 同步依赖
just sync

# 2. 配置(仅需设置API key)
just setup

# 3. 在 tmux/zellij 中分别启动服务
just ocr    # 窗格1: OCR服务
just run    # 窗格2: Web应用
```

访问 http://localhost:8080 开始使用。

## 架构设计

```
上传文档 → SQLite队列 → OCR → LLM → 结构化数据
                ↓
            后台轮询处理(无需额外队列服务)
```

**设计决策:**
- ❌ **不用** Celery/Redis - SQLite + 轮询足够,减少依赖
- ❌ **不用** 复杂ORM - 原生SQL更清晰可控
- ✅ **单文件配置** - config.toml 包含所有设置
- ✅ **异步处理** - FastAPI 后台任务处理文档
- ✅ **自动重试** - 失败自动切换模型,无需人工干预

## 配置文件

`config.toml`:
```toml
[llm]
api_key = "your_openrouter_api_key"
models = [
    "google/gemini-2.0-flash-exp:free",
    "deepseek/deepseek-r1-0528:free",
    "qwen/qwen3-4b:free"
]

[ocr]
endpoint = "http://localhost:8000/v1"

[app]
port = 8080
upload_dir = "./uploads"
db_path = "./data.db"
```

## 项目结构

```
housing-ocr/
├── justfile              # 任务命令
├── pyproject.toml        # uv项目配置
├── config.toml           # 应用配置
├── app.py                # 主程序(FastAPI应用)
├── models.py             # 数据模型
├── ocr.py                # OCR客户端
├── llm.py                # LLM提取逻辑
├── processor.py          # 后台处理器
├── templates/
│   └── index.html        # 中文UI
└── static/
    └── style.css         # TailwindCSS
```

## 核心功能

### 1. 文档处理流程
```python
# 简化的处理逻辑
async def process_document(doc_id):
    # OCR提取文本
    text = await ocr_client.extract(doc_path)
    
    # LLM提取属性(自动重试+模型切换)
    for model in config.models:
        try:
            properties = await llm_extract(text, model)
            break
        except:
            continue  # 自动切换下一个模型
    
    # 保存到数据库
    db.save(doc_id, properties)
```

### 2. 提取的房产属性

| 类别 | 属性 |
|------|------|
| **基本** | 类型、名称、房间号 |
| **位置** | 地址、都道府県、区市町村 |
| **权属** | 土地权利、现状、交房日期 |
| **建筑** | 建成年份、构造、楼层(总/所在) |
| **布局** | 房间布局(2LDK)、朝向 |
| **价格** | 售价(万円)、管理费、修缮金 |
| **面积** | 专有/土地/建筑/阳台面积(m²) |
| **交通** | 最近车站、线路、步行时长 |
| **配套** | 停车场、宠物政策 |

**单位自动转换**: 畳(1.62m²)、坪(3.3m²) → 公制

### 3. 中文UI界面

```
┌─────────────────────────────────────────┐
│ 房产OCR │ [模型配置] ... [上传文档]    │
├─────────────────────────────────────────┤
│ 筛选: [类型] [价格] [位置] [面积]        │
├─────────────────────────────────────────┤
│ ┌────────┐ ┌────────┐ ┌────────┐       │
│ │ 港区   │ │处理中..│ │新宿区  │       │
│ │5000万  │ │ ⏳     │ │3800万  │       │
│ │2LDK    │ │        │ │1LDK    │       │
│ └────────┘ └────────┘ └────────┘       │
└─────────────────────────────────────────┘
```

**点击卡片 → 弹窗显示:**
- 左侧: PDF/图片预览
- 右侧: OCR文本 + 可编辑属性表单

## Justfile 命令

```make
just sync       # 同步依赖(uv sync)
just setup      # 创建配置文件
just ocr        # 启动OCR服务
just run        # 启动Web应用
just clean      # 清理数据
```

完整 `justfile`:
```make
# 显示所有可用命令
default:
    @just --list

# 同步项目依赖
sync:
    uv sync

# 创建配置文件
setup:
    @test -f config.toml || cp config.example.toml config.toml
    @mkdir -p uploads
    @echo "✓ 配置完成,请编辑 config.toml 设置API key"

# 启动OCR服务
ocr:
    uv run vllm serve rednote-hilab/dots.ocr \
        --trust-remote-code \
        --async-scheduling \
        --gpu-memory-utilization 0.95

# 启动Web应用
run:
    uv run uvicorn app:app --reload --port 8080

# 清理数据和临时文件
clean:
    rm -rf uploads/* data.db __pycache__
    @echo "✓ 已清理数据"
```

## 实现要点

### 1. 后台处理器(无需额外队列)
```python
# processor.py - 轮询处理未完成的文档
async def background_processor():
    while True:
        pending = db.get_pending_documents()
        for doc in pending:
            await process_document(doc.id)
        await asyncio.sleep(5)  # 每5秒检查一次

# app.py - 启动时运行
@app.on_event("startup")
async def startup():
    asyncio.create_task(background_processor())
```

### 2. LLM提取逻辑(自动重试)
```python
# llm.py
async def extract_properties(text: str) -> dict:
    prompt = f"""从以下文本提取房产信息,返回JSON:
    {text}
    
    需要提取: 房产类型、售价、面积、地址...
    单位转换: 畳→m²(×1.62), 坪→m²(×3.3)
    """
    
    for model in config.models:
        try:
            response = await openrouter_call(prompt, model)
            return parse_json(response)
        except Exception as e:
            logger.warning(f"{model} 失败: {e}")
            continue
    
    raise Exception("所有模型均失败")
```

### 3. 数据库设计(极简)
```sql
-- 只需一张表
CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    filename TEXT,
    upload_time DATETIME,
    ocr_status TEXT,      -- pending/done/failed
    ocr_text TEXT,
    llm_status TEXT,      -- pending/done/failed
    properties JSON,      -- 提取的所有属性
    retry_count INTEGER
);
```

## 开发路线

### Phase 1: 核心流程 (1-2天)
- [x] FastAPI应用框架
- [x] 文件上传接口
- [x] SQLite数据库
- [x] OCR客户端集成
- [x] 后台处理器

### Phase 2: LLM集成 (1天)
- [x] OpenRouter客户端
- [x] 属性提取Prompt工程
- [x] 自动重试+模型切换

### Phase 3: UI界面 (1-2天)
- [x] TailwindCSS布局
- [x] 文档上传组件
- [x] 卡片列表+筛选
- [x] 详情弹窗+编辑

### Phase 4: 优化 (可选)
- [ ] 批量处理优化
- [ ] 导出Excel功能
- [ ] 数据统计图表

## 为什么这样设计?

### 简化决策

| 传统方案 | 本方案 | 理由 |
|---------|--------|------|
| Celery + Redis | SQLite轮询 | 文档处理非高并发场景,轮询足够 |
| PostgreSQL | SQLite | 单用户/小团队,SQLite性能充足 |
| 复杂ORM | 原生SQL | 数据模型简单,ORM是过度设计 |
| 微服务 | 单体应用 | 功能聚焦,单体更易维护 |
| Docker部署 | 本地运行 | 开发阶段,避免环境复杂度 |

### 关键原则
1. **YAGNI** (You Aren't Gonna Need It) - 只实现必需功能
2. **依赖最小化** - 每个依赖都是负担
3. **配置优于代码** - 一个toml文件搞定所有配置
4. **失败自愈** - 自动重试比复杂监控更实用

## FAQ

**Q: 为什么不用Celery?**  
A: 房产文档处理是低频任务,SQLite + 后台轮询足够。Celery需要Redis/RabbitMQ,增加运维复杂度。

**Q: SQLite能处理多少文档?**  
A: 百万级别无压力。如需扩展,替换为PostgreSQL只需改一行配置。

**Q: 并发处理怎么办?**  
A: 后台处理器可配置并发数,使用asyncio.Semaphore控制。

**Q: 如何备份数据?**  
A: `cp data.db backup.db` - SQLite备份就是复制文件。

---

**设计哲学**: 在90%的场景下,简单方案比复杂架构更好。先让它跑起来,真正需要时再优化。