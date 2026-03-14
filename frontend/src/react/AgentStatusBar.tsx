import React, { useCallback, useEffect, useRef, useState } from 'react';
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

function formatTokens(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return `${n}`;
}

function formatTime(seconds: number): string {
  if (seconds < 60) return `${Math.floor(seconds)} 秒`;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return s > 0 ? `${m} 分 ${s} 秒` : `${m} 分`;
}

export const AgentStatusBar: React.FC = () => {
  // ChatBox 宽度同步 — 信息卡不被聊天面板遮挡
  const [chatBoxWidth, setChatBoxWidth] = useState(360);

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
        const slugSet = new Set(prev.map((a) => a.slug));
        const fromRegistry = entries.map((a) => ({
          slug: a.slug,
          name: a.displayName,
          color: a.color,
          role: a.role,
          modelDisplay: 'Gemini Flash',
          active: true,
          hasPrompt: true,
        }));
        // 保持已有 agent 的 modelDisplay 等运行时状态
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
  const [workSeconds, setWorkSeconds] = useState<Record<string, number>>({});
  const workStartRef = useRef<Record<string, number>>({});

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

          // 更新 standby 状态
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
      setStatuses((prev) => {
        const oldStatus = prev[data.agentSlug];
        if (data.status === 'working' && oldStatus !== 'working') {
          workStartRef.current[data.agentSlug] = Date.now();
        }
        if (oldStatus === 'working' && data.status !== 'working') {
          const start = workStartRef.current[data.agentSlug];
          if (start) {
            const elapsed = (Date.now() - start) / 1000;
            setWorkSeconds((ws) => ({
              ...ws,
              [data.agentSlug]: (ws[data.agentSlug] || 0) + elapsed,
            }));
            delete workStartRef.current[data.agentSlug];
          }
        }
        return { ...prev, [data.agentSlug]: data.status };
      });
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

  return (
    <div style={{ ...styles.bar, right: chatBoxWidth + 16 }}>
      {agents.map((agent) => {
        const status = statuses[agent.slug] || 'standby';
        const isWorking = status === 'working';
        const totalTokens = tokens[agent.slug] || 0;
        const totalWork = workSeconds[agent.slug] || 0;

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
            {/* 状态圆点 */}
            <div style={{
              width: 18,
              height: 18,
              borderRadius: '50%',
              background: isWorking ? agent.color : (agent.active ? '#887755' : '#776655'),
              boxShadow: isWorking ? `0 0 10px ${agent.color}, 0 0 4px ${agent.color}` : 'none',
              border: `2px solid ${agent.color}`,
              flexShrink: 0,
            }} />

            {/* 信息区 */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ color: agent.color, fontWeight: 'bold', fontSize: '16px' }}>
                  {agent.name}
                </span>
                <span style={{
                  color: isWorking ? '#66ff88' : '#ddcc99',
                  fontSize: '13px',
                  fontWeight: isWorking ? 'bold' : 'normal',
                }}>
                  {statusLabel(status)}
                </span>
              </div>

              <div style={{ color: '#ccbb88', fontSize: '12px', marginTop: 3 }}>
                {agent.role}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 3 }}>
                <span style={{ fontSize: '12px', color: agent.active ? '#55dd77' : '#aa8855' }}>
                  {agent.active ? '\u25cf' : '\u25cb'}
                </span>
                <span style={{ color: agent.active ? '#ddcc88' : '#aa9977', fontSize: '12px' }}>
                  {agent.active ? `${agent.modelDisplay} 已连接` : agent.modelDisplay}
                </span>
              </div>

              <div style={{
                display: 'flex',
                gap: 14,
                marginTop: 4,
                paddingTop: 4,
                borderTop: '1px solid #55442233',
              }}>
                {agent.active ? (
                  <>
                    <span style={{ color: '#ccaa66', fontSize: '12px' }}>
                      消耗 {formatTokens(totalTokens)} tokens
                    </span>
                    <span style={{ color: '#ccaa66', fontSize: '12px' }}>
                      工时 {formatTime(totalWork)}
                    </span>
                  </>
                ) : (
                  <span style={{ color: '#887766', fontSize: '12px' }}>
                    点击配置并激活
                  </span>
                )}
              </div>
            </div>
          </div>
        );
      })}
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
    gap: 6,
    pointerEvents: 'auto',
    zIndex: 10,
  },
  card: {
    flex: 1,
    minWidth: 0,
    display: 'flex',
    alignItems: 'flex-start',
    gap: 10,
    background: 'rgba(20, 15, 8, 0.93)',
    border: '2px solid #887755',
    borderRadius: 5,
    padding: '10px 12px',
    fontFamily: 'monospace',
    boxSizing: 'border-box' as const,
  },
};
