-- ============================================================
-- 文件: scripts/init_db.sql
-- 用途: PostgreSQL 初始化脚本，Docker 启动时自动执行
-- ============================================================

-- 启用 UUID 扩展（备用，当前使用应用层 make_id）
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- 1. 商品数据表
-- ============================================================
CREATE TABLE IF NOT EXISTS products (
    product_id      TEXT PRIMARY KEY,
    sku             TEXT,
    name            TEXT NOT NULL,
    category        TEXT,
    brand           TEXT,
    attributes      JSONB NOT NULL DEFAULT '{}',
    source_platform TEXT,
    source_url      TEXT,
    raw_data        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_products_category ON products (category);
CREATE INDEX IF NOT EXISTS idx_products_brand ON products (brand);
CREATE INDEX IF NOT EXISTS idx_products_source ON products (source_platform);
CREATE INDEX IF NOT EXISTS idx_products_attributes ON products USING GIN (attributes);

-- ============================================================
-- 2. 课程表（对应 CourseRecord）
-- ============================================================
CREATE TABLE IF NOT EXISTS courses (
    course_id       TEXT PRIMARY KEY,
    product_id      TEXT,
    product_name    TEXT NOT NULL,
    objective       TEXT NOT NULL,
    required_points JSONB NOT NULL DEFAULT '[]',
    product_facts   JSONB NOT NULL DEFAULT '{}',
    content_version INT NOT NULL DEFAULT 0,
    latest_content  JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_courses_product ON courses (product_id);

-- ============================================================
-- 3. 练习尝试表（对应 TrainingAttemptRecord）
-- ============================================================
CREATE TABLE IF NOT EXISTS training_attempts (
    attempt_id      TEXT PRIMARY KEY,
    course_id       TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    audio_url       TEXT,
    mock_transcript TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_attempts_course ON training_attempts (course_id);
CREATE INDEX IF NOT EXISTS idx_attempts_user ON training_attempts (user_id);

-- ============================================================
-- 4. 比价任务表（对应 ComparisonTaskRecord）
-- ============================================================
CREATE TABLE IF NOT EXISTS comparison_tasks (
    comparison_task_id  TEXT PRIMARY KEY,
    source_product_id   TEXT NOT NULL,
    source_product_name TEXT NOT NULL,
    targets             JSONB NOT NULL DEFAULT '[]',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_comparison_source ON comparison_tasks (source_product_id);

-- ============================================================
-- 5. 异步任务表（对应 TaskRecord）
-- ============================================================
CREATE TABLE IF NOT EXISTS tasks (
    task_id     TEXT PRIMARY KEY,
    trace_id    TEXT NOT NULL,
    task_type   TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'running', 'succeeded', 'failed')),
    input       JSONB NOT NULL DEFAULT '{}',
    output      JSONB,
    error       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tasks_trace ON tasks (trace_id);
CREATE INDEX IF NOT EXISTS idx_tasks_type ON tasks (task_type);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status);
CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks (created_at);

-- ============================================================
-- 6. Agent 事件日志表
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_events (
    event_id    BIGSERIAL PRIMARY KEY,
    trace_id    TEXT NOT NULL,
    agent_name  TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    session_id  TEXT,
    payload     JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_trace ON agent_events (trace_id);
CREATE INDEX IF NOT EXISTS idx_events_agent ON agent_events (agent_name);
CREATE INDEX IF NOT EXISTS idx_events_type ON agent_events (event_type);
CREATE INDEX IF NOT EXISTS idx_events_created ON agent_events (created_at);

-- ============================================================
-- 7. 审计日志表
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_logs (
    log_id       BIGSERIAL PRIMARY KEY,
    trace_id     TEXT NOT NULL,
    action       TEXT NOT NULL,
    actor        TEXT,
    entity_type  TEXT NOT NULL,
    entity_id    TEXT NOT NULL,
    before_state JSONB,
    after_state  JSONB,
    detail       JSONB NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_trace ON audit_logs (trace_id);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_logs (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs (action);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs (created_at);

-- ============================================================
-- 8. Agent 注册表（AgentsOffice 容器层）
-- ============================================================
CREATE TABLE IF NOT EXISTS agents (
    agent_id        TEXT PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    slug            TEXT NOT NULL UNIQUE,
    description     TEXT,
    agent_type      TEXT NOT NULL DEFAULT 'general',
    status          TEXT NOT NULL DEFAULT 'idle'
                    CHECK (status IN ('idle', 'running', 'error', 'disabled')),
    model_config    JSONB NOT NULL DEFAULT '{}',
    last_active_at  TIMESTAMPTZ,
    error_message   TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agents_slug ON agents (slug);
CREATE INDEX IF NOT EXISTS idx_agents_status ON agents (status);
CREATE INDEX IF NOT EXISTS idx_agents_type ON agents (agent_type);

COMMENT ON TABLE agents IS 'Agent 注册表，管理所有 AI Agent 的元数据和配置';
COMMENT ON COLUMN agents.slug IS '代码级标识，与 agent_events.agent_name 对应';
COMMENT ON COLUMN agents.model_config IS '模型配置，包含 model_name, temperature, max_tokens 等';

-- ============================================================
-- 9. Skill 注册表（AgentsOffice 容器层）
-- ============================================================
CREATE TABLE IF NOT EXISTS skills (
    skill_id        TEXT PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    display_name    TEXT NOT NULL,
    description     TEXT,
    skill_type      TEXT NOT NULL DEFAULT 'tool'
                    CHECK (skill_type IN ('tool', 'api', 'knowledge', 'internal')),
    endpoint        TEXT,
    config          JSONB NOT NULL DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'deprecated', 'disabled')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE skills IS 'Skill 注册表，管理 Agent 可使用的能力';

-- ============================================================
-- 10. Agent-Skill 关联表（AgentsOffice 容器层）
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_skills (
    agent_id    TEXT NOT NULL REFERENCES agents(agent_id),
    skill_id    TEXT NOT NULL REFERENCES skills(skill_id),
    config      JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (agent_id, skill_id)
);

COMMENT ON TABLE agent_skills IS 'Agent 与 Skill 的多对多绑定关系';

-- ============================================================
-- 11. 成本记录表（AgentsOffice 容器层）
-- ============================================================
CREATE TABLE IF NOT EXISTS cost_records (
    record_id       BIGSERIAL PRIMARY KEY,
    agent_id        TEXT REFERENCES agents(agent_id),
    agent_slug      TEXT NOT NULL,
    task_id         TEXT,
    trace_id        TEXT NOT NULL,
    model_name      TEXT NOT NULL,
    input_tokens    INT NOT NULL DEFAULT 0,
    output_tokens   INT NOT NULL DEFAULT 0,
    total_tokens    INT NOT NULL DEFAULT 0,
    input_cost      NUMERIC(12, 6) NOT NULL DEFAULT 0,
    output_cost     NUMERIC(12, 6) NOT NULL DEFAULT 0,
    total_cost      NUMERIC(12, 6) NOT NULL DEFAULT 0,
    duration_ms     INT,
    metadata        JSONB NOT NULL DEFAULT '{}',
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

-- ============================================================
-- 12. 模型定价表（AgentsOffice 容器层）
-- ============================================================
CREATE TABLE IF NOT EXISTS model_pricing (
    model_name          TEXT PRIMARY KEY,
    display_name        TEXT NOT NULL,
    provider            TEXT NOT NULL DEFAULT 'openai',
    input_price_per_1k  NUMERIC(10, 6) NOT NULL,
    output_price_per_1k NUMERIC(10, 6) NOT NULL,
    is_active           BOOLEAN NOT NULL DEFAULT true,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE model_pricing IS '模型定价配置，用于计算成本';

-- 模型定价种子数据
INSERT INTO model_pricing (model_name, display_name, provider, input_price_per_1k, output_price_per_1k) VALUES
    ('gpt-4o',      'GPT-4o',      'openai',    0.002500, 0.010000),
    ('gpt-4o-mini', 'GPT-4o Mini', 'openai',    0.000150, 0.000600),
    ('gpt-4.1',     'GPT-4.1',     'openai',    0.002000, 0.008000),
    ('gpt-4.1-mini','GPT-4.1 Mini','openai',    0.000400, 0.001600),
    ('gpt-4.1-nano','GPT-4.1 Nano','openai',    0.000100, 0.000400),
    ('claude-sonnet-4-20250514', 'Claude Sonnet 4', 'anthropic', 0.003000, 0.015000),
    ('claude-opus-4-20250514',   'Claude Opus 4',   'anthropic', 0.015000, 0.075000),
    ('claude-haiku-4-5-20251001','Claude Haiku 4.5','anthropic', 0.000800, 0.004000),
    ('gemini/gemini-2.0-flash',  'Gemini 2.0 Flash','google',   0.000100, 0.000400),
    ('gemini/gemini-2.5-flash-preview-05-20','Gemini 2.5 Flash','google',0.000150,0.000600),
    ('gemini/gemini-2.5-pro-preview-05-06',  'Gemini 2.5 Pro', 'google', 0.001250, 0.010000),
    ('deepseek/deepseek-chat',   'DeepSeek V3',    'deepseek',  0.000270, 0.001100),
    ('deepseek/deepseek-reasoner','DeepSeek R1',   'deepseek',  0.000550, 0.002190)
ON CONFLICT (model_name) DO NOTHING;

-- ============================================================
-- 13. 会话表（AgentsOffice Chat History）
-- ============================================================
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id TEXT PRIMARY KEY,
    title           TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'archived', 'deleted')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE conversations IS '聊天会话记录';

-- ============================================================
-- 14. 聊天消息表（AgentsOffice Chat History）
-- ============================================================
CREATE TABLE IF NOT EXISTS chat_messages (
    message_id      BIGSERIAL PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    role            TEXT NOT NULL,
    agent_slug      TEXT,
    agent_name      TEXT,
    content         TEXT NOT NULL DEFAULT '',
    message_type    TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_msg_conv ON chat_messages (conversation_id);
CREATE INDEX IF NOT EXISTS idx_chat_msg_created ON chat_messages (created_at);

COMMENT ON TABLE chat_messages IS '聊天消息记录，关联到 conversations 表';

-- ============================================================
-- 15. 数据大屏表（AgentsOffice Dashboard）
-- ============================================================
CREATE TABLE IF NOT EXISTS dashboards (
    dashboard_id    TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    slug            TEXT NOT NULL UNIQUE,
    description     TEXT,
    template_key    TEXT,
    layout          JSONB NOT NULL DEFAULT '[]',
    charts          JSONB NOT NULL DEFAULT '[]',
    data_sources    JSONB NOT NULL DEFAULT '[]',
    refresh_config  JSONB NOT NULL DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft', 'active', 'archived')),
    created_by      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE dashboards IS '数据大屏配置';

-- ============================================================
-- 16. 修改 tasks 表：增加 agent_id 和 agent_slug 列
-- ============================================================
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS agent_id TEXT;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS agent_slug TEXT;

CREATE INDEX IF NOT EXISTS idx_tasks_agent ON tasks (agent_id);
CREATE INDEX IF NOT EXISTS idx_tasks_agent_slug ON tasks (agent_slug);
