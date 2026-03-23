# PRD：AgentsOffice 容器层 -- Agent 管理与可视化平台

## 1. 文档信息

| 项目 | 内容 |
| --- | --- |
| 产品名称 | AgentsOffice |
| 定位 | AI Agent 管理与可视化平台（容器层） |
| 文档类型 | 产品需求文档（PRD） |
| 当前阶段 | 容器层 MVP |
| 创建日期 | 2026-03-12 |
| 前置依赖 | 一期业务原型已跑通（导购培训 + 跨平台比价） |
| 技术栈 | React + Phaser 3 + WebSocket + FastAPI + PostgreSQL |

---

 
### 2.1 AgentsOffice 是什么

AgentsOffice 是一个 **AI Agent 管理与可视化平台**，它是承载所有 Agent 和非 Agent 模块的"容器"。类比：

- Agent 是"演员"，AgentsOffice 是"剧院"
- Agent 是"员工"，AgentsOffice 是"办公室"
- 具体的比价、培训是"节目"，AgentsOffice 是"舞台 + 控制室"

核心职责：
1. **Agent 生命周期管理** -- 注册、配置、启停、监控
2. **任务编排与追踪** -- 任务的创建、分发、状态追踪、结果查看
3. **成本监控** -- 各模型的 token 用量和费用统计
4. **运行可视化** -- 从管理后台到实时看板再到 Pixel RPG

### 2.2 AgentsOffice 不是什么

- **不是业务应用本身** -- 导购培训界面、比价报告页不属于 AgentsOffice，它们是 Agent 能力层的业务前端
- **不是 Agent 开发框架** -- 不提供 Agent 编写 SDK 或 DSL，Agent 的技术实现由 Agent 能力层负责
- **不是多租户 SaaS** -- 一期只服务项目负责人/管理员，不做租户隔离
- **不是自动化决策系统** -- 容器层只负责管理和呈现，不替代人做业务决策

### 2.3 MVP 范围边界

**一期做（容器层 MVP）：**

| 做 | 说明 |
| --- | --- |
| Agent 注册与 CRUD | 把 Agent 从硬编码变成可管理的数据库实体 |
| Agent 配置管理 | 为每个 Agent 配置模型、参数、Skills |
| Agent 状态看板 | 查看所有 Agent 的当前状态和健康度 |
| 任务中心 | 统一查看和管理 Agent 执行的所有任务 |
| 成本监控 | 按 Agent / 模型 / 时间段统计 token 用量和费用 |
| 事件日志 | Agent 的活动记录流，支持 trace_id 追踪 |
| Skills 注册表 | 查看和管理 Agent 绑定的 Skills |
| WebSocket 事件推送 | 为未来 RPG 可视化预留实时事件通道 |

**一期不做：**

| 不做 | 原因 |
| --- | --- |
| Pixel RPG 可视化 | 需要 Phaser 3 大量开发，放在二期 |
| Agent 之间的自主协商协议 | 一期的 Agent 协作由 Orchestrator 硬编排 |
| 可视化工作流编辑器 | 拖拽式编排过于复杂，一期用代码定义工作流 |
| 多用户权限体系 | 一期只有管理员角色 |
| Agent 市场 / Agent 模板商店 | 不在实验室阶段范围内 |
| 实时告警和通知 | 一期靠主动查看看板 |

### 2.4 容器层 vs Agent 能力层的职责划分

```
┌─────────────────────────────────────────────────────┐
│                 AgentsOffice（容器层）                 │
│                                                     │
│  Agent 注册表  │ 任务中心 │ 成本监控 │ 事件日志 │ 看板  │
│                                                     │
│  ─ ─ ─ ─ ─ ─ ─ 接口边界 ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  │
│                                                     │
│  容器层只关心：                                       │
│  - Agent 是谁（注册信息、配置）                        │
│  - Agent 在干什么（任务状态、事件流）                    │
│  - Agent 花了多少钱（token 用量、费用）                 │
│  - Agent 健不健康（状态、错误率）                       │
└─────────────────────────────────────────────────────┘
                         │
              Agent 能力层接口
              （标准化的上报协议）
                         │
┌─────────────────────────────────────────────────────┐
│               Agent 能力层（具体业务）                  │
│                                                     │
│  Agent 能力层只关心：                                  │
│  - 怎么完成任务（LLM 调用、工具使用）                    │
│  - 怎么产出结果（话术、评分、比价报告）                   │
│  - 需要什么 Skills（RAG、TTS、ASR、OpenClaw）          │
│                                                     │
│  Orchestrator │ Sales Coach │ Pitch Evaluator │ ...  │
└─────────────────────────────────────────────────────┘
```

**关键接口约定：**

| 接口方向 | 说明 | 协议 |
| --- | --- | --- |
| 容器层 -> 能力层 | 启动/停止 Agent、下发任务 | HTTP API 调用 |
| 能力层 -> 容器层 | 上报事件、上报 token 用量 | 写入 agent_events 表 + cost_records 表 |
| 能力层 -> 容器层 | 更新任务状态 | 更新 tasks 表 status/output |

---

## 3. 用户角色与核心用户旅程

### 3.1 一期用户角色

| 角色 | 人物画像 | 使用频次 |
| --- | --- | --- |
| 管理员（项目负责人） | 负责整个 AI 实验室的运行，需要掌握所有 Agent 的状态、成本、任务进度 | 日常使用 |

一期不区分细分角色。管理员拥有全部权限。

### 3.2 核心用户旅程

#### 旅程 A：管理员查看系统全局状态（日常巡检）

```
1. 打开 AgentsOffice 首页
2. 看到 Agent 总览卡片：
   - 6 个已注册 Agent 的状态（运行中 / 空闲 / 异常）
   - 今日任务统计（完成 / 进行中 / 失败）
   - 今日 token 消耗和费用
3. 发现 Price Intelligence Agent 状态异常
4. 点击该 Agent 卡片，进入 Agent 详情页
5. 查看最近事件日志，发现 3 次连续采集超时
6. 查看该 Agent 的成本趋势，确认费用是否异常
7. 决定是否需要调整配置或暂停 Agent
```

