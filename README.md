<p align="center">
  <img src="docs/images/rpg-office-overview.png" width="800" alt="AgentsOffice RPG Interface" />
</p>

<h1 align="center">AgentsOffice - AI Digital Workforce Lab</h1>

<p align="center">
  <strong>不只是好看的像素办公室，是真正能干活的 AI 数字员工团队</strong>
</p>

<p align="center">
  <a href="https://github.com/DBell-workshop/ecommerce-ai-lab/stargazers"><img src="https://img.shields.io/github/stars/DBell-workshop/ecommerce-ai-lab?style=social" alt="Stars" /></a>
  <a href="https://github.com/DBell-workshop/ecommerce-ai-lab/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-BSL_1.1-blue" alt="License" /></a>
  <a href="https://github.com/DBell-workshop/ecommerce-ai-lab"><img src="https://img.shields.io/badge/python-3.11+-green" alt="Python" /></a>
  <a href="https://github.com/DBell-workshop/ecommerce-ai-lab"><img src="https://img.shields.io/badge/frontend-React%20%2B%20Phaser3-purple" alt="Frontend" /></a>
</p>

<p align="center">
  <a href="#features">功能</a> ·
  <a href="#quick-start">快速开始</a> ·
  <a href="#architecture">架构</a> ·
  <a href="#pricing">定价</a> ·
  <a href="LICENSE">许可证</a> ·
  <a href="#features">Features</a> ·
  <a href="#quick-start">Quick Start</a>
</p>

---

## What is AgentsOffice?

AgentsOffice 是一个 **电商 AI 数字员工实验室**。每个 AI Agent 都是一个有岗位、有技能、能协作的"数字员工"，在像素风 RPG 办公室里可视化地工作。

> 和其他"像素办公室"项目不同：**我们的 Agent 不只是会走来走去的小人，它们真的在干活。**

| 其他项目 | AgentsOffice |
|---------|-------------|
| 纯可视化看板，展示 Agent 状态 | **完整的 AI 业务平台**，Agent 有真实技能 |
| 需要外接其他 AI 工具才能工作 | **自带 LLM 语义分析**，开箱即用 |
| 单角色展示 | **7 个不同角色**，各有专长 |

---

<a id="features"></a>
## Features

### 🏢 像素风 RPG 办公室
基于 Phaser 游戏引擎构建的 2D 像素办公室，每个 Agent 有自己的工位、房间和动画。点击 Agent 可以和它对话。

### 🤖 7 个 AI 数字员工

| Agent | 角色 | 能力 |
|-------|------|------|
| 🔀 调度员 | 任务分配 | 自动分析需求，路由到合适的 Agent |
| 🛒 导购员 | 商品推荐 | 理解用户需求，推荐合适商品 |
| 💰 比价专员 | 跨平台比价 | **跨京东/淘宝/拼多多语义比价**，LLM 智能分析 |
| 📦 理货员 | 库存查询 | 商品数据查询、价格监控、规格统计 |
| 🔧 数据工程师 | 数据管理 | 文件上传、SQL 查询、数据库管理 |
| 📊 数据分析师 | 数据分析 | 数据可视化、成本分析、效率评估 |
| 🎨 平面设计师 | 视觉设计 | 海报生成、产品落地页、宣传素材 |

### 💡 核心场景：跨平台智能比价

```
用户输入 "小厨宝" → 比价专员搜索 3 个平台 → 找到 7 个商品
→ 用户勾选要对比的商品 → LLM 语义分析 → 生成比价报告卡片
```

<p align="center">
  <img src="docs/images/skill-search-results.png" width="700" alt="跨平台搜索结果" />
  <br/><em>跨平台搜索结果：京东/淘宝/拼多多实时商品数据</em>
</p>

<p align="center">
  <img src="docs/images/comparison-result.png" width="700" alt="LLM 语义比价结果" />
  <br/><em>LLM 智能比价结果卡片：价格对比 + 促销汇总 + 推荐建议</em>
</p>

- **不是简单的价格排序**，而是 LLM 语义理解（识别同款/近似款/不可比）
- 自动汇总各平台促销、优惠券、赠品信息
- 算法降级兜底：LLM 不可用时自动切换纯算法比价

### 🗄️ 商品数据管理
- 标准化商品数据导入 API（支持京东/淘宝/拼多多/抖音）
- PostgreSQL 持久化存储，JSONB 灵活字段
- 按平台、类目、关键词多维检索

### 💬 智能对话
- 群聊模式：调度员自动识别意图，分配给合适的 Agent
- 私聊模式：直接和特定 Agent 一对一交流
- Skill 自动触发：Agent 自动识别是否需要触发专业技能

