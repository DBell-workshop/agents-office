import React, { Component, lazy, Suspense, useEffect, useState } from 'react';
import { EventBus } from '../shared/events/EventBus';
import { getAgentsCached, loadAgentRegistry } from '../shared/agentRegistry';
import { AgentConfigPanel } from './AgentConfigPanel';
import { AgentCreateDialog } from './AgentCreateDialog';
import { AgentStatusBar } from './AgentStatusBar';
import { ChatBox } from './ChatBox';
// import { CollectorPanel } from './CollectorPanel';  // 采集功能暂停，改为接口导入模式
import { DatabasePanel } from './DatabasePanel';

import { ScenarioTemplatePanel } from './ScenarioTemplatePanel';
const DashboardView = lazy(() => import('./DashboardView'));

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
  isBuiltin: boolean;
}

const MAX_AGENTS = 20;

export const ReactOverlay: React.FC = () => {
  const [sceneReady, setSceneReady] = useState(false);
  const [configAgent, setConfigAgent] = useState<AgentClickData | null>(null);
  const [showDatabase, setShowDatabase] = useState(false);

  const [_showCollector, setShowCollector] = useState(false);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showDashboard, setShowDashboard] = useState(false);
  const [dashboardId, setDashboardId] = useState<string | undefined>(undefined);
  const [showTemplates, setShowTemplates] = useState(false);
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
        setConfigAgent({ agentSlug: agent.slug, agentName: agent.displayName, agentColor: agent.color, isBuiltin: agent.isBuiltin });
      }
    };

    // 状态栏卡片点击 → 打开配置面板
    const onConfigOpen = (data: AgentClickData) => setConfigAgent(data);

    // 事件驱动打开数据库面板（从 AgentConfigPanel 内的按钮触发）
    const onOpenDatabase = () => {
      setConfigAgent(null);
      setShowDatabase(true);
    };

    // ➕ 按钮 → 打开创建对话框
    const onAddNew = () => setShowCreateDialog(true);

    // 打开数据大屏
    const onOpenDashboard = (data?: { dashboardId?: string }) => {
      setDashboardId(data?.dashboardId);
      setShowDashboard(true);
    };

    // Agent 注册表变更 → 更新计数
    const onRegistryChanged = (data: { count: number }) => {
      setAgentCount(data.count);
    };

    EventBus.on('scene:ready', onSceneReady);
    EventBus.on('agent:clicked', onAgentClicked);
    EventBus.on('agent:open-config', onConfigOpen);
    EventBus.on('database:open', onOpenDatabase);
    EventBus.on('agent:add-new', onAddNew);
    EventBus.on('agent:registry-changed', onRegistryChanged);
    EventBus.on('dashboard:open', onOpenDashboard);

    return () => {
      EventBus.off('scene:ready', onSceneReady);
      EventBus.off('agent:clicked', onAgentClicked);
      EventBus.off('agent:open-config', onConfigOpen);
      EventBus.off('database:open', onOpenDatabase);
      EventBus.off('agent:add-new', onAddNew);
      EventBus.off('agent:registry-changed', onRegistryChanged);
      EventBus.off('dashboard:open', onOpenDashboard);
    };
  }, []);

  // ESC 关闭面板
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setConfigAgent(null);
        setShowDatabase(false);
        setShowCollector(false);
        setShowCreateDialog(false);
        setShowDashboard(false);
        setShowTemplates(false);
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
          <span style={{ color: '#88cc99' }}>|</span>
          <button
            onClick={() => setShowTemplates(true)}
            title="场景模板"
            style={{
              background: 'none',
              color: '#ffd666',
              border: '1px solid #ffd666',
              borderRadius: 3,
              padding: '1px 8px',
              fontSize: '11px',
              cursor: 'pointer',
              fontFamily: 'monospace',
            }}
          >
            📋 模板
          </button>
          <button
            onClick={() => window.open('/static/office/dashboard.html', '_blank', 'noopener')}
            title="数据大屏"
            style={{
              background: 'linear-gradient(135deg, rgba(139,92,246,0.2), rgba(99,102,241,0.2))',
              color: '#c4b5fd',
              border: '1px solid rgba(139,92,246,0.5)',
              borderRadius: 6,
              padding: '3px 12px',
              fontSize: '12px',
              cursor: 'pointer',
              fontFamily: 'monospace',
              fontWeight: 600,
              letterSpacing: 1,
              transition: 'all 0.2s ease',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.background = 'linear-gradient(135deg, rgba(139,92,246,0.4), rgba(99,102,241,0.4))';
              e.currentTarget.style.borderColor = 'rgba(139,92,246,0.8)';
              e.currentTarget.style.color = '#fff';
              e.currentTarget.style.transform = 'translateY(-1px)';
              e.currentTarget.style.boxShadow = '0 2px 12px rgba(139,92,246,0.3)';
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = 'linear-gradient(135deg, rgba(139,92,246,0.2), rgba(99,102,241,0.2))';
              e.currentTarget.style.borderColor = 'rgba(139,92,246,0.5)';
              e.currentTarget.style.color = '#c4b5fd';
              e.currentTarget.style.transform = 'translateY(0)';
              e.currentTarget.style.boxShadow = 'none';
            }}
          >
            📊 大屏
          </button>
          {agentCount < MAX_AGENTS && (
            <button
              onClick={() => setShowCreateDialog(true)}
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

      {/* Agent 创建对话框 */}
      {showCreateDialog && (
        <AgentCreateDialog
          onClose={() => setShowCreateDialog(false)}
          onCreated={(slug, name, color) => {
            setShowCreateDialog(false);
            // 创建成功后打开配置面板，方便用户继续设置提示词和模型
            setConfigAgent({ agentSlug: slug, agentName: name, agentColor: color, isBuiltin: false });
          }}
        />
      )}

      {/* Agent 配置面板 */}
      {configAgent && (
        <AgentConfigPanel
          agentSlug={configAgent.agentSlug}
          agentName={configAgent.agentName}
          agentColor={configAgent.agentColor}
          isBuiltin={configAgent.isBuiltin}
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

      {/* 场景模板 */}
      {showTemplates && (
        <ScenarioTemplatePanel
          onClose={() => setShowTemplates(false)}
          onApplied={() => {
            // 刷新 Agent 注册表
            loadAgentRegistry().then((entries) => setAgentCount(entries.length));
          }}
        />
      )}

      {/* 数据大屏 */}
      {showDashboard && (
        <PanelErrorBoundary onError={() => setShowDashboard(false)}>
          <Suspense fallback={<div style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'linear-gradient(-45deg, #f3e8ff, #e0f2fe, #f0fdf4, #ede9fe)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#8b5cf6', fontSize: 15, fontFamily: 'Inter, sans-serif' }}>加载大屏组件...</div>}>
            <DashboardView
              dashboardId={dashboardId}
              onClose={() => { setShowDashboard(false); setDashboardId(undefined); }}
            />
          </Suspense>
        </PanelErrorBoundary>
      )}

      {/* 底部 Agent 状态栏 */}
      {sceneReady && <AgentStatusBar />}

      {/* 右侧聊天面板 */}
      {sceneReady && <ChatBox />}
    </>
  );
};