#### 旅程 B：管理员注册一个新 Agent

```
1. 在 Agent 管理页点击"注册新 Agent"
2. 填写 Agent 基本信息：
   - 名称：Risk and QA Agent
   - 描述：审核事实错误、违规表述、敏感风险
   - Agent 类型：审核型
3. 配置模型：
   - 选择模型：gpt-4o
   - 设置 temperature：0.2
   - 设置 max_tokens：4096
4. 绑定 Skills：
   - fact_check（事实核验）
   - compliance_check（合规检查）
5. 保存，Agent 状态变为"已注册/空闲"
6. 在 Agent 列表中看到新增的 Agent 卡片
```

#### 旅程 C：管理员追踪一个任务的完整链路

```
1. 在任务中心看到一个"比价任务"状态为"失败"
2. 点击任务，看到 trace_id 和完整时间线：
   - 14:30:01 Orchestrator 接收到比价请求
   - 14:30:02 Price Intelligence Agent 开始采集
   - 14:30:15 OpenClaw 采集京东页面成功
   - 14:30:28 OpenClaw 采集淘宝页面超时（失败原因）
   - 14:30:29 任务标记为失败
3. 查看该次任务消耗的 token 数量
4. 查看失败的原始错误信息和 payload
5. 决定是否要重新发起任务
```

#### 旅程 D：管理员查看成本报表

```
1. 进入成本监控页面
2. 选择时间范围：本周
3. 看到：
   - 按模型维度：gpt-4o 消耗 $12.30，gpt-4o-mini 消耗 $0.80
   - 按 Agent 维度：Sales Coach 消耗最多（$5.20）
   - 按任务类型维度：内容生成类最贵
4. 查看费用趋势图，判断是否需要切换更便宜的模型
5. 点击某个 Agent 的费用详情，看到每次调用的 token 明细
```

---

## 4. 功能模块拆解

### 4.1 模块 A：Agent 注册与管理

**定位：** AgentsOffice 的核心模块，把 Agent 从代码中的硬编码类变成数据库中可管理的实体。

**优先级：P0**

**核心功能点：**

| 编号 | 功能 | 验收标准（Given/When/Then） |
| --- | --- | --- |
| A-1 | Agent 注册 | Given 管理员在 Agent 管理页；When 填写名称、描述、类型并提交；Then 系统创建 Agent 记录，状态为 `idle`，在列表中可见 |
| A-2 | Agent 配置 | Given 一个已注册的 Agent；When 管理员修改其模型配置（model_name, temperature, max_tokens）并保存；Then 配置写入数据库，下次 Agent 执行时使用新配置 |
| A-3 | Agent 状态管理 | Given 一个处于 `idle` 状态的 Agent；When Agent 开始执行任务；Then 状态自动变更为 `running`；When 任务完成或失败；Then 状态自动回到 `idle` 或 `error` |
| A-4 | Agent 停用/启用 | Given 一个运行中的 Agent；When 管理员点击"停用"；Then Agent 状态变为 `disabled`，不再接受新任务，正在执行的任务不受影响 |
| A-5 | Agent 详情页 | Given 管理员点击某个 Agent；When 进入详情页；Then 可看到：基本信息、当前配置、绑定的 Skills 列表、最近 20 条事件日志、累计 token 消耗 |

**与 Agent 能力层的接口边界：**
- 容器层负责 Agent 元数据的 CRUD，不负责 Agent 的具体执行逻辑
- Agent 能力层在启动时从数据库读取 Agent 配置（模型、参数）
- Agent 能力层在执行过程中向 `agent_events` 表写入事件，容器层负责展示

---

### 4.2 模块 B：Agent 可视化看板

**定位：** 管理员的日常工作入口，一屏掌握所有 Agent 的运行状态。

**优先级：P0**

**核心功能点：**

| 编号 | 功能 | 验收标准（Given/When/Then） |
| --- | --- | --- |
| B-1 | Agent 状态总览 | Given 管理员打开 AgentsOffice 首页；When 页面加载完成；Then 显示所有已注册 Agent 的状态卡片，每张卡片包含：Agent 名称、当前状态（idle/running/error/disabled）、最后活跃时间 |
| B-2 | 任务统计摘要 | Given 管理员在看板页；When 选择时间范围（今日/本周/本月）；Then 显示该时段的任务总数、成功数、失败数、进行中数量，以及成功率百分比 |
| B-3 | 成本摘要 | Given 管理员在看板页；When 页面加载完成；Then 显示今日/本周/本月的总 token 消耗量和估算费用（单位：美元） |
| B-4 | 最近事件流 | Given 管理员在看板页；When 滚动到事件流区域；Then 实时展示最近 50 条 Agent 事件（agent_name + event_type + 时间 + 摘要），新事件自动追加到顶部 |
| B-5 | 异常高亮 | Given 某 Agent 最近 10 分钟有 >= 3 次 `agent_error` 事件；When 管理员查看看板；Then 该 Agent 卡片显示红色边框和异常标记 |

**与 Agent 能力层的接口边界：**
- 看板数据来源：`agents` 表（Agent 元数据）、`tasks` 表（任务统计）、`agent_events` 表（事件流）、`cost_records` 表（成本）
- 事件流通过 WebSocket 实时推送（基于 PostgreSQL LISTEN/NOTIFY）
- 容器层只消费数据，不修改 Agent 运行状态

---

### 4.3 模块 C：成本监控

**定位：** 追踪每个 Agent、每个模型、每次调用的 token 用量和费用，辅助模型选型决策。

**优先级：P0**

**核心功能点：**

