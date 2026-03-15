import React, { Component, useEffect, useState } from 'react';
import { EventBus } from '../shared/events/EventBus';
import { getAgentsCached, loadAgentRegistry } from '../shared/agentRegistry';
import { AgentConfigPanel } from './AgentConfigPanel';
import { AgentStatusBar } from './AgentStatusBar';
import { ChatBox } from './ChatBox';
// import { CollectorPanel } from './CollectorPanel';  // 采集功能暂停，改为接口导入模式
import { DatabasePanel } from './DatabasePanel';

// 错误边界：防止子面板崩溃导致整个 UI 消失
class PanelErrorBoundary extends Component<
  { children: React.ReactNode; onError?: () => void },
  { hasError: boolean; errorMsg: string }
> {
  state = { hasError: false, errorMsg: '' };
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, errorMsg: error.message };
  }
  componentDidCatch(error: Error) {
    console.error('[PanelErrorBoundary]', error);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 10000,
          background: 'rgba(0,0,0,0.6)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          pointerEvents: 'auto',
        }}>
          <div style={{
            background: '#1a1a2e', border: '2px solid #ff6b6b',
            borderRadius: 8, padding: '24px 32px', fontFamily: 'monospace',
            color: '#ff6b6b', maxWidth: 400, textAlign: 'center' as const,
          }}>
            <div style={{ fontSize: 28, marginBottom: 12 }}>⚠️</div>
            <div style={{ fontSize: 14, marginBottom: 8 }}>面板加载出错</div>
            <div style={{ fontSize: 12, color: '#999', marginBottom: 16 }}>{this.state.errorMsg}</div>
            <button
              onClick={() => {
                this.setState({ hasError: false, errorMsg: '' });
                this.props.onError?.();
              }}
              style={{
                background: '#ff6b6b', color: '#fff', border: 'none',
                borderRadius: 4, padding: '6px 20px', cursor: 'pointer',
                fontFamily: 'monospace', fontSize: 13,
              }}
            >
              关闭
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

interface AgentClickData {
  agentSlug: string;
  agentName: string;
  agentColor: string;
}

const MAX_AGENTS = 20;

export const ReactOverlay: React.FC = () => {
  const [sceneReady, setSceneReady] = useState(false);
  const [configAgent, setConfigAgent] = useState<AgentClickData | null>(null);
  const [showDatabase, setShowDatabase] = useState(false);
  const [showCollector, setShowCollector] = useState(false);
  const [agentCount, setAgentCount] = useState(6);

  // 初始化 agent 计数
  useEffect(() => {
    setAgentCount(getAgentsCached().length);
    loadAgentRegistry().then((entries) => {
      setAgentCount(entries.length);
    });
  }, []);

  useEffect(() => {
    const onSceneReady = () => setSceneReady(true);

    // Phaser 精灵点击 → 打开配置面板（动态查找 agent）
    const onAgentClicked = (data: { agentId: string; name: string }) => {
      const agents = getAgentsCached();
      const agent = agents.find((a) => a.phaserAgentId === data.agentId);
      if (agent) {
        setConfigAgent({ agentSlug: agent.slug, agentName: agent.displayName, agentColor: agent.color });
      }
    };

    // 状态栏卡片点击 → 打开配置面板
    const onConfigOpen = (data: AgentClickData) => setConfigAgent(data);

    // 事件驱动打开数据库面板（从 AgentConfigPanel 内的按钮触发）
    const onOpenDatabase = () => {
      setConfigAgent(null);
      setShowDatabase(true);
    };

    // 采集面板事件已暂停
    // const onOpenCollector = () => { setConfigAgent(null); setShowCollector(true); };

    EventBus.on('scene:ready', onSceneReady);
    EventBus.on('agent:clicked', onAgentClicked);
    EventBus.on('agent:open-config', onConfigOpen);
    EventBus.on('database:open', onOpenDatabase);

    return () => {
      EventBus.off('scene:ready', onSceneReady);
      EventBus.off('agent:clicked', onAgentClicked);
      EventBus.off('agent:open-config', onConfigOpen);
      EventBus.off('database:open', onOpenDatabase);
    };
  }, []);

  // ESC 关闭面板
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setConfigAgent(null);
        setShowDatabase(false);
        setShowCollector(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <>
      {/* 顶部状态栏 */}
      {sceneReady && (
        <div style={{
          position: 'absolute',
          top: 8,
          left: 8,
          pointerEvents: 'auto',
          background: 'rgba(0, 0, 0, 0.7)',
          border: '2px solid #4ade80',
          padding: '6px 12px',
          fontFamily: 'monospace',
          fontSize: '12px',
          color: '#4ade80',
          imageRendering: 'pixelated',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }}>
          <span>AgentsOffice v0.1</span>
          <span style={{ color: '#88cc99' }}>|</span>
          <span>Agents: {agentCount}/{MAX_AGENTS}</span>
          {agentCount < MAX_AGENTS && (
            <button
              onClick={() => EventBus.emit('agent:add-new', {})}
              title="添加新 Agent"
              style={{
                background: '#4ade80',
                color: '#000',
                border: 'none',
                borderRadius: 3,
                width: 20,
                height: 20,
                fontSize: '14px',
                fontWeight: 'bold',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: 0,
                lineHeight: 1,
              }}
            >
              +
            </button>
          )}
        </div>
      )}

      {/* Agent 配置面板 */}
      {configAgent && (
        <AgentConfigPanel
          agentSlug={configAgent.agentSlug}
          agentName={configAgent.agentName}
          agentColor={configAgent.agentColor}
          onClose={() => setConfigAgent(null)}
        />
      )}

      {/* 浏览器采集面板 */}
      {/* 采集面板暂停使用 */}
      {/* {showCollector && (
        <PanelErrorBoundary onError={() => setShowCollector(false)}>
          <CollectorPanel onClose={() => setShowCollector(false)} />
        </PanelErrorBoundary>
      )} */}

      {/* 数据库可视化面板 */}
      {showDatabase && (
        <PanelErrorBoundary onError={() => setShowDatabase(false)}>
          <DatabasePanel onClose={() => setShowDatabase(false)} />
        </PanelErrorBoundary>
      )}

      {/* 底部 Agent 状态栏 */}
      {sceneReady && <AgentStatusBar />}

      {/* 右侧聊天面板 */}
      {sceneReady && <ChatBox />}
    </>
  );
};
