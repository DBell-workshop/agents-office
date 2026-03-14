# AgentsOffice 实现状态与规划

> 最后更新：2026-03-13

## 1. 整体架构

```
┌─────────────────────────────────────────────────────────┐
│               前端：Phaser 3 + React 19                  │
│  ┌──────────────────┐  ┌───────────────────────────────┐ │
│  │   Phaser Canvas   │  │       React Overlay          │ │
│  │  (全屏像素办公室)  │  │  AgentStatusBar（底部栏）     │ │
│  │  角色/寻路/动画    │  │  AgentConfigPanel（配置面板）  │ │
│  │  房间交互热区      │  │  ChatPanel（对话面板）        │ │
│  └────────┬─────────┘  └──────────┬────────────────────┘ │
│           └──── EventBus 通信 ────┘                      │
└───────────────────────────┬─────────────────────────────┘
                            │ HTTP / WebSocket
┌───────────────────────────┴─────────────────────────────┐
│              后端：FastAPI + PostgreSQL                   │
│  ┌──────────────┐ ┌──────────────┐ ┌─────────────────┐  │
│  │ office/       │ │ services/    │ │ db/             │  │
│  │ router.py     │ │ dispatcher   │ │ orm_models.py   │  │
│  │ store.py      │ │ llm_service  │ │ postgres_store  │  │
│  │ cost_engine   │ │ workflows    │ │                 │  │
│  └──────────────┘ └──────────────┘ └─────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## 2. 已完成功能

### 2.1 容器层后端 API（`/api/v1/office/`）

| API | 方法 | 说明 | 状态 |
|-----|------|------|------|
| `/chat` | POST | 用户对话入口，调度员路由 | ✅ 完成 |
| `/agents` | POST/GET | Agent CRUD | ✅ 完成 |
| `/agents/{id}` | GET/PUT | Agent 详情/更新 | ✅ 完成 |
| `/agents/{id}/status` | PATCH | Agent 状态变更 | ✅ 完成 |
| `/agent-config` | GET | 获取所有 Agent 完整定义 | ✅ 完成 |
| `/agent-config/{slug}` | PUT | 更新 Agent 配置（模型+身份） | ✅ 完成 |
| `/agent-config/{slug}/refine-prompt` | POST | AI 优化系统提示词 | ✅ 完成 |
| `/models` | GET | 可用模型列表（含可用性状态） | ✅ 完成 |
| `/skills` | POST/GET | Skills CRUD | ✅ 完成 |
| `/agents/{id}/skills/{id}` | POST/DELETE | Skill 绑定/解绑 | ✅ 完成 |
| `/costs/by-agent` | GET | 按 Agent 统计费用 | ✅ 完成 |
| `/costs/by-model` | GET | 按模型统计费用 | ✅ 完成 |
| `/costs/summary` | GET | 费用总览 | ✅ 完成 |
| `/tasks` | GET | 任务列表（支持筛选） | ✅ 完成 |
| `/tasks/{id}` | GET | 任务详情 | ✅ 完成 |
| `/events` | GET | 事件日志（支持筛选） | ✅ 完成 |

### 2.2 Agent 动态配置系统

**Phase A — 直接编辑（已完成）**

- **数据模型**：`model_config` JSONB 存 LLM 设置，`extra_metadata` JSONB 存身份定义
- **dispatcher 动态加载**：每次 dispatch 从 DB 加载 Agent 定义，与内置 `BUILTIN_AGENTS` 合并
- **前端配置面板**：3 标签页（身份定义 / 系统提示词 / 模型配置）
- **待命槽位**：3 个预留位，通过 UI 配置即可激活为真实 Agent
- **模型可用性**：后端检测各 provider API Key，前端显示可用/不可用状态

**Phase B — AI 辅助优化（已完成）**

- **后端 API**：`POST /agent-config/{slug}/refine-prompt`
- **Meta-Prompt 设计**：将用户自然语言描述转化为结构化 system prompt
  - 以「你是...」开头定义角色
  - Markdown 分节：职责、工作方式、回复风格、注意事项
  - 保留用户原始意图，模糊处标注推断
- **前端交互**：金色「AI 优化提示词」按钮，优化后自动填入编辑框，用户审阅后保存

### 2.3 前端可视化

| 组件 | 说明 | 状态 |
|------|------|------|
| Phaser 场景 | 像素办公室、角色系统、寻路 | ✅ 基础完成 |
| AgentStatusBar | 底部动态状态栏，显示所有 Agent 状态/token/工时 | ✅ 完成 |
| AgentConfigPanel | 3 标签页配置面板 + AI 优化 | ✅ 完成 |
| ChatPanel | 右侧对话面板 | ✅ 基础完成 |
| ReactOverlay | React ↔ Phaser 桥接层 | ✅ 完成 |

### 2.4 成本记录管线

```
dispatcher._run_agent() → _record_cost() → store.record_cost() → PostgreSQL cost_records
                                                                 ↓
                                           cost_engine.calculate_cost() → 费用计算
