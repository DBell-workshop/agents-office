# 系统架构与数据架构设计

## 文档信息

| 项目     | 内容                             |
| -------- | -------------------------------- |
| 项目名称 | 电商 AI 实验室                   |
| 文档类型 | 系统架构设计                     |
| 适用阶段 | 一期原型 (Phase 1)               |
| 创建日期 | 2026-03-12                       |
| 设计原则 | 实验室原型优先，数据层必须做对   |

---

## 1. 数据库选型

### 1.1 候选方案对比

| 维度               | PostgreSQL                       | SQLite                          | MongoDB                         |
| ------------------ | -------------------------------- | ------------------------------- | ------------------------------- |
| JSON 支持          | 原生 `jsonb`，支持索引和查询     | JSON1 扩展，功能有限            | 原生文档模型                    |
| Docker 部署        | 官方镜像，一行启动               | 嵌入式，无需容器                | 官方镜像，一行启动              |
| Python 生态        | SQLAlchemy + asyncpg 成熟        | 内置 sqlite3，aiosqlite 可用    | motor / pymongo                 |
| 并发写入           | MVCC，支持高并发                 | 单写者锁，后台任务写入有瓶颈   | 写入性能好                      |
| 全文检索           | 内置 `tsvector`                  | FTS5 扩展                       | Atlas Search（本地不支持）      |
| 迁移到生产         | 直接用，RDS/Aurora 兼容          | 需要全量迁移到其他数据库        | 需要独立运维 MongoDB 集群       |
| 关系建模           | 强项，外键、约束完备             | 支持，但无严格类型              | 弱项，嵌套文档代替关系          |
| 事务支持           | 完整 ACID                        | 文件级锁                        | 多文档事务（4.0+）              |
| ORM 支持           | SQLAlchemy 完整支持              | SQLAlchemy 支持                 | ODM 生态较弱                    |

### 1.2 推荐方案：PostgreSQL

**理由：**

1. **JSON 与关系的平衡**：Agent 输出是结构化 JSON（评分报告、比价结果、事件日志），PostgreSQL 的 `jsonb` 类型可以直接存储并建立 GIN 索引查询，同时保持课程、任务、用户等实体的关系建模能力。这比纯文档数据库多了关系约束，比 SQLite 多了并发能力。

2. **并发写入无瓶颈**：当前架构使用 `BackgroundTasks` 执行异步工作流，多个后台任务会并发写入任务状态。SQLite 的单写者锁在这个场景下会成为瓶颈。PostgreSQL 的 MVCC 完全没有这个问题。

3. **零成本生产迁移**：原型阶段 Docker 跑 PostgreSQL，生产直接迁移到 RDS / Aurora PostgreSQL，Schema 和查询完全不变。SQLite 则需要全量重写数据层。

4. **全链路追踪友好**：`trace_id` 索引、时间范围查询、JSON 路径查询在 PostgreSQL 中都是一等公民。审计日志和事件日志的查询需求天然适合关系型数据库。

5. **开发效率**：SQLAlchemy 2.0 + Alembic 提供成熟的 ORM 和迁移工具链，Pydantic 模型可以一对一映射到 SQLAlchemy 模型。

**不选 SQLite 的原因**：后台任务并发写入会遇到锁竞争；未来 WebSocket 事件流写入量更大，SQLite 扛不住。

**不选 MongoDB 的原因**：当前数据模型有明确的关系结构（课程->尝试->评分报告、比价任务->采集结果->标准化报价）；团队后续生产环境更可能用 RDS 而非自运维 MongoDB。

### 1.3 Python 技术栈

```
PostgreSQL 16
  + SQLAlchemy 2.0 (async, asyncpg driver)
  + Alembic (数据库迁移)
  + Pydantic 2.x (现有模型保持不变，新增 ORM 映射层)
```

新增依赖：

```txt
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
alembic==1.14.1
```

---

## 2. Docker Compose 设计

### 2.1 服务清单

```yaml
# docker-compose.yml
version: "3.9"

services:
  # ---- 数据层 ----
  postgres:
    image: postgres:16-alpine
    container_name: ecom_ai_db
    restart: unless-stopped
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: ecom_ai
      POSTGRES_PASSWORD: ecom_ai_dev
      POSTGRES_DB: ecom_ai
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./scripts/init_db.sql:/docker-entrypoint-initdb.d/01_init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ecom_ai"]
      interval: 5s
      timeout: 3s
      retries: 5

  # ---- 应用层 ----
  api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: ecom_ai_api
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://ecom_ai:ecom_ai_dev@postgres:5432/ecom_ai
      DATABASE_URL_SYNC: postgresql://ecom_ai:ecom_ai_dev@postgres:5432/ecom_ai
      OPENCLAW_MODE: mock
      OPENCLAW_REMOTE_BASE_URL: http://127.0.0.1:9001
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - ./app:/app/app:ro
      - ./scripts:/app/scripts:ro

  # ---- 缓存层（二期可选，先预留位置）----
  # redis:
  #   image: redis:7-alpine
  #   ports:
  #     - "6379:6379"

volumes:
  pgdata:
    driver: local
```

### 2.2 端口映射总览

| 服务       | 容器端口 | 宿主机端口 | 用途                     |
| ---------- | -------- | ---------- | ------------------------ |
| PostgreSQL | 5432     | 5432       | 数据库连接               |
| API        | 8000     | 8000       | FastAPI 后端             |
| (Redis)    | 6379     | 6379       | 二期：WebSocket pub/sub  |

