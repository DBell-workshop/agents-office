import React, { useCallback, useEffect, useState } from 'react';
import { EventBus } from '../shared/events/EventBus';
import { loadAgentRegistry, getAgentsCached } from '../shared/agentRegistry';

// 模型名称显示映射 — 从 /api/v1/office/models 动态加载
let MODEL_DISPLAY_NAMES: Record<string, string> = {};

// 启动时从后端加载模型显示名映射
fetch('/api/v1/office/models')
  .then((r) => r.json())
  .then((envelope) => {
    const models = envelope?.data?.models || [];
    const map: Record<string, string> = {};
    for (const m of models) {
      if (m.model_name && m.display_name) {
        map[m.model_name] = m.display_name;
      }
    }
    MODEL_DISPLAY_NAMES = map;
  })
  .catch(() => {});

interface AgentDef {
  slug: string;
  name: string;
  color: string;
  role: string;
  modelDisplay: string;
  active: boolean;
  hasPrompt: boolean;
}

type AgentStatus = 'idle' | 'working' | 'standby';

const MAX_PER_ROW = 7;

function formatTokens(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return `${n}`;
}

export const AgentStatusBar: React.FC = () => {
  // 展开/折叠状态
  const [expanded, setExpanded] = useState(false);

  // ChatBox 宽度同步 — 信息卡不被聊天面板遮挡
  const [chatBoxWidth, setChatBoxWidth] = useState(520);

  useEffect(() => {
    const onResize = (data: { width: number }) => setChatBoxWidth(data.width);
    EventBus.on('chatbox:resize', onResize);
    return () => { EventBus.off('chatbox:resize', onResize); };
  }, []);

  // Agent 定义列表（从 agentRegistry 加载）
  const [agents, setAgents] = useState<AgentDef[]>(() =>
    getAgentsCached().map((a) => ({
      slug: a.slug,
      name: a.displayName,
      color: a.color,
      role: a.role,
      modelDisplay: 'Gemini Flash',
      active: true,
      hasPrompt: true,
    }))
  );

  // 加载注册表后更新 agent 列表
  useEffect(() => {
    loadAgentRegistry().then((entries) => {
      setAgents((prev) => {
        const fromRegistry = entries.map((a) => ({
          slug: a.slug,
          name: a.displayName,
          color: a.color,
          role: a.role,
          modelDisplay: 'Gemini Flash',
          active: true,
          hasPrompt: true,
        }));
        return fromRegistry.map((r) => {
          const existing = prev.find((p) => p.slug === r.slug);
          return existing ? { ...r, modelDisplay: existing.modelDisplay, active: existing.active, hasPrompt: existing.hasPrompt } : r;
        });
      });
    });
  }, []);

  const [statuses, setStatuses] = useState<Record<string, AgentStatus>>(() => {
    const init: Record<string, AgentStatus> = {};
    for (const a of getAgentsCached()) {
      init[a.slug] = 'idle';
    }
    return init;
  });

  const [tokens, setTokens] = useState<Record<string, number>>({});

  // 从后端加载 agent 定义
  const syncAgentDefinitions = useCallback(() => {
    fetch('/api/v1/office/agent-config')
      .then((res) => res.json())
      .then((envelope) => {
        const configs = envelope?.data?.configs || {};
        setAgents((prev) => {
          const updated = prev.map((agent) => {
            const cfg = configs[agent.slug];
            if (!cfg) return agent;
            return {
              ...agent,
              name: (cfg.display_name && cfg.display_name !== agent.slug) ? cfg.display_name : agent.name,
              color: cfg.color || agent.color,
              role: cfg.role || agent.role,
              modelDisplay: cfg.model_name
                ? MODEL_DISPLAY_NAMES[cfg.model_name] || cfg.model_name
                : agent.modelDisplay,
              active: cfg.active ?? agent.active,
              hasPrompt: !!(cfg.system_prompt),
            };
          });

          setStatuses((prevStatuses) => {
            const newStatuses = { ...prevStatuses };
            for (const agent of updated) {
              if (agent.active && newStatuses[agent.slug] === 'standby') {
                newStatuses[agent.slug] = 'idle';
              }
              if (!agent.active && newStatuses[agent.slug] !== 'standby') {
                newStatuses[agent.slug] = 'standby';
              }
            }
            return newStatuses;
          });

          return updated;
        });
      })
      .catch(() => {});
  }, []);

  const syncTokensFromAPI = useCallback(() => {
    fetch('/api/v1/office/costs/by-agent')
      .then((res) => res.json())
      .then((envelope) => {
        const items = envelope?.data?.items || [];
        const loaded: Record<string, number> = {};
        for (const item of items) {
          if (item.agent_slug) {
            loaded[item.agent_slug] = (loaded[item.agent_slug] || 0) + (item.total_tokens || 0);
          }
        }
        setTokens(loaded);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    syncAgentDefinitions();
    syncTokensFromAPI();

    EventBus.on('chat:round-complete', syncTokensFromAPI);
    EventBus.on('agent:config-updated', syncAgentDefinitions);

    return () => {
      EventBus.off('chat:round-complete', syncTokensFromAPI);
      EventBus.off('agent:config-updated', syncAgentDefinitions);
    };
  }, [syncAgentDefinitions, syncTokensFromAPI]);

  useEffect(() => {
    const onStatusChange = (data: { agentSlug: string; status: AgentStatus }) => {
      setStatuses((prev) => ({ ...prev, [data.agentSlug]: data.status }));
    };

    const onTokenUsage = (data: { agentSlug: string; tokens: number }) => {
      setTokens((prev) => ({
        ...prev,
        [data.agentSlug]: (prev[data.agentSlug] || 0) + data.tokens,
      }));
    };

    EventBus.on('agent:status', onStatusChange);
    EventBus.on('agent:token-usage', onTokenUsage);
    return () => {
      EventBus.off('agent:status', onStatusChange);
      EventBus.off('agent:token-usage', onTokenUsage);
    };
  }, []);

  const statusLabel = (s: AgentStatus) => {
    switch (s) {
      case 'working': return '工作中';
      case 'standby': return '待命';
      default: return '空闲';
    }
  };

  const handleCardClick = (agent: AgentDef) => {
    EventBus.emit('agent:open-config', {
      agentSlug: agent.slug,
      agentName: agent.name,
      agentColor: agent.color,
    });
  };

  // 将 agents 按每行 MAX_PER_ROW 分组
  const rows: AgentDef[][] = [];
  for (let i = 0; i < agents.length; i += MAX_PER_ROW) {
    rows.push(agents.slice(i, i + MAX_PER_ROW));
  }

  return (
    <div style={{ ...styles.bar, right: chatBoxWidth + 16 }}>
      {/* 展开/折叠按钮 */}
      <div
        onClick={() => setExpanded(!expanded)}
        style={styles.toggleBtn}
        title={expanded ? '收起详情' : '展开详情'}
      >
        <span style={{ fontSize: 10 }}>{expanded ? '▼' : '▲'}</span>
        <span style={{ fontSize: 11 }}>
          {expanded ? '收起' : '详情'}
        </span>
      </div>

      {/* Agent 卡片网格 */}
      {rows.map((row, rowIdx) => (
        <div key={rowIdx} style={styles.row}>
          {row.map((agent) => {
            const status = statuses[agent.slug] || 'standby';
            const isWorking = status === 'working';
            const totalTokens = tokens[agent.slug] || 0;

            return (
              <div
                key={agent.slug}
                onClick={() => handleCardClick(agent)}
                style={{
                  ...styles.card,
                  opacity: agent.active ? 1 : 0.7,
                  borderColor: isWorking ? agent.color : (agent.active ? '#887755' : '#776655'),
                  boxShadow: isWorking ? `0 0 10px ${agent.color}44` : 'none',
                  cursor: 'pointer',
                }}
              >
                {/* 紧凑头部：圆点 + 名称 + 状态 */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{
                    width: 10,
                    height: 10,
                    borderRadius: '50%',
                    background: isWorking ? agent.color : (agent.active ? '#887755' : '#776655'),
                    boxShadow: isWorking ? `0 0 6px ${agent.color}` : 'none',
                    border: `1.5px solid ${agent.color}`,
                    flexShrink: 0,
                  }} />
                  <span style={{ color: agent.color, fontWeight: 'bold', fontSize: '13px' }}>
                    {agent.name}
                  </span>
                  <span style={{
                    color: isWorking ? '#66ff88' : '#ddcc99',
                    fontSize: '11px',
                    fontWeight: isWorking ? 'bold' : 'normal',
                    marginLeft: 'auto',
                  }}>
                    {statusLabel(status)}
                  </span>
                </div>

                {/* 展开时显示的详细信息 */}
                {expanded && (
                  <>
                    <div style={{ color: '#ccbb88', fontSize: '11px', marginTop: 3, lineHeight: 1.3 }}>
                      {agent.role}
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 3 }}>
                      <span style={{ fontSize: '10px', color: agent.active ? '#55dd77' : '#aa8855' }}>
                        {agent.active ? '\u25cf' : '\u25cb'}
                      </span>
                      <span style={{ color: agent.active ? '#ddcc88' : '#aa9977', fontSize: '11px' }}>
                        {agent.active ? `${agent.modelDisplay}` : '未配置'}
                      </span>
                    </div>

                    <div style={{
                      marginTop: 3,
                      paddingTop: 3,
                      borderTop: '1px solid #55442233',
                    }}>
                      {agent.active ? (
                        <span style={{ color: '#ccaa66', fontSize: '11px' }}>
                          消耗 {formatTokens(totalTokens)} tokens
                        </span>
                      ) : (
                        <span style={{ color: '#887766', fontSize: '11px' }}>
                          点击配置
                        </span>
                      )}
                    </div>
                  </>
                )}

                {/* 折叠时只显示 token 摘要 */}
                {!expanded && agent.active && (
                  <div style={{ display: 'flex', gap: 8, marginTop: 2 }}>
                    <span style={{ color: '#ccaa66', fontSize: '10px' }}>
                      {formatTokens(totalTokens)} tok
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  bar: {
    position: 'absolute',
    bottom: 12,
    left: 12,
    right: 376,
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
    pointerEvents: 'auto',
    zIndex: 10,
  },
  toggleBtn: {
    alignSelf: 'flex-end',
    display: 'flex',
    alignItems: 'center',
    gap: 4,
    background: 'rgba(20, 15, 8, 0.85)',
    border: '1px solid #887755',
    borderRadius: 3,
    padding: '2px 8px',
    fontFamily: 'monospace',
    color: '#ccbb88',
    cursor: 'pointer',
    userSelect: 'none' as const,
  },
  row: {
    display: 'flex',
    gap: 4,
  },
  card: {
    flex: 1,
    minWidth: 0,
    display: 'flex',
    flexDirection: 'column' as const,
    background: 'rgba(20, 15, 8, 0.93)',
    border: '2px solid #887755',
    borderRadius: 5,
    padding: '6px 8px',
    fontFamily: 'monospace',
    boxSizing: 'border-box' as const,
  },
};
