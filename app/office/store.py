"""AgentsOffice 容器层数据操作 -- agents, skills, cost_records 的 CRUD。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func as sa_func
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.db.engine import build_session_factory
from app.db.orm_models import (
    AgentEventRow,
    AgentRow,
    AgentSkillRow,
    ChatMessageRow,
    ConversationRow,
    CostRecordRow,
    ModelPricingRow,
    ProductRow,
    SkillRow,
    TaskRow,
)
from app.models import now_iso


def _dt_to_iso(val: Any) -> str:
    """将数据库返回的 datetime 转为 ISO 字符串。"""
    if val is None:
        return now_iso()
    if isinstance(val, str):
        return val
    return val.isoformat()


class OfficeStore:
    """AgentsOffice 容器层 Store -- 管理 agents, skills, cost_records 的 CRUD。"""

    def __init__(self, database_url: str) -> None:
        self.SessionFactory = build_session_factory(database_url)

    # ================================================================
    # Agent CRUD
    # ================================================================

    def create_agent(self, agent_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        with self.SessionFactory() as session:
            row = AgentRow(
                agent_id=agent_id,
                name=data["name"],
                slug=data["slug"],
                description=data.get("description"),
                agent_type=data.get("agent_type", "general"),
                status="idle",
                model_config=data.get("model_config", {}),
                extra_metadata=data.get("metadata", {}),
            )
            session.add(row)
            session.commit()
            return self._agent_row_to_dict(row)

    def list_agents(
        self,
        status: Optional[str] = None,
        agent_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        with self.SessionFactory() as session:
            q = session.query(AgentRow)
            if status:
                q = q.filter(AgentRow.status == status)
            if agent_type:
                q = q.filter(AgentRow.agent_type == agent_type)
            q = q.order_by(AgentRow.created_at)
            return [self._agent_row_to_dict(r) for r in q.all()]

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        with self.SessionFactory() as session:
            row = session.get(AgentRow, agent_id)
            if row is None:
                return None
            return self._agent_row_to_dict(row)

    def update_agent(self, agent_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with self.SessionFactory() as session:
            row = session.get(AgentRow, agent_id)
            if row is None:
                return None
            if "name" in data and data["name"] is not None:
                row.name = data["name"]
            if "description" in data and data["description"] is not None:
                row.description = data["description"]
            if "agent_type" in data and data["agent_type"] is not None:
                row.agent_type = data["agent_type"]
            if "model_config" in data and data["model_config"] is not None:
                row.model_config = data["model_config"]
            if "metadata" in data and data["metadata"] is not None:
                row.extra_metadata = data["metadata"]
            session.commit()
            return self._agent_row_to_dict(row)

    def update_agent_status(
        self,
        agent_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        with self.SessionFactory() as session:
            row = session.get(AgentRow, agent_id)
            if row is None:
                return None
            row.status = status
            row.error_message = error_message
            if status == "running":
                row.last_active_at = datetime.now(timezone.utc)
            session.commit()
            return self._agent_row_to_dict(row)

    # ================================================================
    # Agent 详情（含 skills、最近事件、累计成本）
    # ================================================================

    def get_agent_detail(self, agent_id: str) -> Optional[Dict[str, Any]]:
        with self.SessionFactory() as session:
            row = session.get(AgentRow, agent_id)
            if row is None:
                return None
            agent_dict = self._agent_row_to_dict(row)

            # 绑定的 skills
            skill_rows = (
                session.query(SkillRow)
                .join(AgentSkillRow, AgentSkillRow.skill_id == SkillRow.skill_id)
                .filter(AgentSkillRow.agent_id == agent_id)
                .all()
            )
            agent_dict["skills"] = [self._skill_row_to_dict(s) for s in skill_rows]

            # 最近 20 条事件（通过 slug 关联 agent_events）
            events = (
                session.query(AgentEventRow)
                .filter(AgentEventRow.agent_name == row.slug)
                .order_by(AgentEventRow.created_at.desc())
                .limit(20)
                .all()
            )
            agent_dict["recent_events"] = [self._event_row_to_dict(e) for e in events]

            # 累计成本
            total = (
                session.query(sa_func.coalesce(sa_func.sum(CostRecordRow.total_cost), 0))
                .filter(CostRecordRow.agent_id == agent_id)
                .scalar()
            )
            agent_dict["total_cost"] = float(total) if total else 0.0

            return agent_dict

    # ================================================================
    # Skill CRUD
    # ================================================================

    def create_skill(self, skill_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        with self.SessionFactory() as session:
            row = SkillRow(
                skill_id=skill_id,
                name=data["name"],
                display_name=data["display_name"],
                description=data.get("description"),
                skill_type=data.get("skill_type", "tool"),
                endpoint=data.get("endpoint"),
                config=data.get("config", {}),
            )
            session.add(row)
            session.commit()
            return self._skill_row_to_dict(row)

    def list_skills(
        self,
        skill_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        with self.SessionFactory() as session:
            q = session.query(SkillRow)
            if skill_type:
                q = q.filter(SkillRow.skill_type == skill_type)
            if status:
                q = q.filter(SkillRow.status == status)
            q = q.order_by(SkillRow.created_at)
            return [self._skill_row_to_dict(r) for r in q.all()]

    # ================================================================
    # Agent-Skill 绑定/解绑
    # ================================================================

    def bind_skill(self, agent_id: str, skill_id: str, config: Optional[Dict] = None) -> bool:
        with self.SessionFactory() as session:
            # 检查 agent 和 skill 是否存在
            agent = session.get(AgentRow, agent_id)
            skill = session.get(SkillRow, skill_id)
            if agent is None or skill is None:
                return False
            existing = session.get(AgentSkillRow, (agent_id, skill_id))
            if existing is not None:
                return True  # 已绑定
            row = AgentSkillRow(
                agent_id=agent_id,
                skill_id=skill_id,
                config=config or {},
            )
            session.add(row)
            session.commit()
            return True

    def unbind_skill(self, agent_id: str, skill_id: str) -> bool:
        with self.SessionFactory() as session:
            row = session.get(AgentSkillRow, (agent_id, skill_id))
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True

    # ================================================================
    # Per-Agent 模型配置
    # ================================================================

    def get_agent_model_configs(self) -> Dict[str, Dict[str, str]]:
        """获取所有 Agent 的模型配置。返回 {agent_slug: {model_name, api_base, api_key}}。"""
        with self.SessionFactory() as session:
            rows = session.query(AgentRow).all()
            result: Dict[str, Dict[str, str]] = {}
            for row in rows:
                cfg = row.model_config or {}
                if cfg.get("model_name") or cfg.get("api_base"):
                    result[row.slug] = {
                        "model_name": cfg.get("model_name", ""),
                        "api_base": cfg.get("api_base", ""),
                        "api_key": cfg.get("api_key", ""),
                    }
            return result

    def get_all_agent_configs(self) -> Dict[str, Dict[str, Any]]:
        """获取所有 Agent 的完整定义（模型配置 + 身份/行为定义）。"""
        with self.SessionFactory() as session:
            rows = session.query(AgentRow).all()
            result = {}
            for row in rows:
                cfg = row.model_config or {}
                meta = row.extra_metadata or {}
                result[row.slug] = {
                    # 模型配置
                    "model_name": cfg.get("model_name", ""),
                    "temperature": cfg.get("temperature", 0.7),
                    "max_tokens": cfg.get("max_tokens", 2048),
                    "api_base": cfg.get("api_base", ""),
                    "api_key": cfg.get("api_key", ""),
                    # 身份定义
                    "display_name": meta.get("display_name", row.name),
                    "role": meta.get("role", row.description or ""),
                    "system_prompt": meta.get("system_prompt", ""),
                    "color": meta.get("color", ""),
                    "active": meta.get("active", False),
                }
            return result

    def update_agent_config_by_slug(
        self, slug: str, config: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """按 slug 更新 Agent 的完整配置（模型 + 身份/行为）。如果不存在则自动创建。"""
        from app.models import make_id

        # 分离模型配置和身份配置
        model_fields = {"model_name", "temperature", "max_tokens", "api_base", "api_key"}
        identity_fields = {"display_name", "role", "system_prompt", "color", "active"}

        model_cfg = {k: v for k, v in config.items() if k in model_fields}
        identity_cfg = {k: v for k, v in config.items() if k in identity_fields}

        with self.SessionFactory() as session:
            row = session.query(AgentRow).filter(AgentRow.slug == slug).first()
            if row is None:
                row = AgentRow(
                    agent_id=make_id("agt"),
                    name=identity_cfg.get("display_name", slug),
                    slug=slug,
                    description=identity_cfg.get("role", ""),
                    agent_type="general",
                    status="idle",
                    model_config=model_cfg,
                    extra_metadata=identity_cfg,
                )
                session.add(row)
            else:
                # 合并更新 model_config
                if model_cfg:
                    existing_mc = row.model_config or {}
                    existing_mc.update(model_cfg)
                    row.model_config = existing_mc
                # 合并更新 extra_metadata（身份信息）
                if identity_cfg:
                    existing_meta = row.extra_metadata or {}
                    existing_meta.update(identity_cfg)
                    row.extra_metadata = existing_meta
                    # 同步 name 和 description 列
                    if "display_name" in identity_cfg:
                        row.name = identity_cfg["display_name"]
                    if "role" in identity_cfg:
                        row.description = identity_cfg["role"]
            session.commit()
            return self._agent_row_to_dict(row)

    def get_active_agent_definitions(self) -> List[Dict[str, Any]]:
        """获取所有活跃 Agent 的定义，供调度员动态构建路由使用。"""
        with self.SessionFactory() as session:
            rows = session.query(AgentRow).all()
            result = []
            for row in rows:
                meta = row.extra_metadata or {}
                if not meta.get("active", False):
                    continue
                cfg = row.model_config or {}
                result.append({
                    "slug": row.slug,
                    "display_name": meta.get("display_name", row.name),
                    "role": meta.get("role", row.description or ""),
                    "system_prompt": meta.get("system_prompt", ""),
                    "color": meta.get("color", ""),
                    "model_name": cfg.get("model_name", ""),
                    "temperature": cfg.get("temperature", 0.7),
                    "max_tokens": cfg.get("max_tokens", 2048),
                    "room_id": meta.get("room_id", "workspace"),
                    "phaser_agent_id": meta.get("phaser_agent_id", ""),
                })
            return result

    # ================================================================
    # 可用模型列表
    # ================================================================

    def list_models(self) -> List[Dict[str, Any]]:
        """返回所有活跃模型及其定价信息，供前端配置面板使用。"""
        from app.office.cost_engine import get_pricing_list
        with self.SessionFactory() as session:
            return get_pricing_list(session)

    # ================================================================
    # 成本记录写入
    # ================================================================

    def record_cost(
        self,
        agent_slug: str,
        trace_id: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        duration_ms: Optional[int] = None,
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """将一次 LLM 调用的 token 用量和费用写入 cost_records 表。"""
        from app.office.cost_engine import calculate_cost

        with self.SessionFactory() as session:
            input_cost, output_cost, total_cost = calculate_cost(
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                session=session,
            )
            row = CostRecordRow(
                agent_id=agent_id,
                agent_slug=agent_slug,
                task_id=task_id,
                trace_id=trace_id,
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                input_cost=input_cost,
                output_cost=output_cost,
                total_cost=total_cost,
                duration_ms=duration_ms,
                extra_metadata=metadata or {},
            )
            session.add(row)
            session.commit()

    # ================================================================
    # 成本查询
    # ================================================================

    def costs_by_agent(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        with self.SessionFactory() as session:
            q = session.query(
                CostRecordRow.agent_id,
                CostRecordRow.agent_slug,
                sa_func.sum(CostRecordRow.input_tokens).label("total_input_tokens"),
                sa_func.sum(CostRecordRow.output_tokens).label("total_output_tokens"),
                sa_func.sum(CostRecordRow.total_tokens).label("total_tokens"),
                sa_func.sum(CostRecordRow.total_cost).label("total_cost"),
                sa_func.count().label("call_count"),
            )
            q = self._apply_time_filter(q, CostRecordRow.created_at, start, end)
            q = q.group_by(CostRecordRow.agent_id, CostRecordRow.agent_slug)
            q = q.order_by(sa_func.sum(CostRecordRow.total_cost).desc())
            results = []
            for row in q.all():
                # 尝试获取 agent 名称
                agent_name = None
                if row.agent_id:
                    agent_row = session.get(AgentRow, row.agent_id)
                    if agent_row:
                        agent_name = agent_row.name
                results.append({
                    "agent_id": row.agent_id,
                    "agent_slug": row.agent_slug,
                    "agent_name": agent_name,
                    "total_input_tokens": int(row.total_input_tokens or 0),
                    "total_output_tokens": int(row.total_output_tokens or 0),
                    "total_tokens": int(row.total_tokens or 0),
                    "total_cost": float(row.total_cost or 0),
                    "call_count": int(row.call_count or 0),
                })
            return results

    def costs_by_model(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        with self.SessionFactory() as session:
            q = session.query(
                CostRecordRow.model_name,
                sa_func.sum(CostRecordRow.input_tokens).label("total_input_tokens"),
                sa_func.sum(CostRecordRow.output_tokens).label("total_output_tokens"),
                sa_func.sum(CostRecordRow.total_tokens).label("total_tokens"),
                sa_func.sum(CostRecordRow.total_cost).label("total_cost"),
                sa_func.count().label("call_count"),
            )
            q = self._apply_time_filter(q, CostRecordRow.created_at, start, end)
            q = q.group_by(CostRecordRow.model_name)
            q = q.order_by(sa_func.sum(CostRecordRow.total_cost).desc())
            return [
                {
                    "model_name": row.model_name,
                    "total_input_tokens": int(row.total_input_tokens or 0),
                    "total_output_tokens": int(row.total_output_tokens or 0),
                    "total_tokens": int(row.total_tokens or 0),
                    "total_cost": float(row.total_cost or 0),
                    "call_count": int(row.call_count or 0),
                }
                for row in q.all()
            ]

    def cost_summary(self) -> Dict[str, Any]:
        """返回今日、本周、本月的费用总览。"""
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=now.weekday())
        month_start = today_start.replace(day=1)

        return {
            "today": self._cost_summary_for_period("today", today_start, now),
            "this_week": self._cost_summary_for_period("this_week", week_start, now),
            "this_month": self._cost_summary_for_period("this_month", month_start, now),
        }

    def _cost_summary_for_period(
        self,
        period: str,
        start: datetime,
        end: datetime,
    ) -> Dict[str, Any]:
        with self.SessionFactory() as session:
            row = (
                session.query(
                    sa_func.coalesce(sa_func.sum(CostRecordRow.total_cost), 0).label("total_cost"),
                    sa_func.coalesce(sa_func.sum(CostRecordRow.total_tokens), 0).label("total_tokens"),
                    sa_func.count().label("call_count"),
                )
                .filter(CostRecordRow.created_at >= start)
                .filter(CostRecordRow.created_at <= end)
                .one()
            )
            return {
                "period": period,
                "total_cost": float(row.total_cost),
                "total_tokens": int(row.total_tokens),
                "call_count": int(row.call_count),
            }

    # ================================================================
    # 任务查询（复用现有 tasks 表）
    # ================================================================

    def list_tasks(
        self,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        agent_slug: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        with self.SessionFactory() as session:
            q = session.query(TaskRow)
            if status:
                q = q.filter(TaskRow.status == status)
            if task_type:
                q = q.filter(TaskRow.task_type == task_type)
            if agent_slug:
                q = q.filter(TaskRow.agent_slug == agent_slug)
            q = q.order_by(TaskRow.created_at.desc()).offset(offset).limit(limit)
            return [self._task_row_to_dict(r) for r in q.all()]

    def get_task_detail(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self.SessionFactory() as session:
            row = session.get(TaskRow, task_id)
            if row is None:
                return None
            task_dict = self._task_row_to_dict(row)
            task_dict["input"] = getattr(row, "input") or {}
            task_dict["output"] = row.output
            task_dict["error"] = row.error

            # 关联事件时间线（通过 trace_id）
            events = (
                session.query(AgentEventRow)
                .filter(AgentEventRow.trace_id == row.trace_id)
                .order_by(AgentEventRow.created_at)
                .all()
            )
            task_dict["events"] = [self._event_row_to_dict(e) for e in events]
            return task_dict

    # ================================================================
    # 事件查询（复用现有 agent_events 表）
    # ================================================================

    def list_events(
        self,
        agent_name: Optional[str] = None,
        event_type: Optional[str] = None,
        trace_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        with self.SessionFactory() as session:
            q = session.query(AgentEventRow)
            if agent_name:
                q = q.filter(AgentEventRow.agent_name == agent_name)
            if event_type:
                q = q.filter(AgentEventRow.event_type == event_type)
            if trace_id:
                q = q.filter(AgentEventRow.trace_id == trace_id)
            q = q.order_by(AgentEventRow.created_at.desc()).offset(offset).limit(limit)
            return [self._event_row_to_dict(r) for r in q.all()]

    # ================================================================
    # Conversation & ChatMessage CRUD
    # ================================================================

    def create_conversation(self, conversation_id: str, title: str = "") -> Dict[str, Any]:
        with self.SessionFactory() as session:
            row = ConversationRow(conversation_id=conversation_id, title=title)
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._conversation_row_to_dict(row)

    def list_conversations(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        with self.SessionFactory() as session:
            q = (
                session.query(ConversationRow)
                .filter(ConversationRow.status == "active")
                .order_by(ConversationRow.updated_at.desc())
                .offset(offset)
                .limit(limit)
            )
            results = []
            for row in q.all():
                d = self._conversation_row_to_dict(row)
                # 附带消息数量和最后一条消息预览
                msg_count = (
                    session.query(sa_func.count(ChatMessageRow.message_id))
                    .filter(ChatMessageRow.conversation_id == row.conversation_id)
                    .scalar()
                ) or 0
                last_msg = (
                    session.query(ChatMessageRow)
                    .filter(ChatMessageRow.conversation_id == row.conversation_id)
                    .order_by(ChatMessageRow.created_at.desc())
                    .first()
                )
                d["message_count"] = msg_count
                d["last_message"] = last_msg.content[:80] if last_msg else ""
                results.append(d)
            return results

    def get_conversation_messages(
        self, conversation_id: str, limit: int = 200, offset: int = 0,
    ) -> Optional[Dict[str, Any]]:
        with self.SessionFactory() as session:
            conv = session.get(ConversationRow, conversation_id)
            if not conv:
                return None
            msgs = (
                session.query(ChatMessageRow)
                .filter(ChatMessageRow.conversation_id == conversation_id)
                .order_by(ChatMessageRow.created_at.asc())
                .offset(offset)
                .limit(limit)
                .all()
            )
            return {
                **self._conversation_row_to_dict(conv),
                "messages": [self._chat_message_row_to_dict(m) for m in msgs],
            }

    def add_chat_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        agent_slug: Optional[str] = None,
        agent_name: Optional[str] = None,
        message_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        with self.SessionFactory() as session:
            row = ChatMessageRow(
                conversation_id=conversation_id,
                role=role,
                content=content,
                agent_slug=agent_slug,
                agent_name=agent_name,
                message_type=message_type,
                extra_metadata=metadata or {},
            )
            session.add(row)
            # 更新会话的 updated_at
            conv = session.get(ConversationRow, conversation_id)
            if conv:
                conv.updated_at = datetime.now(timezone.utc)
                # 如果是第一条用户消息且标题为空，用消息内容作标题
                if not conv.title and role == "user":
                    conv.title = content[:50]
            session.commit()
            session.refresh(row)
            return self._chat_message_row_to_dict(row)

    def update_conversation(self, conversation_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with self.SessionFactory() as session:
            conv = session.get(ConversationRow, conversation_id)
            if not conv:
                return None
            if "title" in data:
                conv.title = data["title"]
            if "status" in data:
                conv.status = data["status"]
            conv.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(conv)
            return self._conversation_row_to_dict(conv)

    def delete_conversation(self, conversation_id: str) -> bool:
        with self.SessionFactory() as session:
            conv = session.get(ConversationRow, conversation_id)
            if not conv:
                return False
            conv.status = "deleted"
            conv.updated_at = datetime.now(timezone.utc)
            session.commit()
            return True

    @staticmethod
    def _conversation_row_to_dict(row: ConversationRow) -> Dict[str, Any]:
        return {
            "conversation_id": row.conversation_id,
            "title": row.title or "",
            "status": row.status,
            "created_at": _dt_to_iso(row.created_at),
            "updated_at": _dt_to_iso(row.updated_at),
        }

    @staticmethod
    def _chat_message_row_to_dict(row: ChatMessageRow) -> Dict[str, Any]:
        return {
            "message_id": row.message_id,
            "conversation_id": row.conversation_id,
            "role": row.role,
            "agent_slug": row.agent_slug,
            "agent_name": row.agent_name,
            "content": row.content,
            "message_type": row.message_type,
            "metadata": row.extra_metadata or {},
            "created_at": _dt_to_iso(row.created_at),
        }

    # ================================================================
    # Product CRUD — 商品数据持久化
    # ================================================================

    def save_products(
        self,
        products: List[Dict[str, Any]],
        source: str,
        batch_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """批量导入商品数据，已存在的 product_id+platform 组合会更新。

        Args:
            products: ProductImportItem 转换后的 dict 列表
            source: 数据来源标识
            batch_id: 外部批次号

        Returns:
            导入结果列表 [{product_id, platform, name, status: "created"|"updated"}]
        """
        results = []
        with self.SessionFactory() as session:
            for item in products:
                # 用 platform + product_id 构造唯一 key
                pk = f"{item['platform']}_{item['product_id']}"
                existing = session.get(ProductRow, pk)

                # 将完整数据打包为 raw_data 和 attributes
                raw_data = {
                    "source": source,
                    "batch_id": batch_id,
                    "price": item.get("price"),
                    "original_price": item.get("original_price"),
                    "url": item.get("url"),
                    "shop_name": item.get("shop_name"),
                    "images": item.get("images", []),
                    "video_url": item.get("video_url"),
                    "specs": item.get("specs", []),
                    "description": item.get("description"),
                    "promotions": item.get("promotions", []),
                    "rating": item.get("rating"),
                    "review_count": item.get("review_count"),
                    "sales_count": item.get("sales_count"),
                    "extra": item.get("extra", {}),
                }
                attributes = {
                    "specs": item.get("specs", []),
                    "promotions": item.get("promotions", []),
                }

                if existing:
                    existing.name = item["name"]
                    existing.brand = item.get("brand")
                    existing.category = item.get("category")
                    existing.source_url = item.get("url")
                    existing.attributes = attributes
                    existing.raw_data = raw_data
                    status = "updated"
                else:
                    row = ProductRow(
                        product_id=pk,
                        sku=item["product_id"],
                        name=item["name"],
                        category=item.get("category"),
                        brand=item.get("brand"),
                        source_platform=item["platform"],
                        source_url=item.get("url"),
                        attributes=attributes,
                        raw_data=raw_data,
                    )
                    session.add(row)
                    status = "created"

                results.append({
                    "product_id": item["product_id"],
                    "platform": item["platform"],
                    "name": item["name"],
                    "price": item.get("price"),
                    "status": status,
                })
            session.commit()
        return results

    def get_product(self, product_id: str) -> Optional[Dict[str, Any]]:
        """按主键查询商品。"""
        with self.SessionFactory() as session:
            row = session.get(ProductRow, product_id)
            if row is None:
                return None
            return self._product_row_to_dict(row)

    def list_products(
        self,
        platform: Optional[str] = None,
        category: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """查询商品列表，支持按平台、类目、关键词筛选。"""
        with self.SessionFactory() as session:
            q = session.query(ProductRow)
            if platform:
                q = q.filter(ProductRow.source_platform == platform)
            if category:
                q = q.filter(ProductRow.category == category)
            if keyword:
                q = q.filter(ProductRow.name.ilike(f"%{keyword}%"))
            q = q.order_by(ProductRow.updated_at.desc()).offset(offset).limit(limit)
            return [self._product_row_to_dict(r) for r in q.all()]

    def count_products(
        self,
        platform: Optional[str] = None,
        category: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> int:
        """统计商品数量（筛选条件与 list_products 一致）。"""
        with self.SessionFactory() as session:
            q = session.query(sa_func.count(ProductRow.product_id))
            if platform:
                q = q.filter(ProductRow.source_platform == platform)
            if category:
                q = q.filter(ProductRow.category == category)
            if keyword:
                q = q.filter(ProductRow.name.ilike(f"%{keyword}%"))
            return q.scalar() or 0

    @staticmethod
    def _product_row_to_dict(row: ProductRow) -> Dict[str, Any]:
        raw = row.raw_data or {}
        return {
            "product_id": row.product_id,
            "sku": row.sku,
            "name": row.name,
            "category": row.category,
            "brand": row.brand,
            "platform": row.source_platform,
            "url": row.source_url,
            "price": raw.get("price"),
            "original_price": raw.get("original_price"),
            "shop_name": raw.get("shop_name"),
            "images": raw.get("images", []),
            "specs": raw.get("specs", []),
            "description": raw.get("description"),
            "promotions": raw.get("promotions", []),
            "rating": raw.get("rating"),
            "review_count": raw.get("review_count"),
            "sales_count": raw.get("sales_count"),
            "created_at": _dt_to_iso(row.created_at),
            "updated_at": _dt_to_iso(row.updated_at),
        }

    # ================================================================
    # 私有辅助方法
    # ================================================================

    @staticmethod
    def _apply_time_filter(q, column, start, end):
        if start:
            q = q.filter(column >= start)
        if end:
            q = q.filter(column <= end)
        return q

    @staticmethod
    def _agent_row_to_dict(row: AgentRow) -> Dict[str, Any]:
        return {
            "agent_id": row.agent_id,
            "name": row.name,
            "slug": row.slug,
            "description": row.description,
            "agent_type": row.agent_type,
            "status": row.status,
            "model_config": row.model_config or {},
            "last_active_at": _dt_to_iso(row.last_active_at) if row.last_active_at else None,
            "error_message": row.error_message,
            "metadata": row.extra_metadata or {},
            "created_at": _dt_to_iso(row.created_at),
            "updated_at": _dt_to_iso(row.updated_at),
        }

    @staticmethod
    def _skill_row_to_dict(row: SkillRow) -> Dict[str, Any]:
        return {
            "skill_id": row.skill_id,
            "name": row.name,
            "display_name": row.display_name,
            "description": row.description,
            "skill_type": row.skill_type,
            "endpoint": row.endpoint,
            "config": row.config or {},
            "status": row.status,
            "created_at": _dt_to_iso(row.created_at),
            "updated_at": _dt_to_iso(row.updated_at),
        }

    @staticmethod
    def _task_row_to_dict(row: TaskRow) -> Dict[str, Any]:
        return {
            "task_id": row.task_id,
            "trace_id": row.trace_id,
            "task_type": row.task_type,
            "status": row.status,
            "agent_id": getattr(row, "agent_id", None),
            "agent_slug": getattr(row, "agent_slug", None),
            "created_at": _dt_to_iso(row.created_at),
            "updated_at": _dt_to_iso(row.updated_at),
        }

    @staticmethod
    def _event_row_to_dict(row: AgentEventRow) -> Dict[str, Any]:
        return {
            "event_id": row.event_id,
            "trace_id": row.trace_id,
            "agent_name": row.agent_name,
            "event_type": row.event_type,
            "session_id": row.session_id,
            "payload": row.payload or {},
            "created_at": _dt_to_iso(row.created_at),
        }


def _create_office_store() -> Optional[OfficeStore]:
    """根据环境变量创建 OfficeStore 实例。"""
    from app.config import settings
    if settings.database_url_sync:
        return OfficeStore(settings.database_url_sync)
    return None


office_store: Optional[OfficeStore] = _create_office_store()