```

### 2.5 多模型支持

通过 LiteLLM 统一调用层（`app/services/llm_service.py`），支持：
- Google: Gemini 2.0 Flash, Gemini 2.5 Flash, Gemini 2.5 Pro
- Anthropic: Claude Sonnet 4, Claude Haiku 4.5
- OpenAI: GPT-4o, GPT-4o Mini, GPT-4 Turbo
- DeepSeek: DeepSeek V3, DeepSeek R1

当前仅配置 `GEMINI_API_KEY`，其余 provider 需在 `.env` 中配置对应 API Key。

## 3. 关键文件索引

### 后端
| 文件 | 职责 |
|------|------|
| `app/office/router.py` | 所有 AgentsOffice API 路由 |
| `app/office/store.py` | 数据持久化（Agent/Skill/Cost/Task/Event CRUD） |
| `app/office/cost_engine.py` | 成本计算引擎 + 模型定价表 |
| `app/office/models.py` | Pydantic 请求/响应模型 |
| `app/services/dispatcher.py` | 调度员实现，动态 Agent 加载 + Function Calling |
| `app/services/llm_service.py` | LiteLLM 统一调用层 |
| `app/db/orm_models.py` | SQLAlchemy ORM 模型 |
| `app/config.py` | 系统配置（API Keys、数据库 URL 等） |

### 前端
| 文件 | 职责 |
|------|------|
| `frontend/src/react/AgentStatusBar.tsx` | 底部 Agent 状态栏（动态加载） |
| `frontend/src/react/AgentConfigPanel.tsx` | Agent 配置面板（3 标签页 + AI 优化） |
| `frontend/src/react/ReactOverlay.tsx` | React 层入口（管理面板挂载/卸载） |
| `frontend/src/react/ChatPanel.tsx` | 右侧对话面板 |
| `frontend/src/shared/events/EventBus.ts` | 前端事件总线（Phaser ↔ React） |
| `frontend/src/phaser/` | Phaser 场景、角色、寻路 |

## 4. 规划中的 Agent 角色

### 已实现（内置）
1. **调度员**（dispatcher）— 任务路由、资源分配
2. **导购员**（shopping_guide）— 面向用户推荐
3. **理货员**（product_specialist）— 商品数据查询

### 已规划（待实现）
4. **数据工程师**（data_engineer）
   - 引导用户创建/连接数据库
   - 接收上传文件（照片/PDF/Excel/CSV），自动分析整理入库
   - 帮用户操作外部数据库
   - 面向非技术用户，引导式交互

5. **数据产品经理**（data_pm）
   - 与数据工程师协同，基于数据设计 BI 报表
   - 接收用户需求，分析确认后产出分析报告
   - 主动追问确认需求细节

6. **爬虫工程师**（web_scraper）
   - 根据用户需求抓取网站信息
   - 与数据工程师协同存储结构化数据
   - 主动提问引导用户明确目标和关键信息

### 远期可能
- 质检员 — 审核推荐质量
- 数据分析师 — 销售趋势分析
- 客服 — 售后退换货

## 5. 待开发事项

### P0（核心功能）
- [ ] WebSocket 实时事件推送（Agent 状态变更实时反映到前端）
- [ ] 数据工程师 Agent 实现（文件上传 + 数据库操作 Skills）
- [ ] 数据产品经理 Agent 实现（BI 报表 + 分析报告）
- [ ] 爬虫工程师 Agent 实现（OpenClaw 集成 + 结构化存储）
- [ ] Agent-to-Agent 通信机制（多 Agent 协作对话）

### P1（体验增强）
- [ ] Agent 间协作可视化（走到对方房间对话的动画）
- [ ] 多轮对话上下文管理（conversation_id 持久化）
- [ ] 成本趋势图（按时间的费用折线图）
- [ ] 任务重试功能

### P2（未来规划）
- [ ] 用户权限体系（多角色管理）
- [ ] Agent 模板市场
- [ ] 可视化工作流编辑器（拖拽式编排）
- [ ] 语音交互（TTS + ASR 集成）

## 6. 技术约定

### 后端代码规范
- `from __future__ import annotations`
- `ApiEnvelope` 统一响应格式，`make_id()` 生成 ID
- 路由不写业务逻辑，逻辑在 store/service 层
- 单例模式的 `office_store`（线程安全）
- `BackgroundTasks` 模式处理异步操作

### 前端通信约定
- EventBus 事件名用 `domain:action` 格式
- React 组件通过 EventBus 监听 Phaser 事件
- 配置保存后 emit `agent:config-updated` 触发状态栏刷新

### 数据模型约定
- `model_config` JSONB：LLM 相关配置（model_name, temperature, max_tokens）
- `extra_metadata` JSONB：身份和行为定义（system_prompt, role, display_name, color, active）
- 两个 JSONB 字段分离，避免频繁的 schema 迁移