### 2.3 卷挂载说明

| 卷名称    | 挂载路径                         | 用途                             |
| --------- | -------------------------------- | -------------------------------- |
| `pgdata`  | `/var/lib/postgresql/data`       | PostgreSQL 数据持久化            |
| `init_db` | `/docker-entrypoint-initdb.d/`   | 初始化 SQL（建表、种子数据）     |
| `app`     | `/app/app` (只读)                | 开发时热更新代码                 |

### 2.4 环境变量清单

| 变量名                     | 默认值                              | 说明                   |
| -------------------------- | ----------------------------------- | ---------------------- |
| `DATABASE_URL`             | `postgresql+asyncpg://...`          | 异步连接串             |
| `DATABASE_URL_SYNC`        | `postgresql://...`                  | 同步连接串（Alembic）  |
| `OPENCLAW_MODE`            | `mock`                              | 采集适配模式           |
| `OPENCLAW_REMOTE_BASE_URL` | `http://127.0.0.1:9001`            | 远程 OpenClaw 地址     |
| `OPENCLAW_TIMEOUT_SECONDS` | `15`                                | 采集超时               |

---

## 3. 数据库 Schema 设计

### 3.1 ER 关系图

```mermaid
erDiagram
    products ||--o{ courses : "一个商品可有多个课程"
    courses ||--o{ training_attempts : "一个课程可有多次练习"
    courses ||--o{ tasks : "课程生成内容创建任务"
    training_attempts ||--o{ tasks : "练习评分创建任务"
    comparison_tasks ||--o{ tasks : "比价执行创建任务"
    products ||--o{ comparison_tasks : "一个商品可有多个比价任务"

    products {
        text product_id PK
        text sku
        text name
        text category
        text brand
        jsonb attributes
        text source_platform
        text source_url
        jsonb raw_data
        timestamptz created_at
        timestamptz updated_at
    }

    courses {
        text course_id PK
        text product_id FK
        text product_name
        text objective
        jsonb required_points
        jsonb product_facts
        int content_version
        jsonb latest_content
        timestamptz created_at
        timestamptz updated_at
    }

    training_attempts {
        text attempt_id PK
        text course_id FK
        text user_id
        text audio_url
        text mock_transcript
        timestamptz created_at
    }

    comparison_tasks {
        text comparison_task_id PK
        text source_product_id FK
        text source_product_name
        jsonb targets
        timestamptz created_at
    }

    tasks {
        text task_id PK
        text trace_id
        text task_type
        text status
        jsonb input
        jsonb output
        text error
        timestamptz created_at
        timestamptz updated_at
    }

    agent_events {
        bigint event_id PK
        text trace_id
        text agent_name
        text event_type
        jsonb payload
        timestamptz created_at
    }

    audit_logs {
        bigint log_id PK
        text trace_id
        text action
        text actor
        text entity_type
        text entity_id
        jsonb before_state
        jsonb after_state
        jsonb metadata
        timestamptz created_at
    }
```

### 3.2 完整建表 DDL