| 编号 | 功能 | 验收标准（Given/When/Then） |
| --- | --- | --- |
| C-1 | 按 Agent 统计费用 | Given 管理员进入成本监控页并选择"按 Agent"视图；When 选择时间范围；Then 显示每个 Agent 的总 token 数（input + output 分开）、估算费用、调用次数，按费用降序排列 |
| C-2 | 按模型统计费用 | Given 管理员选择"按模型"视图；When 选择时间范围；Then 显示每个模型的总 token 数、估算费用、调用次数，费用按模型定价自动计算 |
| C-3 | 费用趋势图 | Given 管理员在成本监控页；When 选择"趋势"视图和时间范围；Then 显示折线图，X 轴为日期，Y 轴为费用，可按 Agent 或模型筛选 |
| C-4 | 单次调用明细 | Given 管理员点击某个 Agent 的费用行；When 展开详情；Then 显示该 Agent 最近的调用列表：时间、task_id、模型、input_tokens、output_tokens、费用 |
| C-5 | 模型定价配置 | Given 管理员进入成本设置；When 配置模型的 input/output 单价（$/1K tokens）；Then 后续的费用计算使用新的单价 |

**与 Agent 能力层的接口边界：**
- Agent 能力层在每次 LLM 调用完成后，向 `cost_records` 表写入一条记录，包含：agent_id, model_name, input_tokens, output_tokens, task_id, trace_id
- 容器层负责聚合查询和展示，不直接参与 LLM 调用
- 模型定价数据存储在 `model_pricing` 表中，由管理员配置

---

### 4.4 模块 D：Skills 管理

**定位：** Agent 的能力注册表。每个 Skill 是 Agent 可以使用的一个具体能力（工具/API/知识库访问），在容器层只做元数据管理。

**优先级：P1**

**核心功能点：**

| 编号 | 功能 | 验收标准（Given/When/Then） |
| --- | --- | --- |
| D-1 | Skill 注册 | Given 管理员在 Skills 管理页点击"注册 Skill"；When 填写名称（如 `tts_synthesize`）、描述、类型（tool/api/knowledge）、端点信息并提交；Then Skill 出现在列表中 |
| D-2 | Skill 绑定到 Agent | Given 一个已注册的 Skill 和一个已注册的 Agent；When 管理员在 Agent 详情页的 Skills 区域添加该 Skill；Then 绑定关系写入 `agent_skills` 关联表，Agent 详情页显示该 Skill |
| D-3 | Skill 列表与搜索 | Given 管理员在 Skills 管理页；When 输入关键词搜索或按类型筛选；Then 返回匹配的 Skill 列表，每个条目显示名称、类型、绑定的 Agent 数量 |
| D-4 | Skill 使用统计 | Given 管理员查看某个 Skill 详情；When 页面加载；Then 显示该 Skill 被调用的次数、成功率、平均耗时（从 agent_events 中聚合） |

**与 Agent 能力层的接口边界：**
- 容器层只管理 Skill 的"名片"（元数据和绑定关系），不管理 Skill 的实现代码
- Agent 能力层在执行时查询自己绑定了哪些 Skills，然后调用对应的服务
- Skill 的使用记录通过 agent_events 中的 `agent_act` 事件类型体现

---

### 4.5 模块 E：任务中心

**定位：** 所有 Agent 执行的任务的统一管理入口，替代直接查数据库看 tasks 表。

**优先级：P0**

**核心功能点：**

| 编号 | 功能 | 验收标准（Given/When/Then） |
| --- | --- | --- |
| E-1 | 任务列表 | Given 管理员进入任务中心；When 页面加载；Then 显示最近 100 条任务，每条包含：task_id、task_type、状态、创建时间、耗时、关联 Agent；支持按状态和类型筛选 |
| E-2 | 任务详情 | Given 管理员点击某个任务；When 进入详情页；Then 显示：task_id、trace_id、task_type、status、input（JSON 可折叠）、output（JSON 可折叠）、error（如有）、创建和更新时间 |
| E-3 | 任务事件时间线 | Given 管理员在任务详情页；When 查看时间线区域；Then 显示该 trace_id 关联的所有 agent_events，按时间排序，形成完整的任务执行链路 |
| E-4 | 任务重试 | Given 一个状态为 `failed` 的任务；When 管理员点击"重试"；Then 系统创建一个新任务（新 task_id，相同 input），关联到同一 trace_id |
| E-5 | 任务统计 | Given 管理员在任务中心顶部；When 选择时间范围；Then 显示：总任务数、按 task_type 分布饼图、成功率趋势图、平均耗时 |

**与 Agent 能力层的接口边界：**
- 任务创建仍由业务 API（main.py 中的路由）触发，容器层不创建业务任务
- 容器层只提供任务的查看、筛选和重试功能
- 任务重试实际上是调用对应的业务 API 重新下发任务

---

### 4.6 模块 F：事件日志

**定位：** Agent 的活动记录和审计日志的统一查看入口。

**优先级：P1**

**核心功能点：**

| 编号 | 功能 | 验收标准（Given/When/Then） |
| --- | --- | --- |
| F-1 | 事件流查看 | Given 管理员进入事件日志页；When 页面加载；Then 显示最近 200 条事件，每条包含：时间、agent_name、event_type、payload 摘要；实时通过 WebSocket 追加新事件 |
| F-2 | 按 trace_id 查询 | Given 管理员输入一个 trace_id；When 点击搜索；Then 返回该 trace_id 关联的所有事件和审计记录，按时间排序 |
| F-3 | 按 Agent 筛选 | Given 管理员选择某个 Agent 名称作为筛选条件；When 应用筛选；Then 只显示该 Agent 的事件日志 |
| F-4 | 事件详情 | Given 管理员点击某条事件；When 展开详情；Then 显示完整的 payload JSON |
| F-5 | 审计日志查看 | Given 管理员切换到"审计日志"标签；When 页面加载；Then 显示 audit_logs 表中的记录，支持按 entity_type 和 action 筛选 |

