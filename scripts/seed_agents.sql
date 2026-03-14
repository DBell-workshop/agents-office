-- ============================================================
-- 文件: scripts/seed_agents.sql
-- 用途: AgentsOffice 容器层种子数据（Agents, Skills, 绑定关系）
-- 前置: init_db.sql 已执行完毕
-- ============================================================

-- ============================================================
-- 1. 注册 6 个初始 Agent
-- ============================================================
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

-- ============================================================
-- 2. 注册 8 个初始 Skill
-- ============================================================
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

-- ============================================================
-- 3. 绑定 Skills 到 Agents
-- ============================================================
INSERT INTO agent_skills (agent_id, skill_id) VALUES
    -- Sales Coach: LLM + TTS + RAG
    ('agt_sales_coach', 'skl_llm'),
    ('agt_sales_coach', 'skl_tts'),
    ('agt_sales_coach', 'skl_rag'),
    -- Pitch Evaluator: LLM + ASR + 评分 + 事实核验
    ('agt_pitch_eval',  'skl_llm'),
    ('agt_pitch_eval',  'skl_asr'),
    ('agt_pitch_eval',  'skl_scoring'),
    ('agt_pitch_eval',  'skl_fact_check'),
    -- Price Intelligence: LLM + 页面采集 + 价格标准化
    ('agt_price_intel', 'skl_llm'),
    ('agt_price_intel', 'skl_openclaw'),
    ('agt_price_intel', 'skl_normalize'),
    -- Risk & QA: LLM + 事实核验
    ('agt_risk_qa',     'skl_llm'),
    ('agt_risk_qa',     'skl_fact_check'),
    -- Experiment Analyst: LLM + RAG
    ('agt_experiment',  'skl_llm'),
    ('agt_experiment',  'skl_rag')
ON CONFLICT DO NOTHING;