```sql
-- ============================================================
-- 文件: scripts/init_db.sql
-- 用途: PostgreSQL 初始化脚本，Docker 启动时自动执行
-- ============================================================

-- 启用 UUID 扩展（备用，当前使用应用层 make_id）
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- 1. 商品数据表
-- 用于导入 Best Buy Open Data 和 Amazon Reviews 测试数据
-- ============================================================
CREATE TABLE IF NOT EXISTS products (
    product_id    TEXT PRIMARY KEY,               -- make_id("prod") 或外部 SKU
    sku           TEXT,                            -- 外部 SKU 编号
    name          TEXT NOT NULL,                   -- 商品名称
    category      TEXT,                            -- 类目
    brand         TEXT,                            -- 品牌
    attributes    JSONB NOT NULL DEFAULT '{}',     -- 商品属性（规格参数、卖点等）
    source_platform TEXT,                          -- 数据来源平台（bestbuy / amazon）
    source_url    TEXT,                            -- 原始数据链接
    raw_data      JSONB NOT NULL DEFAULT '{}',     -- 原始导入数据完整保留
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_products_category ON products (category);
CREATE INDEX IF NOT EXISTS idx_products_brand ON products (brand);
CREATE INDEX IF NOT EXISTS idx_products_source ON products (source_platform);
-- GIN 索引支持 JSON 属性查询
CREATE INDEX IF NOT EXISTS idx_products_attributes ON products USING GIN (attributes);

COMMENT ON TABLE products IS '商品主数据表，存储 Best Buy / Amazon 等来源的测试数据';
COMMENT ON COLUMN products.raw_data IS '完整保留导入时的原始 JSON，方便回溯和重新解析';

-- ============================================================
-- 2. 课程表
-- 对应现有 CourseRecord Pydantic 模型
-- ============================================================
CREATE TABLE IF NOT EXISTS courses (
    course_id       TEXT PRIMARY KEY,              -- make_id("course")
    product_id      TEXT REFERENCES products(product_id),
    product_name    TEXT NOT NULL,
    objective       TEXT NOT NULL,
    required_points JSONB NOT NULL DEFAULT '[]',   -- list[str]
    product_facts   JSONB NOT NULL DEFAULT '{}',   -- dict[str, str]
    content_version INT NOT NULL DEFAULT 0,
    latest_content  JSONB,                         -- 生成的训练内容
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_courses_product ON courses (product_id);

COMMENT ON TABLE courses IS '导购培训课程配置，对应 CourseRecord';

-- ============================================================
-- 3. 练习尝试表
-- 对应现有 TrainingAttemptRecord Pydantic 模型
-- ============================================================
CREATE TABLE IF NOT EXISTS training_attempts (
    attempt_id      TEXT PRIMARY KEY,              -- make_id("attempt")
    course_id       TEXT NOT NULL REFERENCES courses(course_id),
    user_id         TEXT NOT NULL,
    audio_url       TEXT,
    mock_transcript TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_attempts_course ON training_attempts (course_id);
CREATE INDEX IF NOT EXISTS idx_attempts_user ON training_attempts (user_id);

COMMENT ON TABLE training_attempts IS '导购练习记录，对应 TrainingAttemptRecord';

-- ============================================================
-- 4. 比价任务表
-- 对应现有 ComparisonTaskRecord Pydantic 模型
-- ============================================================
CREATE TABLE IF NOT EXISTS comparison_tasks (
    comparison_task_id TEXT PRIMARY KEY,            -- make_id("cmp")
    source_product_id  TEXT NOT NULL,               -- 关联 products 表（软引用，因为可能输入不在库中）
    source_product_name TEXT NOT NULL,
    targets            JSONB NOT NULL DEFAULT '[]', -- list[{platform, url}]
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_comparison_source ON comparison_tasks (source_product_id);

COMMENT ON TABLE comparison_tasks IS '跨平台比价任务，对应 ComparisonTaskRecord';

-- ============================================================
-- 5. 异步任务表
-- 对应现有 TaskRecord Pydantic 模型
-- 统一存储所有异步任务（内容生成、评分、比价执行）
-- ============================================================
CREATE TABLE IF NOT EXISTS tasks (
    task_id     TEXT PRIMARY KEY,                   -- make_id("task")
    trace_id    TEXT NOT NULL,                      -- 全链路追踪 ID
    task_type   TEXT NOT NULL,                      -- training.generate_content / training.evaluate / comparison.run
    status      TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'running', 'succeeded', 'failed')),
    input       JSONB NOT NULL DEFAULT '{}',        -- 任务输入参数
    output      JSONB,                              -- 任务输出结果
    error       TEXT,                               -- 失败原因
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tasks_trace ON tasks (trace_id);
CREATE INDEX IF NOT EXISTS idx_tasks_type ON tasks (task_type);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status);
CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks (created_at);

COMMENT ON TABLE tasks IS '统一异步任务表，对应 TaskRecord';

-- ============================================================
-- 6. Agent 事件日志表
-- 支持 RPG 可视化界面的 WebSocket 事件推送
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_events (
    event_id    BIGSERIAL PRIMARY KEY,              -- 自增 ID，保证顺序
    trace_id    TEXT NOT NULL,                       -- 关联到业务任务
    agent_name  TEXT NOT NULL,                       -- Agent 名称（orchestrator / coach / evaluator / price_intel）
    event_type  TEXT NOT NULL,                       -- 事件类型（见下方枚举）
    payload     JSONB NOT NULL DEFAULT '{}',         -- 事件负载（位置、状态、消息内容等）
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- event_type 枚举值说明:
--   agent_spawn     : Agent 被创建/激活
--   agent_move      : Agent 在地图上移动（RPG 可视化）
--   agent_think     : Agent 开始推理
--   agent_speak     : Agent 发出消息/与其他 Agent 对话
--   agent_act       : Agent 执行动作（调用工具/API）
--   agent_complete  : Agent 完成任务
--   agent_error     : Agent 遇到错误
--   agent_idle      : Agent 进入空闲状态

CREATE INDEX IF NOT EXISTS idx_events_trace ON agent_events (trace_id);
CREATE INDEX IF NOT EXISTS idx_events_agent ON agent_events (agent_name);
CREATE INDEX IF NOT EXISTS idx_events_type ON agent_events (event_type);
CREATE INDEX IF NOT EXISTS idx_events_created ON agent_events (created_at);

COMMENT ON TABLE agent_events IS 'Agent 事件流，用于 WebSocket 推送到 RPG 可视化界面';
COMMENT ON COLUMN agent_events.payload IS '事件负载示例: {"x":5,"y":3,"message":"正在分析商品数据...","target_agent":"evaluator"}';

-- ============================================================
-- 7. 审计日志表
-- trace_id 全链路追踪，记录所有关键变更
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_logs (
    log_id       BIGSERIAL PRIMARY KEY,
    trace_id     TEXT NOT NULL,                      -- 关联到业务链路
    action       TEXT NOT NULL,                      -- 动作类型（create / update / delete / invoke / review）
    actor        TEXT,                               -- 操作者（user_id / system / agent_name）
    entity_type  TEXT NOT NULL,                      -- 实体类型（course / attempt / comparison_task / task）
    entity_id    TEXT NOT NULL,                      -- 实体 ID
    before_state JSONB,                              -- 变更前状态（可选）
    after_state  JSONB,                              -- 变更后状态（可选）
    metadata     JSONB NOT NULL DEFAULT '{}',        -- 附加元数据（model_version, prompt_version, rubric_version 等）
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_trace ON audit_logs (trace_id);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_logs (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs (action);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs (created_at);

COMMENT ON TABLE audit_logs IS '全链路审计日志，支持 trace_id 追踪所有操作';
COMMENT ON COLUMN audit_logs.metadata IS '记录模型版本、prompt版本、知识版本等可追溯信息';
```