**与 Agent 能力层的接口边界：**
- 事件由 Agent 能力层写入 `agent_events` 和 `audit_logs` 表
- 容器层只负责读取和展示，提供搜索和筛选能力
- WebSocket 事件推送基于 PostgreSQL LISTEN/NOTIFY 触发器（已在 init_db.sql 中预留设计）

---

### 4.7 模块 G：系统设置

**定位：** 管理全局配置，包括模型定价、系统参数等。

**优先级：P2**

**核心功能点：**

| 编号 | 功能 | 验收标准（Given/When/Then） |
| --- | --- | --- |
| G-1 | 模型定价管理 | Given 管理员进入系统设置；When 添加或修改模型定价（model_name, input_price_per_1k, output_price_per_1k）；Then 新定价立即用于成本计算 |
| G-2 | Agent 类型管理 | Given 管理员在设置页；When 添加新的 Agent 类型（如"审核型"、"生成型"、"分析型"）；Then 注册 Agent 时可选择该类型 |
| G-3 | 系统健康检查 | Given 管理员在设置页；When 点击"健康检查"；Then 检查并显示：PostgreSQL 连接状态、WebSocket 服务状态、各外部服务（LLM/TTS/ASR/OpenClaw）可达性 |

**与 Agent 能力层的接口边界：**
- 系统设置是纯容器层功能，不与 Agent 能力层交互
- 模型定价通过 `model_pricing` 表存储，成本监控模块读取

---

## 5. 数据模型草案

### 5.1 新增表：agents（Agent 注册表）

```sql
CREATE TABLE IF NOT EXISTS agents (
    agent_id        TEXT PRIMARY KEY,           -- make_id("agt")
    name            TEXT NOT NULL UNIQUE,        -- Agent 显示名称（如 "Sales Coach Agent"）
    slug            TEXT NOT NULL UNIQUE,        -- 代码引用名（如 "sales_coach"），对应现有 agent_events.agent_name
    description     TEXT,                        -- Agent 职责描述
    agent_type      TEXT NOT NULL DEFAULT 'general',  -- 类型：general / generator / evaluator / collector / auditor
    status          TEXT NOT NULL DEFAULT 'idle'
                    CHECK (status IN ('idle', 'running', 'error', 'disabled')),

    -- 模型配置
    model_config    JSONB NOT NULL DEFAULT '{}',
    -- 结构示例：
    -- {
    --   "model_name": "gpt-4o",
    --   "temperature": 0.7,
    --   "max_tokens": 4096,
    --   "system_prompt_version": "v1.2"
    -- }

    -- 运行时元数据
    last_active_at  TIMESTAMPTZ,                -- 最后活跃时间
    error_message   TEXT,                        -- 最近错误信息（status=error 时）
    metadata        JSONB NOT NULL DEFAULT '{}', -- 扩展字段

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agents_slug ON agents (slug);
CREATE INDEX IF NOT EXISTS idx_agents_status ON agents (status);
CREATE INDEX IF NOT EXISTS idx_agents_type ON agents (agent_type);

COMMENT ON TABLE agents IS 'Agent 注册表，管理所有 AI Agent 的元数据和配置';
COMMENT ON COLUMN agents.slug IS '代码级标识，与 agent_events.agent_name 对应';
COMMENT ON COLUMN agents.model_config IS '模型配置，包含 model_name, temperature, max_tokens 等';
```

**与现有表的关系：**
- `agents.slug` 对应现有 `agent_events.agent_name`，通过该字段关联事件
- 现有 6 个 Agent（orchestrator, sales_coach, pitch_evaluator, price_intel, risk_qa, experiment_analyst）将作为初始种子数据写入

### 5.2 新增表：skills（Skill 注册表）

```sql
CREATE TABLE IF NOT EXISTS skills (
    skill_id        TEXT PRIMARY KEY,           -- make_id("skl")
    name            TEXT NOT NULL UNIQUE,        -- Skill 名称（如 "tts_synthesize"）
    display_name    TEXT NOT NULL,               -- 显示名称（如 "语音合成"）
    description     TEXT,                        -- Skill 描述
    skill_type      TEXT NOT NULL DEFAULT 'tool'
                    CHECK (skill_type IN ('tool', 'api', 'knowledge', 'internal')),
    endpoint        TEXT,                        -- 服务端点（如 API URL）
    config          JSONB NOT NULL DEFAULT '{}', -- Skill 特有配置
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'deprecated', 'disabled')),

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE skills IS 'Skill 注册表，管理 Agent 可使用的能力';
```

### 5.3 新增表：agent_skills（Agent-Skill 关联表）

```sql
CREATE TABLE IF NOT EXISTS agent_skills (
    agent_id    TEXT NOT NULL REFERENCES agents(agent_id),
    skill_id    TEXT NOT NULL REFERENCES skills(skill_id),
    config      JSONB NOT NULL DEFAULT '{}',    -- Agent 特定的 Skill 配置覆盖
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (agent_id, skill_id)
);

COMMENT ON TABLE agent_skills IS 'Agent 与 Skill 的多对多绑定关系';
```

### 5.4 新增表：cost_records（成本记录表）

