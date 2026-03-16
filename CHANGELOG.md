# Changelog

本项目遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范。

## [Unreleased]

### Added
- **Agent 生命周期管理**：通过 ➕ 按钮创建自定义 Agent（名称、角色、颜色、房间），最多 20 个
- **Agent 删除功能**：用户创建的 Agent 可在配置面板「身份定义」Tab 中删除（二次确认）
- **内置 Agent 保护**：7 个内置 Agent 禁止删除（前端隐藏按钮 + 后端 403）
- **Phaser 精灵动态管理**：创建/删除 Agent 时地图精灵实时同步
- **CI 工作流**：GitHub Actions 自动运行 TypeScript 检查 + Vite 构建 + pytest
- **社区文件**：CONTRIBUTING.md、Issue 模板（Bug/Feature）、PR 模板

### Changed
- README 定价改为完全免费
- agent-registry API 返回 `is_builtin` 字段
- .env.example 补充 DashScope API Key 配置

---

## [0.1.0] - 2026-03-15

首个公开版本。

### Added
- 像素风 RPG 办公室界面（Phaser 3 + React）
- 7 个 AI 数字员工：调度员、导购员、理货员、数据工程师、数据分析师、比价专员、平面设计师
- 调度员自动路由（LLM Function Calling）
- 群聊 / 私聊对话模式
- 跨平台智能比价 Skill（京东/淘宝/拼多多，LLM 语义分析 + 算法降级）
- Agent 配置面板（身份定义、系统提示词、模型配置）
- AI 优化提示词功能
- 商品数据导入 API + PostgreSQL 持久化
- 数据库管理面板（表结构、数据预览）
- Token 成本追踪（按 Agent / 按模型）
- 多 LLM 支持（Google Gemini、OpenAI、Anthropic、DeepSeek、阿里云百炼）
- BSL 1.1 许可证