### 3.3 Pydantic 模型与数据库表的映射关系

| Pydantic 模型            | 数据库表             | 映射说明                                       |
| ------------------------ | -------------------- | ---------------------------------------------- |
| `CourseRecord`           | `courses`            | 字段一一对应，`required_points` 存为 JSONB      |
| `TrainingAttemptRecord`  | `training_attempts`  | 字段一一对应                                   |
| `ComparisonTaskRecord`   | `comparison_tasks`   | `targets` 存为 JSONB 数组                       |
| `TaskRecord`             | `tasks`              | `input`/`output` 存为 JSONB                     |
| (新增) `ProductRecord`   | `products`           | 新增，用于导入测试数据                          |
| (新增) `AgentEvent`      | `agent_events`       | 新增，用于 RPG 可视化                           |
| (新增) `AuditLog`        | `audit_logs`         | 新增，用于全链路审计                            |

### 3.4 时间字段策略

现有代码中时间字段使用 `str` 类型（`now_iso()` 返回 ISO 字符串）。数据库层使用 `TIMESTAMPTZ`。映射策略：

- **写入时**：Python `datetime` 对象直接写入 PostgreSQL `TIMESTAMPTZ`
- **读取时**：SQLAlchemy 返回 `datetime` 对象，在 API 层转为 ISO 字符串
- **现有 API 契约不变**：`ApiEnvelope` 中的时间字段继续返回 ISO 字符串

---

## 4. 数据流向图

### 4.1 整体数据流

```mermaid
flowchart LR
    subgraph 数据源
        BB["Best Buy Open Data<br/>(CC0 CSV/JSON)"]
        AMZ["Amazon Reviews 2023<br/>(Appliances 子集)"]
    end

    subgraph 数据导入
        SCRIPT["scripts/import_products.py<br/>解析 + 清洗 + 写入"]
    end

    subgraph PostgreSQL
        PROD[(products)]
        COURSE[(courses)]
        ATTEMPT[(training_attempts)]
        CMP[(comparison_tasks)]
        TASK[(tasks)]
        EVENT[(agent_events)]
        AUDIT[(audit_logs)]
    end

    subgraph FastAPI 后端
        API["API 路由层<br/>(main.py)"]
        ORCH["Orchestrator<br/>(orchestrator.py)"]
        TW["TrainingWorkflow"]
        CW["ComparisonWorkflow"]
    end

    subgraph 外部能力
        LLM["LLM Service"]
        TTS["TTS Service"]
        ASR["ASR Service"]
        OC["OpenClaw Adapter"]
    end

    subgraph 前端
        WEB["静态 HTML / React"]
        RPG["Phaser RPG 界面"]
        WS["WebSocket 客户端"]
    end

    BB --> SCRIPT
    AMZ --> SCRIPT
    SCRIPT --> PROD

    WEB -->|HTTP| API
    API -->|CRUD| COURSE
    API -->|CRUD| ATTEMPT
    API -->|CRUD| CMP
    API -->|创建异步任务| TASK
    API -->|BackgroundTasks| ORCH

    ORCH --> TW
    ORCH --> CW
    TW --> LLM
    TW --> TTS
    TW --> ASR
    CW --> OC
    CW --> LLM

    ORCH -->|更新状态| TASK
    ORCH -->|写入结果| COURSE
    ORCH -->|发布事件| EVENT
    ORCH -->|记录审计| AUDIT

    EVENT -->|WebSocket| WS
    WS --> RPG
    API -->|轮询任务状态| WEB
```

### 4.2 导购培训数据流

```mermaid
flowchart TD
    A["运营创建课程<br/>POST /api/v1/training/courses"] -->|写入| B[(courses)]
    B -->|读取| C["生成训练内容<br/>POST .../:generate-content"]
    C -->|创建| D[(tasks)]
    C -->|BackgroundTasks| E["TrainingWorkflow.generate_content()"]
    E -->|调用| F["MockLLMService / 真实 LLM"]
    E -->|调用| G["MockTTSService / 真实 TTS"]
    F -->|返回| E
    G -->|返回| E
    E -->|更新 latest_content| B
    E -->|更新 status=succeeded| D
    E -->|写入事件| H[(agent_events)]
    E -->|写入审计| I[(audit_logs)]

    J["导购提交练习<br/>POST /api/v1/training/attempts"] -->|写入| K[(training_attempts)]
    K -->|读取| L["发起评分<br/>POST .../:evaluate"]
    L -->|创建| D
    L -->|BackgroundTasks| M["TrainingWorkflow.evaluate_attempt()"]
    M -->|调用| N["MockASRService / 真实 ASR"]
    M -->|调用| O["ScoringService"]
    N -->|返回| M
    O -->|返回| M
    M -->|更新 output=report| D
    M -->|写入事件| H
    M -->|写入审计| I
```

### 4.3 跨平台比价数据流