```sql
CREATE TABLE IF NOT EXISTS cost_records (
    record_id       BIGSERIAL PRIMARY KEY,
    agent_id        TEXT REFERENCES agents(agent_id),   -- 关联 Agent
    agent_slug      TEXT NOT NULL,                       -- 冗余存储，方便快速查询
    task_id         TEXT,                                -- 关联 tasks 表
    trace_id        TEXT NOT NULL,                       -- 全链路追踪

    -- 模型和 token 信息
    model_name      TEXT NOT NULL,                       -- 如 "gpt-4o", "gpt-4o-mini"
    input_tokens    INT NOT NULL DEFAULT 0,
    output_tokens   INT NOT NULL DEFAULT 0,
    total_tokens    INT NOT NULL DEFAULT 0,              -- input + output

    -- 费用（单位：美元，精确到小数点后 6 位）
    input_cost      NUMERIC(12, 6) NOT NULL DEFAULT 0,
    output_cost     NUMERIC(12, 6) NOT NULL DEFAULT 0,
    total_cost      NUMERIC(12, 6) NOT NULL DEFAULT 0,

    -- 调用元数据
    duration_ms     INT,                                 -- 调用耗时（毫秒）
    metadata        JSONB NOT NULL DEFAULT '{}',         -- 额外信息（prompt 版本等）

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cost_agent ON cost_records (agent_id);
CREATE INDEX IF NOT EXISTS idx_cost_agent_slug ON cost_records (agent_slug);
CREATE INDEX IF NOT EXISTS idx_cost_model ON cost_records (model_name);
CREATE INDEX IF NOT EXISTS idx_cost_task ON cost_records (task_id);
CREATE INDEX IF NOT EXISTS idx_cost_trace ON cost_records (trace_id);
CREATE INDEX IF NOT EXISTS idx_cost_created ON cost_records (created_at);

COMMENT ON TABLE cost_records IS '模型调用成本记录，每次 LLM 调用写入一条';
COMMENT ON COLUMN cost_records.agent_slug IS '冗余字段，避免每次查询都 JOIN agents 表';
```

### 5.5 新增表：model_pricing（模型定价表）

```sql
CREATE TABLE IF NOT EXISTS model_pricing (
    model_name          TEXT PRIMARY KEY,                -- 模型名称
    display_name        TEXT NOT NULL,                   -- 显示名称
    provider            TEXT NOT NULL DEFAULT 'openai',  -- 提供商
    input_price_per_1k  NUMERIC(10, 6) NOT NULL,         -- 每 1K input tokens 价格（美元）
    output_price_per_1k NUMERIC(10, 6) NOT NULL,         -- 每 1K output tokens 价格（美元）
    is_active           BOOLEAN NOT NULL DEFAULT true,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 初始种子数据
INSERT INTO model_pricing (model_name, display_name, provider, input_price_per_1k, output_price_per_1k) VALUES
    ('gpt-4o',      'GPT-4o',      'openai',    0.002500, 0.010000),
    ('gpt-4o-mini', 'GPT-4o Mini', 'openai',    0.000150, 0.000600),
    ('gpt-4.1',     'GPT-4.1',     'openai',    0.002000, 0.008000),
    ('gpt-4.1-mini','GPT-4.1 Mini','openai',    0.000400, 0.001600),
    ('gpt-4.1-nano','GPT-4.1 Nano','openai',    0.000100, 0.000400),
    ('claude-sonnet-4-20250514', 'Claude Sonnet 4', 'anthropic', 0.003000, 0.015000),
    ('claude-opus-4-20250514',   'Claude Opus 4',   'anthropic', 0.015000, 0.075000)
ON CONFLICT (model_name) DO NOTHING;

COMMENT ON TABLE model_pricing IS '模型定价配置，用于计算成本';
```

### 5.6 修改现有表：tasks -- 增加 agent_id 字段

```sql
-- 为 tasks 表增加 agent_id 关联（可空，兼容现有数据）
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS agent_id TEXT;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS agent_slug TEXT;

CREATE INDEX IF NOT EXISTS idx_tasks_agent ON tasks (agent_id);
CREATE INDEX IF NOT EXISTS idx_tasks_agent_slug ON tasks (agent_slug);
```

### 5.7 完整 ER 关系图（容器层新增）

```
agents 1 ──── * agent_skills * ──── 1 skills
  │
  │ 1
  │
  ├──── * cost_records
  │
  ├──── * agent_events （现有表，通过 slug 关联）
  │
  └──── * tasks （现有表，新增 agent_id 字段）

model_pricing （独立配置表）
```

### 5.8 与现有表的兼容策略

| 现有表 | 变化 | 兼容策略 |
| --- | --- | --- |
| products | 不变 | 无影响 |
| courses | 不变 | 无影响 |
| training_attempts | 不变 | 无影响 |
| comparison_tasks | 不变 | 无影响 |
| tasks | 新增 `agent_id`, `agent_slug` 列 | 可空字段，现有数据不受影响 |
| agent_events | 不变 | 通过 `agent_name` = `agents.slug` 逻辑关联 |
| audit_logs | 不变 | 无影响 |

---

## 6. 非 Agent 模块清单

以下功能模块不应该用 Agent 实现，它们是确定性逻辑，应该作为普通的代码模块运行。

| 模块 | 定位 | 实现方式 | 与 Agent 的关系 |
| --- | --- | --- | --- |
| **成本计算引擎** | 根据 token 数和模型定价计算费用 | Python 函数，读 `model_pricing` 表 | Agent 调用 LLM 后上报 token 数，计算引擎自动算费用 |
| **任务状态机** | 管理 task 的状态转换（pending -> running -> succeeded/failed） | 现有 `store.update_task()` 逻辑 | Agent 执行时更新状态，但状态转换规则不依赖 AI |
| **数据导入管道** | 导入商品数据到 products 表 | Python 脚本（`scripts/import_products.py`） | 为 Agent 提供商品知识基础数据，但导入过程不需要 AI |
| **价格标准化规则引擎** | 到手价、券后价、满减的统一口径计算 | Python 函数（`normalize_offer()`） | 被 Price Intelligence Agent 调用，但计算逻辑是确定性规则 |
| **WebSocket 事件网关** | 接收 LISTEN/NOTIFY 事件并推送给前端 | FastAPI WebSocket 端点 | 转发 Agent 事件到前端，自身不包含 AI 逻辑 |
| **审计日志中间件** | 记录所有关键操作到 audit_logs 表 | FastAPI middleware | 被动记录，不参与 Agent 决策 |
| **健康检查服务** | 检测各服务组件可达性 | HTTP 端点 + 数据库查询 | 检查 Agent 依赖的外部服务是否正常 |

**关键原则：** 确定性逻辑走规则，不确定性推理走 Agent。价格计算、状态转换、数据导入这些有确定规则的事情，不需要浪费 AI 资源。

