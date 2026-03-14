import React, { useEffect, useState } from 'react';
import { EventBus } from '../shared/events/EventBus';
import { AgentConfigPanel } from './AgentConfigPanel';
import { AgentStatusBar } from './AgentStatusBar';
import { ChatBox } from './ChatBox';

interface AgentClickData {
  agentSlug: string;
  agentName: string;
  agentColor: string;
}

export const ReactOverlay: React.FC = () => {
  const [sceneReady, setSceneReady] = useState(false);
  const [configAgent, setConfigAgent] = useState<AgentClickData | null>(null);

  useEffect(() => {
    const onSceneReady = () => setSceneReady(true);

    // Phaser 精灵点击 → 打开配置面板
    const onAgentClicked = (data: { agentId: string; name: string }) => {
      // 从 agentId 推导 slug 和颜色
      const mapping: Record<string, { slug: string; color: string }> = {
        agt_dispatcher: { slug: 'dispatcher', color: '#ff6b6b' },
        agt_guide: { slug: 'shopping_guide', color: '#4ade80' },
        agt_inventory: { slug: 'product_specialist', color: '#60a5fa' },
        agt_data_eng: { slug: 'data_engineer', color: '#a78bfa' },
      };
      const info = mapping[data.agentId];
      if (info) {
        setConfigAgent({ agentSlug: info.slug, agentName: data.name, agentColor: info.color });
      }
    };

    // 状态栏卡片点击 → 打开配置面板
    const onConfigOpen = (data: AgentClickData) => setConfigAgent(data);

    EventBus.on('scene:ready', onSceneReady);
    EventBus.on('agent:clicked', onAgentClicked);
    EventBus.on('agent:open-config', onConfigOpen);

    return () => {
      EventBus.off('scene:ready', onSceneReady);
      EventBus.off('agent:clicked', onAgentClicked);
      EventBus.off('agent:open-config', onConfigOpen);
    };
  }, []);

  // ESC 关闭面板
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setConfigAgent(null);
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
        }}>
          AgentsOffice v0.1 | Agents: 6
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

      {/* 底部 Agent 状态栏 */}
      {sceneReady && <AgentStatusBar />}

      {/* 右侧聊天面板 */}
      {sceneReady && <ChatBox />}
    </>
  );
};