```mermaid
flowchart TD
    A["运营创建比价任务<br/>POST /api/v1/comparison/tasks"] -->|写入| B[(comparison_tasks)]
    B -->|读取| C["执行比价<br/>POST .../:run"]
    C -->|创建| D[(tasks)]
    C -->|BackgroundTasks| E["ComparisonWorkflow.run()"]

    E -->|遍历 targets| F["OpenClawAdapter.collect()"]
    F -->|mock / remote| G["采集页面字段 + 截图"]
    G -->|返回 CollectedPage| E

    E -->|调用| H["normalize_offer()"]
    H -->|返回标准化报价| E

    E -->|调用| I["MockLLMService.summarize_comparison()"]
    I -->|返回 deltas + recommendations| E

    E -->|更新 output=report| D
    E -->|写入事件| J[(agent_events)]
    E -->|写入审计| K[(audit_logs)]
```

### 4.4 RPG 可视化事件流

```mermaid
sequenceDiagram
    participant API as FastAPI
    participant ORCH as Orchestrator
    participant DB as agent_events 表
    participant WS as WebSocket Server
    participant RPG as Phaser RPG 客户端

    API->>ORCH: 触发工作流（BackgroundTasks）
    ORCH->>DB: INSERT agent_event (agent_spawn)
    ORCH->>DB: INSERT agent_event (agent_think)
    Note over WS,DB: WebSocket Server 监听新事件<br/>（轮询 / LISTEN-NOTIFY）
    DB-->>WS: 新事件通知
    WS-->>RPG: JSON 事件推送
    RPG->>RPG: 更新 Agent 位置/状态/对话气泡
    ORCH->>DB: INSERT agent_event (agent_speak)
    DB-->>WS: 新事件通知
    WS-->>RPG: JSON 事件推送
    ORCH->>DB: INSERT agent_event (agent_complete)
    DB-->>WS: 新事件通知
    WS-->>RPG: JSON 事件推送
```

**WebSocket 事件格式**：

```json
{
  "event_id": 1024,
  "trace_id": "trc_a1b2c3d4e5",
  "agent_name": "price_intel",
  "event_type": "agent_speak",
  "payload": {
    "x": 8,
    "y": 5,
    "message": "京东到手价 2999，比淘宝低 100 元",
    "target_agent": "orchestrator",
    "emotion": "confident"
  },
  "created_at": "2026-03-12T10:30:15.123Z"
}
```

**PostgreSQL LISTEN/NOTIFY 机制**（一期推荐方案，避免引入 Redis）：

```sql
-- 在 INSERT 触发器中自动通知
CREATE OR REPLACE FUNCTION notify_agent_event() RETURNS trigger AS $$
BEGIN
    PERFORM pg_notify('agent_events', row_to_json(NEW)::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER agent_event_notify
    AFTER INSERT ON agent_events
    FOR EACH ROW EXECUTE FUNCTION notify_agent_event();
```

---

## 5. 从 InMemoryStore 迁移到数据库的路径

### 5.1 迁移策略：接口层抽象 + 实现替换

核心思路是 **保持现有 Store 接口方法签名不变**，将 `InMemoryStore` 替换为 `PostgresStore`。由于 `store.py` 被 `main.py` 和 `orchestrator.py` 直接导入使用，迁移过程中需要保证调用方零修改。

### 5.2 具体步骤

#### 步骤 1：定义抽象 Store 协议

从现有 `InMemoryStore` 提取接口协议，确保两个实现（内存版和数据库版）行为一致。

```python
# app/store_protocol.py
from __future__ import annotations
from typing import Optional, Protocol
from app.models import (
    ComparisonTaskRecord, CourseRecord,
    TaskRecord, TrainingAttemptRecord,
)


class StoreProtocol(Protocol):
    """Store 接口协议，InMemoryStore 和 PostgresStore 都必须实现。"""

    def put_course(self, course: CourseRecord) -> None: ...
    def get_course(self, course_id: str) -> Optional[CourseRecord]: ...
    def update_course_content(self, course_id: str, content: dict) -> None: ...

    def put_task(self, task: TaskRecord) -> None: ...
    def get_task(self, task_id: str) -> Optional[TaskRecord]: ...
    def update_task(self, task_id: str, **kwargs) -> None: ...

    def put_training_attempt(self, attempt: TrainingAttemptRecord) -> None: ...
    def get_training_attempt(self, attempt_id: str) -> Optional[TrainingAttemptRecord]: ...

    def put_comparison_task(self, task: ComparisonTaskRecord) -> None: ...
    def get_comparison_task(self, comparison_task_id: str) -> Optional[ComparisonTaskRecord]: ...
```

#### 步骤 2：定义 SQLAlchemy ORM 模型

在不修改 Pydantic 模型的前提下，新增 ORM 映射层。