---

## 7. 从 MVP 到 RPG 可视化的路线建议

### 阶段一：管理后台（MVP，当前目标）

**核心交付物：**
- 基于 React 的传统 Web 管理后台
- Agent CRUD 和配置管理
- 任务列表和详情查看
- 成本统计表格和简单图表
- 事件日志列表（HTTP 轮询）

**技术特点：**
- React + Ant Design / Shadcn UI
- RESTful API
- 数据库直接查询 + 前端渲染
- 无 WebSocket，前端定时轮询（每 5 秒）刷新状态

**完成标准：**
- 管理员可以通过 Web 界面完成 Agent 管理、任务查看、成本查看的全部操作
- 不再需要直接查数据库

**预计工期：** 2-3 周

---

### 阶段二：实时看板

**核心交付物：**
- WebSocket 实时事件推送
- Agent 状态实时更新（不需要手动刷新）
- 任务执行时间线实时展示
- 成本实时累加器
- 简单的数据可视化（ECharts / Recharts 图表）

**技术特点：**
- FastAPI WebSocket 端点
- PostgreSQL LISTEN/NOTIFY -> WebSocket Server -> React 前端
- 状态变更推送，不再轮询
- 增加图表：费用趋势线、任务分布饼图、Agent 活跃热力图

**与阶段一的增量：**
- 替换轮询为 WebSocket
- 增加实时事件流组件
- 增加数据可视化图表

**完成标准：**
- 任务执行时，管理员可以实时看到事件流滚动更新
- Agent 状态变更在 1 秒内反映在界面上

**预计工期：** 1-2 周（在阶段一基础上）

---

### 阶段三：Pixel RPG 可视化

**核心交付物：**
- Phaser 3 像素风格虚拟办公室场景
- 每个 Agent 是一个可移动的像素角色
- Agent 执行任务时有对应的动画和对话气泡
- Agent 之间的协作通过角色移动和交互表现
- 完整的 SEGA MD / 像素 RPG 美学风格

**技术特点：**
- React 作为外壳，Phaser 3 作为游戏渲染引擎
- WebSocket 事件驱动角色行为
- `agent_events` 中的 `payload.x`, `payload.y` 驱动角色位置
- `event_type` 映射到角色动画状态：
  - `agent_spawn` -> 角色出现动画
  - `agent_think` -> 角色头顶出现思考气泡
  - `agent_speak` -> 角色对话框显示消息
  - `agent_act` -> 角色执行动作动画
  - `agent_move` -> 角色移动到目标位置
  - `agent_complete` -> 角色完成动画（星星/绿色光效）
  - `agent_error` -> 角色错误动画（红色叹号）
  - `agent_idle` -> 角色待机动画

**必须在阶段一/二预留的接口：**
1. `agent_events` 表的 `payload` 字段已支持 `x`, `y`, `emotion`, `target_agent` 等 RPG 所需字段
2. WebSocket 事件推送协议已标准化
3. Agent 注册表中预留 `metadata` 字段，可存储像素角色配置（sprite_id, default_position 等）
4. 事件类型枚举已包含 RPG 可视化所需的全部类型

**完成标准：**
- 打开 RPG 可视化页面，看到像素风格的虚拟办公室
- 发起一个比价任务后，可以看到 Orchestrator 角色走到 Price Intelligence 角色旁边"对话"
- 任务完成后，角色回到各自工位

**预计工期：** 4-6 周（独立前端工程）

---

### 各阶段交付时间线

```
阶段一：管理后台（MVP）
  ├── Week 1-2: 后端 API + 前端骨架 + Agent CRUD
  └── Week 3: 任务中心 + 成本监控 + 事件日志

阶段二：实时看板
  ├── Week 4: WebSocket 事件网关 + 实时事件流组件
  └── Week 5: 数据可视化图表 + 异常高亮

阶段三：Pixel RPG 可视化
  ├── Week 6-7: Phaser 3 场景搭建 + 角色系统
  ├── Week 8-9: WebSocket 事件 -> 角色行为映射
  └── Week 10-11: 动画打磨 + 交互优化 + Demo 准备
```

---

## 8. AgentsOffice 容器层 API 设计草案

以下 API 全部挂在 `/api/v1/office/` 命名空间下，与现有业务 API（`/api/v1/training/`、`/api/v1/comparison/`）隔离。

### 8.1 Agent 管理 API

```
POST   /api/v1/office/agents                  创建 Agent
GET    /api/v1/office/agents                  获取 Agent 列表
GET    /api/v1/office/agents/{agent_id}       获取 Agent 详情
PUT    /api/v1/office/agents/{agent_id}       更新 Agent 信息和配置
PATCH  /api/v1/office/agents/{agent_id}/status  更新 Agent 状态（启用/停用）
DELETE /api/v1/office/agents/{agent_id}       删除 Agent（软删除）
```

### 8.2 Skills 管理 API

```
POST   /api/v1/office/skills                  注册 Skill
GET    /api/v1/office/skills                  获取 Skill 列表
GET    /api/v1/office/skills/{skill_id}       获取 Skill 详情
PUT    /api/v1/office/skills/{skill_id}       更新 Skill
POST   /api/v1/office/agents/{agent_id}/skills/{skill_id}  绑定 Skill 到 Agent
DELETE /api/v1/office/agents/{agent_id}/skills/{skill_id}  解绑 Skill
```

### 8.3 任务中心 API

```
GET    /api/v1/office/tasks                   任务列表（支持筛选：status, task_type, agent_slug, 时间范围）
GET    /api/v1/office/tasks/{task_id}         任务详情（含关联事件时间线）
POST   /api/v1/office/tasks/{task_id}:retry   重试失败任务
GET    /api/v1/office/tasks/stats             任务统计（按时间范围聚合）
```

### 8.4 成本监控 API

