<p align="center">
  <a href="README_zh-CN.md">简体中文</a> ·
  <a href="README_zh-TW.md">繁體中文</a> ·
  <a href="README.md">English</a> ·
  <a href="README_ja.md">日本語</a>
</p>

<p align="center">
  <img src="docs/demo.gif" width="800" alt="AgentsOffice Demo" />
</p>

<h1 align="center">AgentsOffice</h1>

<p align="center">
  <strong>给你的 AI 团队一间看得见的办公室</strong>
</p>

<p align="center">
  <a href="https://github.com/DBell-workshop/agents-office/stargazers"><img src="https://img.shields.io/github/stars/DBell-workshop/agents-office?style=social" alt="Stars" /></a>
  <a href="https://github.com/DBell-workshop/agents-office/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-BSL_1.1-blue" alt="License" /></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.11+-green" alt="Python" /></a>
  <a href="#"><img src="https://img.shields.io/badge/frontend-React%20%2B%20Phaser3-purple" alt="Frontend" /></a>
</p>

<p align="center">
  <a href="#use-cases">应用场景</a> ·
  <a href="#features">功能</a> ·
  <a href="#quick-start">快速开始</a> ·
  <a href="#architecture">架构</a> ·
  <a href="#support">支持我们</a> ·
  <a href="LICENSE">License</a>
</p>

---

## What is AgentsOffice?

AgentsOffice 是一个**多 Agent 协作工作台**，用像素风 RPG 办公室让你的 AI 团队"可视化地上班"。

你定义角色、写提示词、装载技能，5 分钟就能搭建一个属于你的 AI 数字员工团队。

> **和其他"像素办公室"项目不同：我们的 Agent 不只是会走来走去的小人，它们真的在干活。**

| 其他项目 | AgentsOffice |
|---------|-------------|
| 纯可视化看板，展示 Agent 状态 | **完整的 AI 工作台**，Agent 有真实技能 |
| 需要外接其他 AI 工具才能工作 | **自带 LLM 对话 + Skill 引擎**，开箱即用 |
| 单角色展示 | **多角色协作**，调度员自动分配任务 |
| 只能看 | **能聊天、能触发技能、能分析数据** |

---

<a id="use-cases"></a>
## Use Cases — 不限行业，你定义角色就是你的团队

> 以下是一些真实应用场景，5 分钟就能配好。

### 📝 自媒体内容工坊
> 一个人做号？给自己配个内容团队。

**选题策划师** 追热点找选题 + **内容编辑** 写初稿改稿 + **标题专家** 生成10个标题供你选。每天打开办公室，把想写的方向丢进群聊，三个员工自动分工，你只管最后拍板。

### 🎯 产品设计团队
> 调研、竞品、PRD，不再当"人肉中间件"。

**用户研究员** 整理反馈归纳需求 + **竞品分析师** 拆解竞品功能策略 + **PRD 助手** 自动生成需求文档。分析结论自动流转，不用复制粘贴。

### 📚 教育辅导站
> 给学生配一个 AI 教学团队。

**知识讲解员** 用通俗语言讲概念 + **出题教练** 根据水平出练习题 + **学习规划师** 根据错题调整复习计划。像素教室里的 AI 老师，学习仪式感拉满。

### 🎧 客服训练营
> 新人培训，不用老员工带。

**模拟顾客** 扮演各种买家 + **质检主管** 实时评估回复打分 + **话术教练** 每轮对话给改进建议。训练-评估-改进闭环，7x24 小时可练。

### 💡 创业智囊团
> 请不起咨询公司？配个 AI 顾问团。

**市场分析师** 研究行业趋势 + **商业顾问** 梳理盈利路径 + **增长专家** 设计获客策略。把商业计划书丢进群聊，三个顾问从不同角度给你反馈。每月不到一顿火锅的钱。

### 💻 独立开发者工作室
> 技术之外的活，交给 AI 同事。

**产品助手** 梳理需求写用户故事 + **代码审查员** review 代码找 bug + **运营文案** 写发布日志和推广文案。你专注写代码，其余交给团队。

---

| 场景 | 核心价值 | Agent 数量 |
|------|---------|-----------|
| 自媒体工坊 | 一人产出三人效率 | 3 |
| 产品设计 | 调研到文档自动流转 | 3 |
| 教育辅导 | AI 教学团队 | 3 |
| 客服训练 | 训练-评估-改进闭环 | 3 |
| 创业智囊 | 平价咨询团队 | 3 |
| 独立开发 | 技术之外全覆盖 | 3 |

**想到了自己的场景？** 打开 AgentsOffice，创建你的 Agent，写上提示词，就能开工。

---

<a id="features"></a>
## Features

### 🏢 像素风 RPG 办公室
基于 Phaser 3 游戏引擎构建的 2D 像素办公室。每个 Agent 有自己的工位、房间和动画。点击 Agent 就能和它对话。

### 🤖 灵活的 Agent 系统
- **不限数量**：自由创建任意多个 Agent，打造你的专属团队
- **通过 UI 配置**：角色名、提示词、模型、技能，不用改代码
- **20 个预制像素角色**可选，每个 Agent 都有独立形象