```python
# app/db/orm_models.py
from sqlalchemy import (
    Column, Text, Integer, BigInteger,
    DateTime, CheckConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class CourseRow(Base):
    __tablename__ = "courses"

    course_id = Column(Text, primary_key=True)
    product_id = Column(Text)
    product_name = Column(Text, nullable=False)
    objective = Column(Text, nullable=False)
    required_points = Column(JSONB, nullable=False, server_default="[]")
    product_facts = Column(JSONB, nullable=False, server_default="{}")
    content_version = Column(Integer, nullable=False, default=0)
    latest_content = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TrainingAttemptRow(Base):
    __tablename__ = "training_attempts"

    attempt_id = Column(Text, primary_key=True)
    course_id = Column(Text, nullable=False)
    user_id = Column(Text, nullable=False)
    audio_url = Column(Text)
    mock_transcript = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ComparisonTaskRow(Base):
    __tablename__ = "comparison_tasks"

    comparison_task_id = Column(Text, primary_key=True)
    source_product_id = Column(Text, nullable=False)
    source_product_name = Column(Text, nullable=False)
    targets = Column(JSONB, nullable=False, server_default="[]")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TaskRow(Base):
    __tablename__ = "tasks"

    task_id = Column(Text, primary_key=True)
    trace_id = Column(Text, nullable=False)
    task_type = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="pending")
    input = Column("input", JSONB, nullable=False, server_default="{}")
    output = Column(JSONB)
    error = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("status IN ('pending', 'running', 'succeeded', 'failed')"),
    )


class AgentEventRow(Base):
    __tablename__ = "agent_events"

    event_id = Column(BigInteger, primary_key=True, autoincrement=True)
    trace_id = Column(Text, nullable=False)
    agent_name = Column(Text, nullable=False)
    event_type = Column(Text, nullable=False)
    payload = Column(JSONB, nullable=False, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AuditLogRow(Base):
    __tablename__ = "audit_logs"

    log_id = Column(BigInteger, primary_key=True, autoincrement=True)
    trace_id = Column(Text, nullable=False)
    action = Column(Text, nullable=False)
    actor = Column(Text)
    entity_type = Column(Text, nullable=False)
    entity_id = Column(Text, nullable=False)
    before_state = Column(JSONB)
    after_state = Column(JSONB)
    metadata_ = Column("metadata", JSONB, nullable=False, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

#### 步骤 3：实现 PostgresStore

关键设计：使用 **同步 SQLAlchemy** 会话，因为现有 `Orchestrator` 在 `BackgroundTasks` 中以同步方式调用 Store，切换为 async 需要改动调用方。一期保持同步，二期再考虑全异步改造。

```python
# app/db/postgres_store.py
from __future__ import annotations
from typing import Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.config import settings
from app.models import (
    ComparisonTaskRecord, CourseRecord,
    TaskRecord, TrainingAttemptRecord, now_iso,
)
from app.db.orm_models import (
    CourseRow, TrainingAttemptRow,
    ComparisonTaskRow, TaskRow,
)


class PostgresStore:
    """与 InMemoryStore 接口完全一致的 PostgreSQL 实现。"""

    def __init__(self, database_url: str) -> None:
        self._engine = create_engine(database_url, pool_size=5, max_overflow=10)
        self._session_factory = sessionmaker(bind=self._engine)

    def _session(self) -> Session:
        return self._session_factory()

    # ---- Course ----

    def put_course(self, course: CourseRecord) -> None:
        with self._session() as session:
            row = CourseRow(**course.model_dump())
            session.merge(row)
            session.commit()

    def get_course(self, course_id: str) -> Optional[CourseRecord]:
        with self._session() as session:
            row = session.get(CourseRow, course_id)
            if row is None:
                return None
            return CourseRecord(**{c.name: getattr(row, c.name) for c in row.__table__.columns})

    def update_course_content(self, course_id: str, content: dict) -> None:
        with self._session() as session:
            row = session.get(CourseRow, course_id)
            row.content_version += 1
            row.latest_content = content
            session.commit()

    # ---- Task ----

    def put_task(self, task: TaskRecord) -> None:
        with self._session() as session:
            row = TaskRow(**task.model_dump())
            session.merge(row)
            session.commit()

    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        with self._session() as session:
            row = session.get(TaskRow, task_id)
            if row is None:
                return None
            return TaskRecord(**{c.name: getattr(row, c.name) for c in row.__table__.columns})

    def update_task(self, task_id: str, **kwargs) -> None:
        with self._session() as session:
            row = session.get(TaskRow, task_id)
            for key, value in kwargs.items():
                setattr(row, key, value)
            session.commit()

    # ---- TrainingAttempt ----

    def put_training_attempt(self, attempt: TrainingAttemptRecord) -> None:
        with self._session() as session:
            row = TrainingAttemptRow(**attempt.model_dump())
            session.merge(row)
            session.commit()

    def get_training_attempt(self, attempt_id: str) -> Optional[TrainingAttemptRecord]:
        with self._session() as session:
            row = session.get(TrainingAttemptRow, attempt_id)
            if row is None:
                return None
            return TrainingAttemptRecord(**{c.name: getattr(row, c.name) for c in row.__table__.columns})

    # ---- ComparisonTask ----

    def put_comparison_task(self, task: ComparisonTaskRecord) -> None:
        with self._session() as session:
            row = ComparisonTaskRow(**task.model_dump())
            session.merge(row)
            session.commit()

    def get_comparison_task(self, comparison_task_id: str) -> Optional[ComparisonTaskRecord]:
        with self._session() as session:
            row = session.get(ComparisonTaskRow, comparison_task_id)
            if row is None:
                return None
            return ComparisonTaskRecord(**{c.name: getattr(row, c.name) for c in row.__table__.columns})
```

#### 步骤 4：修改 store.py 增加切换逻辑

改动最小化——只修改 `store.py` 底部的实例化逻辑：

```python
# app/store.py (修改后)
from __future__ import annotations
import os
from threading import Lock
from typing import Optional
from app.models import (
    ComparisonTaskRecord, CourseRecord,
    TaskRecord, TrainingAttemptRecord, now_iso,
)


class InMemoryStore:
    """保留原有实现，不修改。"""
    # ... 现有代码完全不变 ...