```
GET    /api/v1/office/costs/by-agent          按 Agent 聚合费用（支持时间范围）
GET    /api/v1/office/costs/by-model          按模型聚合费用（支持时间范围）
GET    /api/v1/office/costs/trend             费用趋势（按日聚合）
GET    /api/v1/office/costs/records           原始成本记录列表
GET    /api/v1/office/costs/summary           费用总览（今日/本周/本月）
```

### 8.5 事件日志 API

```
GET    /api/v1/office/events                  事件列表（支持筛选：agent_name, event_type, trace_id）
GET    /api/v1/office/events/{event_id}       事件详情
GET    /api/v1/office/audit-logs              审计日志列表
WS     /api/v1/office/ws/events               WebSocket 实时事件推送
```

### 8.6 系统设置 API

```
GET    /api/v1/office/settings/model-pricing           获取模型定价列表
PUT    /api/v1/office/settings/model-pricing/{model}   更新模型定价
GET    /api/v1/office/health                           系统健康检查
```

---

## 9. 与现有代码库的融合策略

### 9.1 文件结构规划

```
AgentOffice/
├── app/
│   ├── main.py                    # 现有业务路由 + 挂载 office 路由
│   ├── models.py                  # 现有 Pydantic 模型
│   ├── store.py                   # 现有 Store 实现
│   ├── config.py                  # 现有配置
│   │
│   ├── office/                    # 新增：AgentsOffice 容器层
│   │   ├── __init__.py
│   │   ├── router.py              # FastAPI Router，挂载到 /api/v1/office/
│   │   ├── models.py              # 容器层 Pydantic 模型（AgentCreate, SkillCreate, CostSummary 等）
│   │   ├── store.py               # 容器层 Store（agents, skills, cost_records 的 CRUD）
│   │   ├── cost_engine.py         # 成本计算引擎（非 Agent 模块）
│   │   └── ws_gateway.py          # WebSocket 事件网关
│   │
│   ├── db/                        # 现有数据库层
│   │   ├── orm_models.py          # 新增 AgentRow, SkillRow, CostRecordRow 等
│   │   └── postgres_store.py      # 现有 Store 实现
│   │
│   ├── services/                  # 现有业务服务
│   │   ├── orchestrator.py        # 改造：启动时从 agents 表读取配置
│   │   ├── training_workflow.py   # 改造：完成后写入 cost_records
│   │   └── comparison_workflow.py # 改造：完成后写入 cost_records
│   │
│   └── static/                    # 前端静态文件
│       ├── index.html             # 现有
│       └── office/                # 新增：AgentsOffice 前端（React 构建输出）
│
├── frontend/                      # 新增：前端源码目录
│   ├── package.json
│   ├── src/
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx      # 看板首页
│   │   │   ├── AgentList.tsx      # Agent 列表
│   │   │   ├── AgentDetail.tsx    # Agent 详情
│   │   │   ├── TaskCenter.tsx     # 任务中心
│   │   │   ├── CostMonitor.tsx    # 成本监控
│   │   │   ├── EventLog.tsx       # 事件日志
│   │   │   └── Settings.tsx       # 系统设置
│   │   └── components/
│   │       ├── AgentCard.tsx       # Agent 状态卡片
│   │       ├── EventStream.tsx     # 事件流组件
│   │       ├── CostChart.tsx       # 费用图表
│   │       └── TaskTimeline.tsx    # 任务时间线
│   └── vite.config.ts
│
├── scripts/
│   └── seed_agents.sql            # 新增：Agent 和 Skill 初始种子数据
│
└── docs/
    └── agentsoffice_container_prd.md  # 本文档
```

### 9.2 对现有代码的改造清单

| 文件 | 改造内容 | 影响范围 |
| --- | --- | --- |
| `app/main.py` | 增加 `app.include_router(office_router, prefix="/api/v1/office")` | 仅新增一行挂载 |
| `app/services/orchestrator.py` | Agent 执行时从 `agents` 表读取 `model_config`；执行完成后写入 `cost_records` | 改造 `run_*` 方法 |
| `app/services/training_workflow.py` | LLM/TTS/ASR 调用后，返回 token 用量数据 | 返回值增加 usage 字段 |
| `app/services/comparison_workflow.py` | LLM 调用后，返回 token 用量数据 | 返回值增加 usage 字段 |
| `app/db/orm_models.py` | 新增 `AgentRow`, `SkillRow`, `AgentSkillRow`, `CostRecordRow`, `ModelPricingRow` | 新增 ORM 类 |
| `scripts/init_db.sql` | 新增建表语句 | 追加 SQL |

### 9.3 初始种子数据