### 💬 智能对话
- **群聊模式**：调度员自动识别意图，分配给合适的 Agent
- **私聊模式**：直接和特定 Agent 一对一深入交流
- **Skill 自动触发**：Agent 识别到需要技能时自动执行

### 🔌 Skill 插件系统
- 继承 `BaseSkill` 即可开发自定义技能
- Skill 支持多步交互（搜索 → 选择 → 分析）
- SSE 实时推送执行进度

### 🗄️ 数据管理
- 数据工程师 Agent 可帮你上传 CSV、建表、查询数据
- PostgreSQL 持久化，JSONB 灵活字段
- 支持连接外部数据库

### 🧮 成本追踪
- 每次 LLM 调用自动记录 Token 用量和费用
- 按 Agent / 按模型维度查看成本报表
- 内置主流模型定价（OpenAI、Claude、Gemini、DeepSeek）

---

<a id="quick-start"></a>
## Quick Start

### 一键启动（推荐）

只需要安装 [Docker](https://www.docker.com/products/docker-desktop/)，然后：

```bash
git clone https://github.com/DBell-workshop/agents-office.git
cd agents-office
cp .env.example .env   # 编辑 .env，至少填入一个 LLM API Key
docker compose up -d
```

打开 **http://localhost:8001/static/office/** 即可使用。

### 开发模式

如果你想修改代码（支持热更新）：

```bash
# 数据库
docker compose up postgres -d

# 后端
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001

# 前端（另一个终端）
cd frontend && npm install && npm run dev
```

开发模式访问 **http://localhost:5174/static/office/**

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
│  │ AgentChat │  │  Skills  │  │  Data     │  │
│  │ (调度/私聊)│  │  Engine  │  │  Manager  │  │
│  └─────┬────┘  └─────┬────┘  └─────┬─────┘  │
│        │             │             │         │
│  ┌─────▼─────────────▼─────────────▼──────┐  │
│  │           Service Layer                 │  │
│  │  LLM Service / Agent Runner             │  │
│  │  Skill Engine / Cost Tracker            │  │
│  └─────────────────┬──────────────────────┘  │
│                    │                         │
│  ┌─────────────────▼──────────────────────┐  │
│  │         PostgreSQL + SQLAlchemy         │  │
│  │    Agents / Skills / Tasks / Costs      │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

**Tech Stack:**
- **Backend**: Python, FastAPI, SQLAlchemy, Pydantic
- **Frontend**: TypeScript, React, Phaser 3 (RPG engine)
- **AI**: LLM via OpenAI-compatible API (GPT, Claude, Gemini, Qwen, DeepSeek)
- **Database**: PostgreSQL with JSONB
- **Infra**: Docker Compose

---

<a id="support"></a>
## Support This Project

AgentsOffice 是一个由社区驱动的开源项目。如果觉得有用，请考虑支持我们：

<p align="center">

**⭐ [Star this repo](https://github.com/DBell-workshop/agents-office)** — 最简单的支持方式

**💳 PayPal 打赏** — 扫码支持我们<br/>
<img src="docs/paypal-qr.png" width="180" alt="PayPal QR" />

</p>

> 你的每一个 Star 和赞助都是我们持续开发的动力！

---

## Roadmap

- [x] 像素风 RPG 办公室界面
- [x] Agent 动态配置（UI 面板）
- [x] 群聊调度 & 私聊对话
- [x] Skill 插件引擎
- [x] 数据工程师（文件上传、建表、SQL查询）
- [x] LLM 成本追踪
- [ ] 更多预制 Skill 模板
- [ ] Agent 状态动画（工作 → 敲键盘，空闲 → 喝咖啡）
- [ ] 移动端适配
- [ ] Token 充值 & 用量管理
- [ ] Skill 市场（社区共享）

---

## Community

加入社区，交流想法、提问、分享你的 Agent 配置：

<p align="center">
  <a href="https://discord.gg/3Cpe5H6m"><img src="https://img.shields.io/badge/Discord-Join%20Server-5865F2?logo=discord&logoColor=white" alt="Discord" /></a>
</p>

<p align="center">
  <strong>微信群</strong>（扫码加入，7天有效期后请到 Discussions 获取最新二维码）<br/>
  <img src="docs/wechat-qr.jpg" width="200" alt="WeChat Group QR" />
</p>

---

## Contributing

欢迎贡献！

- 提交 Issue 反馈 Bug 或建议功能
- 提交 PR 贡献代码
- 开发自定义 Skill 并分享给社区
- 在 [Discussions](https://github.com/DBell-workshop/agents-office/discussions) 交流想法

---

## License

本项目采用 [Business Source License 1.1](LICENSE)。

- ✅ 个人使用、学习、研究、内部评估
- ❌ 未经授权不得商业化使用
- 📅 2030 年自动转为 Apache 2.0 开源

详见 [LICENSE](LICENSE) 文件。

---

<p align="center">
  <sub>Built with ❤️ by the AgentsOffice Team</sub>
</p>