def _create_store():
    """根据环境变量选择 Store 实现。"""
    database_url = os.getenv("DATABASE_URL_SYNC")
    if database_url:
        from app.db.postgres_store import PostgresStore
        return PostgresStore(database_url)
    return InMemoryStore()


store = _create_store()
```

#### 步骤 5：初始化 Alembic 迁移框架

```bash
# 在项目根目录执行
pip install alembic
alembic init alembic

# 修改 alembic.ini 中的 sqlalchemy.url
# sqlalchemy.url = postgresql://ecom_ai:ecom_ai_dev@localhost:5432/ecom_ai

# 生成第一次迁移
alembic revision --autogenerate -m "initial schema"

# 执行迁移
alembic upgrade head
```

#### 步骤 6：验证迁移

```bash
# 1. 启动 Docker Compose
docker compose up -d postgres

# 2. 运行迁移
alembic upgrade head

# 3. 设置环境变量切换到 PostgreSQL
export DATABASE_URL_SYNC=postgresql://ecom_ai:ecom_ai_dev@localhost:5432/ecom_ai

# 4. 运行现有冒烟测试（必须全部通过）
pytest tests/test_smoke.py -v

# 5. 移除环境变量，确认回退到 InMemoryStore 也正常
unset DATABASE_URL_SYNC
pytest tests/test_smoke.py -v
```

### 5.3 迁移路径时间线

```mermaid
gantt
    title InMemoryStore → PostgresStore 迁移路径
    dateFormat  YYYY-MM-DD
    axisFormat  %m-%d

    section 准备
    定义 StoreProtocol           :a1, 2026-03-13, 1d
    创建 ORM 模型                :a2, after a1, 1d

    section 实现
    实现 PostgresStore           :b1, after a2, 2d
    修改 store.py 切换逻辑       :b2, after b1, 1d

    section 基础设施
    编写 Docker Compose          :c1, 2026-03-13, 1d
    编写 init_db.sql             :c2, after c1, 1d
    初始化 Alembic               :c3, after c2, 1d

    section 验证
    冒烟测试通过                 :d1, after b2, 1d
    数据导入脚本验证             :d2, after d1, 1d

    section 新增表
    实现 AgentEvent 写入         :e1, after d1, 2d
    实现 AuditLog 写入           :e2, after d1, 2d
    WebSocket 事件推送集成       :e3, after e1, 3d
```

### 5.4 文件结构变更

```
电商ai/
├── app/
│   ├── __init__.py
│   ├── config.py              # 新增 DATABASE_URL 配置
│   ├── main.py                # 不修改
│   ├── models.py              # 新增 ProductRecord, AgentEvent, AuditLog
│   ├── store.py               # 修改：底部加 _create_store() 切换逻辑
│   ├── store_protocol.py      # 新增：Store 接口协议
│   ├── db/                    # 新增目录
│   │   ├── __init__.py
│   │   ├── engine.py          # SQLAlchemy engine 和 session 工厂
│   │   ├── orm_models.py      # ORM 模型定义
│   │   └── postgres_store.py  # PostgresStore 实现
│   ├── services/
│   │   ├── orchestrator.py    # 不修改
│   │   ├── training_workflow.py
│   │   ├── comparison_workflow.py
│   │   ├── mock_services.py
│   │   └── openclaw_adapter.py
│   └── static/
├── alembic/                   # 新增：数据库迁移
│   ├── alembic.ini
│   ├── env.py
│   └── versions/
├── scripts/
│   ├── init_db.sql            # 新增：建表 DDL
│   ├── import_products.py     # 新增：导入测试商品数据
│   └── smoke_test.sh
├── docker-compose.yml         # 新增
├── Dockerfile                 # 新增
├── requirements.txt           # 更新：添加 sqlalchemy, asyncpg, alembic
└── tests/
    ├── test_smoke.py          # 不修改，自动适配
    └── test_postgres_store.py # 新增：PostgresStore 单元测试
```

### 5.5 关键约束保留

| 现有约定              | 迁移后保留方式                                          |
| --------------------- | ------------------------------------------------------- |
| `ApiEnvelope` 格式    | API 层不变，Store 层变更不影响响应格式                   |
| `make_id()` 生成 ID   | 继续在应用层生成 ID，数据库不使用自增主键（tasks/courses等） |
| `BackgroundTasks` 模式 | `Orchestrator` 调用方式不变，`store` 实例自动切换         |
| `now_iso()` 时间格式  | API 层继续返回 ISO 字符串，数据库层使用 TIMESTAMPTZ       |
| `trace_id` 全链路     | 所有表都保留 `trace_id` 字段，审计表额外记录完整链路      |

---

## 6. 商品数据导入方案

### 6.1 Best Buy Open Data

```python
# scripts/import_products.py (核心逻辑)

import csv
import json
from app.db.postgres_store import PostgresStore
from app.models import make_id


def import_bestbuy_products(csv_path: str, store: PostgresStore) -> int:
    """导入 Best Buy CSV 数据到 products 表。"""
    count = 0
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            product_id = make_id("prod")
            store.put_product(
                product_id=product_id,
                sku=row.get("sku", ""),
                name=row.get("name", ""),
                category=row.get("category", ""),
                brand=row.get("manufacturer", ""),
                attributes={
                    "regular_price": row.get("regularPrice", ""),
                    "sale_price": row.get("salePrice", ""),
                    "short_description": row.get("shortDescription", ""),
                    "long_description": row.get("longDescription", ""),
                },
                source_platform="bestbuy",
                source_url=row.get("url", ""),
                raw_data=dict(row),
            )
            count += 1
    return count
