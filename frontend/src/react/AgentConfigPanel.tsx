import React, { useEffect, useState } from 'react';
import { EventBus } from '../shared/events/EventBus';

interface ModelOption {
  model_name: string;
  display_name: string;
  provider: string;
  input_price_per_1k: number;
  output_price_per_1k: number;
  available: boolean;
}

interface ProviderStatus {
  [provider: string]: boolean;
}

interface AgentConfig {
  // 模型配置
  model_name: string;
  temperature: number;
  max_tokens: number;
  api_base: string;
  api_key: string;
  // 身份定义
  display_name: string;
  role: string;
  system_prompt: string;
  color: string;
  active: boolean;
}

interface Props {
  agentSlug: string;
  agentName: string;
  agentColor: string;
  onClose: () => void;
}

type Tab = 'identity' | 'model' | 'prompt';

export const AgentConfigPanel: React.FC<Props> = ({ agentSlug, agentName, agentColor, onClose }) => {
  const [models, setModels] = useState<ModelOption[]>([]);
  const [providerStatus, setProviderStatus] = useState<ProviderStatus>({});
  const [config, setConfig] = useState<AgentConfig>({
    model_name: '',
    temperature: 0.7,
    max_tokens: 2048,
    api_base: '',
    api_key: '',
    display_name: agentName,
    role: '',
    system_prompt: '',
    color: agentColor,
    active: true,
  });
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [activeTab, setActiveTab] = useState<Tab>('identity');
  const [refining, setRefining] = useState(false);
  const [refineMsg, setRefineMsg] = useState('');
  const [templates, setTemplates] = useState<Array<{slug: string; display_name: string; role: string; color: string; system_prompt: string}>>([]);
  const [showTemplates, setShowTemplates] = useState(false);

  // 加载预设模板
  useEffect(() => {
    fetch('/api/v1/office/agent-templates')
      .then((r) => r.json())
      .then((envelope) => {
        setTemplates(envelope?.data?.templates || []);
      })
      .catch(() => {});
  }, []);

  // 加载可用模型列表
  useEffect(() => {
    fetch('/api/v1/office/models')
      .then((r) => r.json())
      .then((envelope) => {
        const items: ModelOption[] = envelope?.data?.models || [];
        setModels(items);
        setProviderStatus(envelope?.data?.provider_status || {});
      })
      .catch(() => {});
  }, []);

  // 加载当前 Agent 配置
  useEffect(() => {
    fetch('/api/v1/office/agent-config')
      .then((r) => r.json())
      .then((envelope) => {
        const configs = envelope?.data?.configs || {};
        const agentCfg = configs[agentSlug];
        if (agentCfg) {
          setConfig((prev) => ({
            ...prev,
            model_name: agentCfg.model_name || '',
            temperature: agentCfg.temperature ?? 0.7,
            max_tokens: agentCfg.max_tokens ?? 2048,
            api_base: agentCfg.api_base || '',
            api_key: agentCfg.api_key || '',
            display_name: agentCfg.display_name || agentName,
            role: agentCfg.role || '',
            system_prompt: agentCfg.system_prompt || '',
            color: agentCfg.color || agentColor,
            active: agentCfg.active ?? true,
          }));
        }
      })
      .catch(() => {});
  }, [agentSlug, agentName, agentColor]);

  const handleSave = async () => {
    setSaving(true);
    setMessage('');
    try {
      const res = await fetch(`/api/v1/office/agent-config/${agentSlug}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      if (res.ok) {
        setMessage('已保存');
        EventBus.emit('agent:config-updated', { agentSlug, config });
        setTimeout(() => setMessage(''), 2000);
      } else {
        setMessage('保存失败');
      }
    } catch {
      setMessage('网络错误');
    } finally {
      setSaving(false);
    }
  };

  const handleRefine = async () => {
    const draft = config.system_prompt.trim();
    if (!draft) {
      setRefineMsg('请先输入描述内容');
      setTimeout(() => setRefineMsg(''), 2000);
      return;
    }
    setRefining(true);
    setRefineMsg('');
    try {
      const res = await fetch(`/api/v1/office/agent-config/${agentSlug}/refine-prompt`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          draft,
          agent_name: config.display_name || agentName,
          agent_role: config.role,
        }),
      });
      if (res.ok) {
        const envelope = await res.json();
        const refined = envelope?.data?.refined_prompt;
        if (refined) {
          setConfig((c) => ({ ...c, system_prompt: refined }));
          setRefineMsg('AI 已优化，请检查后保存');
        } else {
          setRefineMsg('返回内容为空');
        }
      } else {
        const err = await res.json().catch(() => null);
        setRefineMsg(err?.detail || 'AI 优化失败');
      }
    } catch {
      setRefineMsg('网络错误');
    } finally {
      setRefining(false);
      setTimeout(() => setRefineMsg(''), 4000);
    }
  };

  const selectedModel = models.find((m) => m.model_name === config.model_name);

  // 按 provider 分组
  const grouped = models.reduce<Record<string, ModelOption[]>>((acc, m) => {
    (acc[m.provider] = acc[m.provider] || []).push(m);
    return acc;
  }, {});
  const providerLabels: Record<string, string> = {
    google: 'Google',
    openai: 'OpenAI',
    anthropic: 'Anthropic',
    deepseek: 'DeepSeek',
    dashscope: '阿里云百炼 (DashScope)',
  };

  const displayColor = config.color || agentColor;

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.panel} onClick={(e) => e.stopPropagation()}>
        {/* 标题栏 */}
        <div style={styles.header}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
              width: 12,
              height: 12,
              borderRadius: '50%',
              background: displayColor,
              border: `2px solid ${displayColor}`,
              boxShadow: `0 0 6px ${displayColor}44`,
              flexShrink: 0,
            }} />
            <span style={{ color: displayColor, fontWeight: 'bold', fontSize: '16px' }}>
              {config.display_name || agentName} 配置
            </span>
          </div>
          <button onClick={onClose} style={styles.closeBtn}>ESC</button>
        </div>

        {/* Tab 切换 */}
        <div style={styles.tabBar}>
          {([
            ['identity', '身份定义'],
            ['prompt', '系统提示词'],
            ['model', '模型配置'],
          ] as [Tab, string][]).map(([tab, label]) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                ...styles.tabBtn,
                color: activeTab === tab ? '#ffd700' : '#998877',
                borderBottomColor: activeTab === tab ? '#ffd700' : 'transparent',
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {/* === 身份定义 Tab === */}
        {activeTab === 'identity' && (
          <>
            {/* 从模板加载 */}
            <div style={styles.section}>
              <button
                onClick={() => setShowTemplates(!showTemplates)}
                style={{
                  background: 'rgba(255, 215, 0, 0.1)', border: '1px dashed #665544',
                  borderRadius: 4, padding: '6px 12px', color: '#ccbb88', cursor: 'pointer',
                  fontSize: '12px', width: '100%',
                }}
              >
                {showTemplates ? '▾ 收起模板' : '▸ 从预设模板加载...'}
              </button>
              {showTemplates && (
                <div style={{
                  marginTop: 8, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6,
                }}>
                  {templates.map((t) => (
                    <button
                      key={t.slug}
                      onClick={() => {
                        setConfig((c) => ({
                          ...c,
                          display_name: t.display_name,
                          role: t.role,
                          color: t.color,
                          system_prompt: t.system_prompt,
                        }));
                        setShowTemplates(false);
                        setMessage(`已加载「${t.display_name}」模板`);
                        setTimeout(() => setMessage(''), 2000);
                      }}
                      style={{
                        background: 'rgba(255, 255, 255, 0.05)', border: '1px solid #44382a',
                        borderRadius: 4, padding: '8px', cursor: 'pointer', textAlign: 'left',
                      }}
                    >
                      <div style={{ color: t.color, fontSize: '13px', fontWeight: 'bold' }}>
                        {t.display_name}
                      </div>
                      <div style={{ color: '#998877', fontSize: '11px', marginTop: 2 }}>
                        {t.role.length > 30 ? t.role.slice(0, 30) + '...' : t.role}
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div style={styles.section}>
              <label style={styles.label}>Agent 名称</label>
              <input
                type="text"
                value={config.display_name}
                onChange={(e) => setConfig((c) => ({ ...c, display_name: e.target.value }))}
                placeholder="如: 售后客服专家"
                style={styles.input}
              />
            </div>

            <div style={styles.section}>
              <label style={styles.label}>职责描述</label>
              <input
                type="text"
                value={config.role}
                onChange={(e) => setConfig((c) => ({ ...c, role: e.target.value }))}
                placeholder="如: 处理退换货和客户投诉"
                style={styles.input}
              />
              <div style={styles.hint}>
                调度员会根据这段描述决定是否将任务分配给这个 Agent
              </div>
            </div>

            <div style={styles.section}>
              <label style={styles.label}>显示颜色</label>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <input
                  type="color"
                  value={config.color || agentColor}
                  onChange={(e) => setConfig((c) => ({ ...c, color: e.target.value }))}
                  style={{ width: 36, height: 28, border: 'none', background: 'none', cursor: 'pointer' }}
                />
                <span style={{ color: '#887766', fontSize: '12px' }}>{config.color || agentColor}</span>
              </div>
            </div>

            <div style={styles.section}>
              <label style={{ ...styles.label, display: 'flex', alignItems: 'center', gap: 8 }}>
                激活状态
                <button
                  onClick={() => setConfig((c) => ({ ...c, active: !c.active }))}
                  style={{
                    background: config.active ? 'rgba(74, 222, 128, 0.2)' : 'rgba(255, 107, 107, 0.15)',
                    border: `1px solid ${config.active ? '#4ade80' : '#ff6b6b'}`,
                    color: config.active ? '#4ade80' : '#ff6b6b',
                    borderRadius: 4,
                    padding: '2px 12px',
                    cursor: 'pointer',
                    fontFamily: 'monospace',
                    fontSize: '12px',
                  }}
                >
                  {config.active ? '已激活' : '未激活'}
                </button>
              </label>
              <div style={styles.hint}>
                未激活的 Agent 不会出现在调度员的路由选项中
              </div>
            </div>

            {/* 比价专员专属：采集数据入口（暂停使用，改为接口导入模式）*/}
            {/* agentSlug === 'price_comparator' && (
              <div style={{
                marginTop: 8,
                padding: '12px 14px',
                background: 'rgba(96, 165, 250, 0.08)',
                border: '1px solid rgba(96, 165, 250, 0.3)',
                borderRadius: 6,
              }}>
                <div style={{ fontSize: 13, color: '#60a5fa', fontWeight: 'bold', marginBottom: 8 }}>
                  比价专员工具
                </div>
                <button
                  onClick={() => EventBus.emit('collector:open')}
                  style={{
                    ...styles.dbBtn,
                    background: 'rgba(96, 165, 250, 0.2)',
                    border: '1px solid #60a5fa',
                    color: '#60a5fa',
                  }}
                >
                  采集数据
                </button>
                <div style={{ ...styles.hint, marginTop: 6 }}>
                  打开浏览器采集面板，从京东/淘宝/拼多多等平台采集商品数据
                </div>
              </div>
            ) */}

            {/* 数据工程师专属：数据库管理入口 */}
            {agentSlug === 'data_engineer' && (
              <div style={{
                marginTop: 8,
                padding: '12px 14px',
                background: 'rgba(167, 139, 250, 0.08)',
                border: '1px solid rgba(167, 139, 250, 0.3)',
                borderRadius: 6,
              }}>
                <div style={{ fontSize: 13, color: '#a78bfa', fontWeight: 'bold', marginBottom: 8 }}>
                  数据工程师专属工具
                </div>
                <button
                  onClick={() => EventBus.emit('database:open')}
                  style={styles.dbBtn}
                >
                  🗄️ 打开数据库管理面板
                </button>
                <div style={{ ...styles.hint, marginTop: 6 }}>
                  查看已导入的数据表、表结构、数据预览和上传的文件
                </div>
              </div>
            )}
          </>
        )}

        {/* === 系统提示词 Tab === */}
        {activeTab === 'prompt' && (
          <div style={styles.section}>
            <label style={styles.label}>
              系统提示词
              <span style={{ color: '#887766', fontWeight: 'normal', marginLeft: 8 }}>
                ({config.system_prompt.length} 字)
              </span>
            </label>
            <textarea
              value={config.system_prompt}
              onChange={(e) => setConfig((c) => ({ ...c, system_prompt: e.target.value }))}
              placeholder="用自然语言描述这个 Agent 的角色、职责、工作方式和回复风格...&#10;&#10;例如：&#10;你是一个售后客服专家，擅长处理退换货和客户投诉。&#10;&#10;## 你的职责&#10;- 安抚客户情绪&#10;- 查询订单状态&#10;- 提供退换货方案"
              style={styles.textarea}
              rows={16}
            />
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 8 }}>
              <button
                onClick={handleRefine}
                disabled={refining || !config.system_prompt.trim()}
                style={{
                  ...styles.refineBtn,
                  opacity: (refining || !config.system_prompt.trim()) ? 0.5 : 1,
                }}
              >
                {refining ? 'AI 优化中...' : 'AI 优化提示词'}
              </button>
              {refineMsg && (
                <span style={{
                  fontSize: '12px',
                  color: refineMsg.includes('已优化') ? '#4ade80' : '#fbbf24',
                }}>
                  {refineMsg}
                </span>
              )}
            </div>
            <div style={styles.hint}>
              先用自然语言写下你对这个 Agent 的想法，然后点击「AI 优化提示词」，AI 会帮你整理成专业的 system prompt。优化后请检查并保存。
            </div>
          </div>
        )}

        {/* === 模型配置 Tab === */}
        {activeTab === 'model' && (
          <>
            {/* API 状态 */}
            <div style={styles.statusBar}>
              <span style={{ color: '#ccbb88', fontSize: '12px' }}>API 状态：</span>
              {Object.entries(providerStatus).map(([provider, available]) => (
                <span
                  key={provider}
                  style={{
                    fontSize: '11px',
                    color: available ? '#4ade80' : '#ff6b6b',
                    padding: '1px 6px',
                    border: `1px solid ${available ? '#4ade8044' : '#ff6b6b44'}`,
                    borderRadius: 3,
                    background: available ? 'rgba(74, 222, 128, 0.08)' : 'rgba(255, 107, 107, 0.08)',
                  }}
                >
                  {available ? '\u25cf' : '\u25cb'} {providerLabels[provider] || provider}
                </span>
              ))}
            </div>

            {/* 模型选择 */}
            <div style={styles.section}>
              <label style={styles.label}>LLM 模型</label>
              <select
                value={config.model_name}
                onChange={(e) => setConfig((c) => ({ ...c, model_name: e.target.value }))}
                style={styles.select}
              >
                <option value="">默认 (系统配置)</option>
                {Object.entries(grouped).map(([provider, items]) => {
                  const isAvailable = providerStatus[provider] ?? false;
                  return (
                    <optgroup
                      key={provider}
                      label={`${providerLabels[provider] || provider}${isAvailable ? '' : ' (未配置 API Key)'}`}
                    >
                      {items.map((m) => (
                        <option key={m.model_name} value={m.model_name} disabled={!m.available}>
                          {m.available ? '\u2713' : '\u2717'} {m.display_name}{!m.available ? ' (不可用)' : ''}
                        </option>
                      ))}
                    </optgroup>
                  );
                })}
              </select>
              {selectedModel && (
                <div style={{ ...styles.hint, color: selectedModel.available ? '#aa9966' : '#ff6b6b' }}>
                  {selectedModel.available
                    ? `输入 $${selectedModel.input_price_per_1k}/1k | 输出 $${selectedModel.output_price_per_1k}/1k`
                    : `不可用 — 请在 .env 中配置 ${selectedModel.provider.toUpperCase()} API Key`
                  }
                </div>
              )}
            </div>

            {/* Temperature */}
            <div style={styles.section}>
              <label style={styles.label}>
                Temperature: <span style={{ color: '#ffd700' }}>{config.temperature.toFixed(1)}</span>
              </label>
              <input
                type="range" min="0" max="1.5" step="0.1"
                value={config.temperature}
                onChange={(e) => setConfig((c) => ({ ...c, temperature: parseFloat(e.target.value) }))}
                style={styles.slider}
              />
              <div style={styles.rangeLabels}>
                <span>精确 0</span><span>创意 1.5</span>
              </div>
            </div>

            {/* Max Tokens */}
            <div style={styles.section}>
              <label style={styles.label}>
                最大输出: <span style={{ color: '#ffd700' }}>{config.max_tokens}</span> tokens
              </label>
              <input
                type="range" min="256" max="8192" step="256"
                value={config.max_tokens}
                onChange={(e) => setConfig((c) => ({ ...c, max_tokens: parseInt(e.target.value) }))}
                style={styles.slider}
              />
              <div style={styles.rangeLabels}>
                <span>256</span><span>8192</span>
              </div>
            </div>

            {/* 自定义代理接入 */}
            <div style={{ ...styles.section, borderTop: '1px solid #33281a', paddingTop: 12, marginTop: 8 }}>
              <label style={styles.label}>自定义代理接入 (可选)</label>
              <div style={styles.hint}>
                支持 one-api / new-api 等 OpenAI 兼容代理服务。留空则使用系统全局 API Key。
              </div>
              <div style={{ marginTop: 8 }}>
                <label style={{ ...styles.label, fontSize: '12px' }}>代理地址 (Base URL)</label>
                <input
                  type="text"
                  placeholder="例: https://your-proxy.com/v1"
                  value={config.api_base}
                  onChange={(e) => setConfig((c) => ({ ...c, api_base: e.target.value }))}
                  style={styles.input}
                />
              </div>
              <div style={{ marginTop: 8 }}>
                <label style={{ ...styles.label, fontSize: '12px' }}>API Key (代理密钥)</label>
                <input
                  type="password"
                  placeholder="sk-..."
                  value={config.api_key}
                  onChange={(e) => setConfig((c) => ({ ...c, api_key: e.target.value }))}
                  style={styles.input}
                />
              </div>
              {(config.api_base || config.api_key) && (
                <div style={{
                  marginTop: 8, padding: '6px 10px', borderRadius: 4,
                  background: 'rgba(255, 170, 50, 0.1)', border: '1px solid rgba(255, 170, 50, 0.3)',
                  fontSize: '11px', color: '#ccaa66', lineHeight: 1.5,
                }}>
                  注意：使用第三方代理服务时，请确保该服务可信。API Key 将以加密方式存储，但仍建议使用专用子密钥。
                  部分代理服务可能不支持所有模型功能（如 Function Calling）。
                </div>
              )}
            </div>
          </>
        )}

        {/* 保存按钮（所有 Tab 都显示） */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 16, paddingTop: 12, borderTop: '1px solid #33281a' }}>
          <button onClick={handleSave} disabled={saving} style={styles.saveBtn}>
            {saving ? '保存中...' : '保存配置'}
          </button>
          {message && (
            <span style={{ color: message === '已保存' ? '#4ade80' : '#ff6b6b', fontSize: '13px' }}>
              {message}
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  overlay: {
    position: 'absolute',
    inset: 0,
    background: 'rgba(0, 0, 0, 0.5)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 200,
    pointerEvents: 'auto',
  },
  panel: {
    width: 440,
    maxHeight: '85vh',
    overflowY: 'auto',
    background: 'rgba(15, 12, 8, 0.97)',
    border: '2px solid #887755',
    borderRadius: 6,
    padding: '20px 24px',
    fontFamily: 'monospace',
    color: '#e0e0e0',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
    paddingBottom: 10,
    borderBottom: '1px solid #554433',
  },
  tabBar: {
    display: 'flex',
    gap: 0,
    marginBottom: 14,
    borderBottom: '1px solid #33281a',
  },
  tabBtn: {
    background: 'none',
    border: 'none',
    borderBottom: '2px solid transparent',
    color: '#998877',
    fontFamily: 'monospace',
    fontSize: '13px',
    padding: '6px 14px',
    cursor: 'pointer',
  },
  statusBar: {
    display: 'flex',
    flexWrap: 'wrap' as const,
    alignItems: 'center',
    gap: 6,
    marginBottom: 10,
    paddingBottom: 8,
    borderBottom: '1px solid #33281a',
  },
  closeBtn: {
    background: 'none',
    border: '1px solid #666',
    color: '#999',
    cursor: 'pointer',
    fontFamily: 'monospace',
    fontSize: '12px',
    padding: '2px 8px',
  },
  section: {
    marginBottom: 14,
  },
  label: {
    display: 'block',
    fontSize: '13px',
    color: '#ccbb88',
    marginBottom: 6,
  },
  input: {
    width: '100%',
    padding: '8px 10px',
    background: 'rgba(255, 255, 255, 0.08)',
    border: '1px solid #665544',
    borderRadius: 4,
    color: '#f0f0f0',
    fontFamily: 'monospace',
    fontSize: '13px',
    outline: 'none',
    boxSizing: 'border-box' as const,
  },
  select: {
    width: '100%',
    padding: '8px 10px',
    background: 'rgba(255, 255, 255, 0.08)',
    border: '1px solid #665544',
    borderRadius: 4,
    color: '#f0f0f0',
    fontFamily: 'monospace',
    fontSize: '13px',
    outline: 'none',
  },
  textarea: {
    width: '100%',
    padding: '10px',
    background: 'rgba(255, 255, 255, 0.06)',
    border: '1px solid #665544',
    borderRadius: 4,
    color: '#f0f0f0',
    fontFamily: 'monospace',
    fontSize: '12px',
    lineHeight: '1.5',
    outline: 'none',
    resize: 'vertical' as const,
    boxSizing: 'border-box' as const,
    minHeight: 200,
  },
  hint: {
    fontSize: '11px',
    color: '#887766',
    marginTop: 4,
    lineHeight: 1.4,
  },
  slider: {
    width: '100%',
    accentColor: '#ffd700',
  },
  rangeLabels: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '11px',
    color: '#887766',
    marginTop: 2,
  },
  saveBtn: {
    background: 'rgba(74, 222, 128, 0.2)',
    border: '1px solid #4ade80',
    borderRadius: 4,
    color: '#4ade80',
    padding: '8px 20px',
    cursor: 'pointer',
    fontFamily: 'monospace',
    fontSize: '14px',
    fontWeight: 'bold',
  },
  refineBtn: {
    background: 'rgba(251, 191, 36, 0.15)',
    border: '1px solid #fbbf24',
    borderRadius: 4,
    color: '#fbbf24',
    padding: '6px 14px',
    cursor: 'pointer',
    fontFamily: 'monospace',
    fontSize: '12px',
    fontWeight: 'bold',
  },
  dbBtn: {
    background: 'rgba(167, 139, 250, 0.2)',
    border: '1px solid #a78bfa',
    borderRadius: 4,
    color: '#a78bfa',
    padding: '8px 16px',
    cursor: 'pointer',
    fontFamily: 'monospace',
    fontSize: '13px',
    fontWeight: 'bold',
    width: '100%',
  },
};