```sql
-- scripts/seed_agents.sql

-- 注册现有 6 个 Agent
INSERT INTO agents (agent_id, name, slug, description, agent_type, model_config) VALUES
    ('agt_orchestrator', 'Orchestrator Agent', 'orchestrator',
     '意图识别、流程路由、上下文装配、权限控制', 'general',
     '{"model_name": "gpt-4o-mini", "temperature": 0.3, "max_tokens": 2048}'),

    ('agt_sales_coach', 'Sales Coach Agent', 'sales_coach',
     '生成卖点、话术、模拟问答、训练内容', 'generator',
     '{"model_name": "gpt-4o", "temperature": 0.7, "max_tokens": 4096}'),

    ('agt_pitch_eval', 'Pitch Evaluator Agent', 'pitch_evaluator',
     '录音转写、事实核验、停顿分析、评分建议', 'evaluator',
     '{"model_name": "gpt-4o", "temperature": 0.2, "max_tokens": 4096}'),

    ('agt_price_intel', 'Price Intelligence Agent', 'price_intel',
     '采集后数据对齐、价格与福利对比、差异解释、经营建议', 'evaluator',
     '{"model_name": "gpt-4o", "temperature": 0.3, "max_tokens": 4096}'),

    ('agt_risk_qa', 'Risk and QA Agent', 'risk_qa',
     '审核事实错误、违规表述、敏感风险', 'auditor',
     '{"model_name": "gpt-4o-mini", "temperature": 0.1, "max_tokens": 2048}'),

    ('agt_experiment', 'Experiment Analyst Agent', 'experiment_analyst',
     '汇总试点指标、分析 ROI、识别问题', 'general',
     '{"model_name": "gpt-4o-mini", "temperature": 0.5, "max_tokens": 4096}')
ON CONFLICT (agent_id) DO NOTHING;

-- 注册现有 Skills
INSERT INTO skills (skill_id, name, display_name, description, skill_type) VALUES
    ('skl_llm',         'llm_generate',      'LLM 生成',      '调用大语言模型进行文本生成', 'api'),
    ('skl_tts',         'tts_synthesize',     '语音合成',      '将文本转换为语音', 'api'),
    ('skl_asr',         'asr_transcribe',     '语音转写',      '将语音转换为文本', 'api'),
    ('skl_scoring',     'pitch_scoring',      '话术评分',      '评估导购话术质量', 'internal'),
    ('skl_openclaw',    'openclaw_collect',   '页面采集',      '使用 OpenClaw 采集平台页面', 'tool'),
    ('skl_normalize',   'offer_normalize',    '价格标准化',    '标准化价格和福利字段', 'internal'),
    ('skl_fact_check',  'fact_check',         '事实核验',      '核验 AI 输出中的事实准确性', 'internal'),
    ('skl_rag',         'rag_retrieve',       '知识检索',      'RAG 检索商品知识库', 'knowledge')
ON CONFLICT (skill_id) DO NOTHING;

-- 绑定 Skills 到 Agents
INSERT INTO agent_skills (agent_id, skill_id) VALUES
    ('agt_sales_coach', 'skl_llm'),
    ('agt_sales_coach', 'skl_tts'),
    ('agt_sales_coach', 'skl_rag'),
    ('agt_pitch_eval',  'skl_llm'),
    ('agt_pitch_eval',  'skl_asr'),
    ('agt_pitch_eval',  'skl_scoring'),
    ('agt_pitch_eval',  'skl_fact_check'),
    ('agt_price_intel', 'skl_llm'),
    ('agt_price_intel', 'skl_openclaw'),
    ('agt_price_intel', 'skl_normalize'),
    ('agt_risk_qa',     'skl_llm'),
    ('agt_risk_qa',     'skl_fact_check'),
    ('agt_experiment',  'skl_llm'),
    ('agt_experiment',  'skl_rag')
ON CONFLICT DO NOTHING;
```

---

## 10. 验收清单（MVP）

### 10.1 功能验收

| 编号 | 验收项 | 验收方法 |
| --- | --- | --- |
| V-1 | 管理员可以在 Web 界面上看到 6 个已注册 Agent 的状态 | 打开首页看板，确认 6 张卡片都渲染正确 |
| V-2 | 管理员可以创建新 Agent 并为其配置模型参数 | 创建一个测试 Agent，设置模型为 gpt-4o-mini，temperature 0.5 |
| V-3 | 管理员可以为 Agent 绑定和解绑 Skills | 为测试 Agent 绑定 llm_generate Skill，确认详情页显示 |
| V-4 | 发起一个导购培训任务后，可以在任务中心看到该任务 | 通过现有 API 创建课程和生成内容，在任务中心确认可见 |
| V-5 | 任务详情页可以看到 trace_id 关联的事件时间线 | 点击任务详情，确认事件按时间排列 |
| V-6 | 成本监控页可以看到按 Agent 和按模型的费用统计 | 确认有数据、计算正确 |
| V-7 | 事件日志页可以按 trace_id 搜索事件 | 输入一个已知 trace_id，确认返回关联事件 |
| V-8 | 管理员可以停用一个 Agent | 停用 experiment_analyst，确认状态变为 disabled |

### 10.2 技术验收

| 编号 | 验收项 | 验收方法 |
| --- | --- | --- |
| T-1 | 新增的 API 全部通过冒烟测试 | `pytest tests/test_office_api.py -v` 全绿 |
| T-2 | 新增表与现有表兼容，现有 API 不受影响 | `pytest tests/test_smoke.py -v` 全绿（不改动） |
| T-3 | 初始种子数据正确写入 | 查询 agents 表确认 6 条记录 |
| T-4 | cost_records 写入正确 | 执行一次培训内容生成，确认 cost_records 有新记录 |
| T-5 | WebSocket 事件推送可连接 | 用 wscat 连接 `/api/v1/office/ws/events`，发起任务后确认收到事件 |

---

## 11. 风险与缓解

| 风险 | 影响 | 缓解措施 |
| --- | --- | --- |
| Agent 能力层改造不及时，cost_records 没有数据 | 成本监控模块无法演示 | 阶段一先支持 Mock 成本数据写入，不依赖能力层改造 |
| 前端工程量大，React + Phaser 3 同时推进 | 延期 | MVP 阶段只用 React，Phaser 3 放到阶段三 |
| 现有 agent_events 没有写入 Agent 的运行事件 | 看板和事件日志为空 | 改造 Orchestrator 时同步增加事件写入 |
| 模型定价变化频繁 | 成本计算不准 | model_pricing 表支持随时更新，成本按记录时的定价计算 |

---

## 12. 术语表

| 术语 | 定义 |
| --- | --- |
| Agent | 一个可管理的 AI 工作实体，有名称、配置、状态和 Skills |
| Skill | Agent 可使用的一个具体能力（工具调用/API 调用/知识库访问） |
| 容器层 | AgentsOffice 平台本身，负责管理和可视化，不负责 Agent 的业务执行逻辑 |
| 能力层 | Agent 的业务执行逻辑，包含 LLM 调用、工作流编排、工具使用 |
| trace_id | 全链路追踪 ID，贯穿一次完整的业务请求，关联所有事件和审计记录 |
| slug | Agent 的代码级标识符，用于事件上报和系统内部引用 |
| cost_record | 一条 LLM 调用的成本记录，包含 token 数量和计算后的费用 |