```

### 6.2 数据量预估

| 数据源                          | 预计记录数 | 存储估算  |
| ------------------------------- | ---------- | --------- |
| Best Buy Appliances 子集        | ~2,000     | ~5 MB     |
| Amazon Reviews Appliances       | ~5,000     | ~15 MB    |
| 课程/练习/比价（原型期间生成）  | ~500       | ~2 MB     |
| Agent 事件日志（单次演示）      | ~1,000     | ~1 MB     |
| 审计日志                        | ~2,000     | ~3 MB     |

总计约 **26 MB**，PostgreSQL 完全无压力。

---

## 7. 架构决策记录（ADR）

### ADR-001：选择 PostgreSQL 而非 SQLite

- **状态**：已采纳
- **上下文**：一期原型需要存储结构化数据 + JSON 数据，同时支持 BackgroundTasks 并发写入
- **决策**：PostgreSQL 16，Docker 部署
- **理由**：并发写入、jsonb 索引、生产迁移零成本
- **代价**：比 SQLite 多一个容器，本地开发需要 Docker

### ADR-002：同步 SQLAlchemy 而非 async

- **状态**：已采纳
- **上下文**：现有 Orchestrator 在 BackgroundTasks 中以同步方式调用 Store
- **决策**：一期使用同步 SQLAlchemy session
- **理由**：改为 async 需要改造 Orchestrator 和所有 workflow，风险大，收益小
- **代价**：每次数据库调用占用一个线程。原型阶段并发量极低，不是问题
- **后续**：二期全异步改造时，PostgresStore 换成 async session，配合 `async def` workflow

### ADR-003：WebSocket 事件使用 PostgreSQL LISTEN/NOTIFY 而非 Redis

- **状态**：已采纳
- **上下文**：RPG 可视化界面需要实时接收 Agent 事件
- **决策**：一期使用 PostgreSQL LISTEN/NOTIFY 推送事件，不引入 Redis
- **理由**：减少基础设施依赖；原型阶段并发连接数极少（< 10）；LISTEN/NOTIFY 延迟 < 10ms
- **代价**：不支持多实例水平扩展（单个 PG 连接只通知一个监听者）
- **后续**：二期如果需要多实例部署，引入 Redis Pub/Sub

### ADR-004：保持 Store 同步接口，通过环境变量切换实现

- **状态**：已采纳
- **上下文**：需要从 InMemoryStore 无缝迁移到 PostgresStore
- **决策**：`store.py` 底部通过 `DATABASE_URL_SYNC` 环境变量决定实例化哪个实现
- **理由**：调用方（main.py、orchestrator.py）零修改；测试可以不依赖数据库
- **代价**：两个实现需要保持接口一致；Protocol 不强制（Python duck typing）

---

## 8. 安全与运维考量

### 8.1 数据安全

- PostgreSQL 连接使用用户名密码认证，生产环境替换为 IAM 认证或 SSL 客户端证书
- `audit_logs` 表为追加写入，不允许 UPDATE/DELETE（可通过行级安全策略实现）
- 商品原始数据（`raw_data`）可能包含用户评论，不对外暴露，仅供内部分析

### 8.2 备份策略

- 开发环境：Docker volume 持久化，`pg_dump` 定期备份到本地
- 生产环境：RDS 自动快照 + WAL 归档（point-in-time recovery）

### 8.3 监控指标

| 指标                     | 告警阈值         | 监控方式                  |
| ------------------------ | ---------------- | ------------------------- |
| 数据库连接池使用率       | > 80%            | SQLAlchemy pool 事件      |
| 慢查询                   | > 500ms          | `pg_stat_statements`      |
| `tasks` 表 pending 积压  | > 50             | 定时查询                  |
| `agent_events` 写入延迟  | > 100ms          | 应用埋点                  |
| 磁盘使用率               | > 80%            | Docker stats / 系统监控   |

---

## 9. 总结与下一步

### 已确定

1. 数据库选型 PostgreSQL 16，Docker Compose 部署
2. 7 张核心表覆盖所有业务实体 + 事件日志 + 审计日志
3. InMemoryStore 到 PostgresStore 迁移路径明确，现有代码零破坏
4. WebSocket 事件流基于 PostgreSQL LISTEN/NOTIFY
5. 商品测试数据导入方案就绪

### 下一步行动

| 序号 | 行动项                                       | 预计耗时 |
| ---- | -------------------------------------------- | -------- |
| 1    | 创建 `app/db/` 目录，实现 ORM 模型            | 0.5 天   |
| 2    | 实现 `PostgresStore`，保持接口一致             | 1 天     |
| 3    | 编写 `docker-compose.yml` 和 `init_db.sql`    | 0.5 天   |
| 4    | 修改 `store.py` 切换逻辑，运行冒烟测试        | 0.5 天   |
| 5    | 初始化 Alembic，创建首次迁移                   | 0.5 天   |
| 6    | 编写商品数据导入脚本                           | 0.5 天   |
| 7    | 实现 Agent 事件写入 + WebSocket 端点           | 2 天     |

总计约 **5.5 个工作日**，可在一周内完成数据层迁移。