---

<a id="quick-start"></a>
## Quick Start

### 环境要求
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose（用于 PostgreSQL）

### 1. 克隆项目

```bash
git clone https://github.com/DBell-workshop/ecommerce-ai-lab.git
cd ecommerce-ai-lab
```

### 2. 启动数据库

```bash
docker compose up -d
```

### 3. 启动后端

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

### 5. 打开浏览器

访问 **http://localhost:5173/static/office/**

你会看到像素风办公室，点击底部 Agent 状态栏开始体验！

### 环境变量

在 `.env` 中配置（参考 `.env.example`）：

```env
# LLM 配置（支持 OpenAI 兼容 API）
LLM_MODEL=qwen-plus
LLM_API_KEY=your-api-key

# 数据库
DATABASE_URL=postgresql://user:pass@localhost:5432/ecommerce_ai

# OpenClaw 采集（可选）
OPENCLAW_MODE=mock
```

---

<a id="architecture"></a>
## Architecture

```
┌─────────────────────────────────────────────┐
│                  Frontend                    │
│  Phaser RPG Engine + React Overlay + ChatBox │
│  (像素办公室 + Agent面板 + 对话框)             │
└────────────────────┬────────────────────────┘
                     │ SSE / REST
┌────────────────────▼────────────────────────┐
│              FastAPI Backend                  │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ AgentChat │  │  Skills  │  │ Product   │  │
│  │ (调度/私聊)│  │ (比价等) │  │ Import API│  │
│  └─────┬────┘  └─────┬────┘  └─────┬─────┘  │
│        │             │             │         │
│  ┌─────▼─────────────▼─────────────▼──────┐  │
│  │           Service Layer                 │  │
│  │  LLM Service / Comparison Workflow      │  │
│  │  Agent Runner / Skill Engine            │  │
│  └─────────────────┬──────────────────────┘  │
│                    │                         │
│  ┌─────────────────▼──────────────────────┐  │
│  │         PostgreSQL + SQLAlchemy         │  │
│  │    Products / Tasks / Agents Config     │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

**Tech Stack:**
- **Backend**: Python, FastAPI, SQLAlchemy, Pydantic
- **Frontend**: TypeScript, React, Phaser 3 (RPG engine)
- **AI**: LLM via OpenAI-compatible API (DashScope/Qwen, OpenAI, etc.)
- **Database**: PostgreSQL with JSONB
- **Infra**: Docker Compose

---

<a id="pricing"></a>
## Pricing

AgentsOffice 采用 **开放核心 (Open Core)** 模式：

| | 免费版 | 专业版 | 团队版 |
|--|--------|--------|--------|
| **Agent 数量** | 2 个（比价专员 + 导购员） | 全部 7 个 | 全部 + 自定义 |
| **RPG 办公室** | ✅ 完整体验 | ✅ | ✅ |
| **每日比价次数** | 10 次 | 无限 | 无限 |
| **数据导出** | - | ✅ CSV/JSON | ✅ |
| **API 接口** | - | - | ✅ |
| **多用户协作** | - | - | ✅ |
| **价格** | **免费** | **¥99/月** | **¥299/月** |

---

## Roadmap

- [x] 像素风 RPG 办公室界面
- [x] 7 个 Agent 角色定义 & 动态配置
- [x] 群聊调度 & 私聊对话
- [x] 跨平台商品比价（LLM 语义分析 + 算法降级）
- [x] 商品数据导入 & PostgreSQL 持久化
- [ ] 理货员商品查询 Skill
- [ ] 导购员智能推荐 Skill
- [ ] 比价结果历史存储 & 回看
- [ ] 分享卡片生成（带品牌水印）
- [ ] 移动端适配
- [ ] Token 充值 & 用量管理
- [ ] 自定义 Agent 角色

---

## Contributing

欢迎贡献！请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解如何参与。

- 提交 Issue 反馈 Bug 或建议功能
- 提交 PR 贡献代码
- 加入社群讨论（微信群/Discord）

---

## License

本项目采用 [Business Source License 1.1](LICENSE) 许可。

**简单说：**
- ✅ 可以学习、研究、个人使用
- ✅ 可以用于内部评估和测试
- ❌ 未经授权不得商业化使用或提供商业服务
- 📅 4 年后自动转为 Apache 2.0 开源许可

详见 [LICENSE](LICENSE) 文件。

---

<p align="center">
  <sub>Built with ❤️ by the AgentsOffice Team</sub>
</p>
