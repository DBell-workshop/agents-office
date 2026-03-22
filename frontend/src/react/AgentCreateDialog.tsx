import React, { useEffect, useState } from 'react';
import { EventBus } from '../shared/events/EventBus';
import { invalidateAgentCache, loadAgentRegistry } from '../shared/agentRegistry';

interface Props {
  onClose: () => void;
  onCreated: (slug: string, displayName: string, color: string) => void;
}

interface Template {
  slug: string;
  display_name: string;
  role: string;
  color: string;
  system_prompt: string;
}

const ROOMS = [
  { id: 'workspace', label: '待命区' },
  { id: 'showroom', label: '展示厅' },
  { id: 'datacenter', label: '数据仓库' },
  { id: 'meeting', label: '协作室' },
];

const PRESET_COLORS = [
  '#4ade80', '#60a5fa', '#f59e0b', '#ec4899',
  '#a78bfa', '#f97316', '#14b8a6', '#e879f9',
  '#fb923c', '#38bdf8', '#facc15', '#34d399',
];

/** 中文/英文名 → slug（仅保留字母数字下划线） */
function toSlug(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/[\s\-]+/g, '_')
    .replace(/[^a-z0-9_\u4e00-\u9fff]/g, '')
    // 如果全是中文，用拼音首字母的简单 fallback
    .replace(/[\u4e00-\u9fff]+/g, '')
    .replace(/^_+|_+$/g, '')
    || `agent_${Date.now().toString(36).slice(-4)}`;
}

export const AgentCreateDialog: React.FC<Props> = ({ onClose, onCreated }) => {
  const [displayName, setDisplayName] = useState('');
  const [slug, setSlug] = useState('');
  const [slugManual, setSlugManual] = useState(false);
  const [role, setRole] = useState('');
  const [color, setColor] = useState('#4ade80');
  const [roomId, setRoomId] = useState('workspace');
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');
  const [templates, setTemplates] = useState<Template[]>([]);
  const [showTemplates, setShowTemplates] = useState(false);

  // 加载预设模板
  useEffect(() => {
    fetch('/api/v1/office/agent-templates')
      .then((r) => r.json())
      .then((envelope) => {
        const items: Template[] = (envelope?.data?.templates || [])
          .filter((t: Template) => t.slug !== 'dispatcher');
        setTemplates(items);
      })
      .catch(() => {});
  }, []);

  // 自动生成 slug
  useEffect(() => {
    if (!slugManual && displayName) {
      setSlug(toSlug(displayName));
    }
  }, [displayName, slugManual]);

  const handleCreate = async () => {
    const trimmedName = displayName.trim();
    const trimmedSlug = slug.trim();
    if (!trimmedName) {
      setError('请输入 Agent 名称');
      return;
    }
    if (!trimmedSlug) {
      setError('请输入 Agent 标识（slug）');
      return;
    }
    if (!/^[a-z0-9_]+$/.test(trimmedSlug)) {
      setError('标识只能包含小写字母、数字和下划线');
      return;
    }

    setCreating(true);
    setError('');

    try {
      const res = await fetch(`/api/v1/office/agent-config/${trimmedSlug}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          display_name: trimmedName,
          role: role.trim() || trimmedName,
          color,
          room_id: roomId,
          active: true,
          model_name: '',
          temperature: 0.7,
          max_tokens: 2048,
        }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        setError(body?.detail || '创建失败');
        setCreating(false);
        return;
      }

      // 刷新注册表缓存
      invalidateAgentCache();
      const entries = await loadAgentRegistry();

      // 通知 Phaser 场景添加新精灵
      const newAgent = entries.find((a) => a.slug === trimmedSlug);
      if (newAgent) {
        EventBus.emit('agent:spawned', {
          slug: newAgent.slug,
          displayName: newAgent.displayName,
          color: newAgent.color,
          roomId: newAgent.roomId || roomId,
          phaserAgentId: newAgent.phaserAgentId,
        });
      }

      // 通知状态栏和顶部计数刷新
      EventBus.emit('agent:registry-changed', { count: entries.length });

      onCreated(trimmedSlug, trimmedName, color);
    } catch {
      setError('网络错误');
    } finally {
      setCreating(false);
    }
  };

  const applyTemplate = (t: Template) => {
    setDisplayName(t.display_name);
    setRole(t.role);
    setColor(t.color);
    if (!slugManual) {
      setSlug(toSlug(t.display_name) || t.slug);
    }
    setShowTemplates(false);
  };

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.panel} onClick={(e) => e.stopPropagation()}>
        {/* 标题栏 */}
        <div style={styles.header}>
          <span style={{ color: '#4ade80', fontWeight: 'bold', fontSize: '16px' }}>
            + 创建新 Agent
          </span>
          <button onClick={onClose} style={styles.closeBtn}>ESC</button>
        </div>

        {/* 从模板创建 */}
        <div style={styles.section}>
          <button
            onClick={() => setShowTemplates(!showTemplates)}
            style={styles.templateToggle}
          >
            {showTemplates ? '▾ 收起模板' : '▸ 从预设模板快速创建...'}
          </button>
          {showTemplates && (
            <div style={styles.templateGrid}>
              {templates.map((t) => (
                <button key={t.slug} onClick={() => applyTemplate(t)} style={styles.templateCard}>
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

        {/* Agent 名称 */}
        <div style={styles.section}>
          <label style={styles.label}>Agent 名称 *</label>
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="如: 售后客服专家"
            style={styles.input}
            autoFocus
          />
        </div>

        {/* Agent 标识 */}
        <div style={styles.section}>
          <label style={styles.label}>
            Agent 标识 (slug) *
            <button
              onClick={() => setSlugManual(!slugManual)}
              style={{
                ...styles.slugToggle,
                color: slugManual ? '#fbbf24' : '#887766',
              }}
            >
              {slugManual ? '手动输入中' : '自动生成'}
            </button>
          </label>
          <input
            type="text"
            value={slug}
            onChange={(e) => {
              setSlugManual(true);
              setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''));
            }}
            placeholder="如: customer_service"
            style={styles.input}
          />
          <div style={styles.hint}>
            唯一标识，只能包含小写字母、数字和下划线。中文名称请手动输入英文标识。
          </div>
        </div>

        {/* 职责描述 */}
        <div style={styles.section}>
          <label style={styles.label}>职责描述</label>
          <input
            type="text"
            value={role}
            onChange={(e) => setRole(e.target.value)}
            placeholder="如: 处理退换货和客户投诉"
            style={styles.input}
          />
          <div style={styles.hint}>
            调度员会根据这段描述决定是否将任务分配给这个 Agent
          </div>
        </div>

        {/* 显示颜色 */}
        <div style={styles.section}>
          <label style={styles.label}>显示颜色</label>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            {PRESET_COLORS.map((c) => (
              <div
                key={c}
                onClick={() => setColor(c)}
                style={{
                  width: 22,
                  height: 22,
                  borderRadius: '50%',
                  background: c,
                  cursor: 'pointer',
                  border: color === c ? '3px solid #fff' : '2px solid transparent',
                  boxShadow: color === c ? `0 0 8px ${c}` : 'none',
                }}
              />
            ))}
            <input
              type="color"
              value={color}
              onChange={(e) => setColor(e.target.value)}
              style={{ width: 28, height: 22, border: 'none', background: 'none', cursor: 'pointer' }}
            />
          </div>
        </div>

        {/* 所在房间 */}
        <div style={styles.section}>
          <label style={styles.label}>所在房间</label>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {ROOMS.map((r) => (
              <button
                key={r.id}
                onClick={() => setRoomId(r.id)}
                style={{
                  ...styles.roomBtn,
                  borderColor: roomId === r.id ? '#4ade80' : '#665544',
                  color: roomId === r.id ? '#4ade80' : '#ccbb88',
                  background: roomId === r.id ? 'rgba(74, 222, 128, 0.1)' : 'rgba(255, 255, 255, 0.05)',
                }}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>

        {/* 错误提示 */}
        {error && (
          <div style={{ color: '#ff6b6b', fontSize: '13px', marginBottom: 8 }}>
            {error}
          </div>
        )}

        {/* 操作按钮 */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 12,
          marginTop: 16, paddingTop: 12, borderTop: '1px solid #33281a',
        }}>
          <button
            onClick={handleCreate}
            disabled={creating || !displayName.trim()}
            style={{
              ...styles.createBtn,
              opacity: (creating || !displayName.trim()) ? 0.5 : 1,
            }}
          >
            {creating ? '创建中...' : '创建 Agent'}
          </button>
          <button onClick={onClose} style={styles.cancelBtn}>
            取消
          </button>
          <div style={{ marginLeft: 'auto', fontSize: '11px', color: '#887766' }}>
            创建后可在配置面板中设置提示词和模型
          </div>
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
    width: 460,
    maxHeight: '85vh',
    overflowY: 'auto',
    background: 'rgba(15, 12, 8, 0.97)',
    border: '2px solid #4ade80',
    borderRadius: 6,
    padding: '20px 24px',
    fontFamily: 'monospace',
    color: '#e0e0e0',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 14,
    paddingBottom: 10,
    borderBottom: '1px solid #554433',
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
    display: 'flex',
    alignItems: 'center',
    gap: 8,
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
  hint: {
    fontSize: '11px',
    color: '#887766',
    marginTop: 4,
    lineHeight: 1.4,
  },
  slugToggle: {
    background: 'none',
    border: 'none',
    fontSize: '11px',
    cursor: 'pointer',
    fontFamily: 'monospace',
    marginLeft: 'auto',
  },
  roomBtn: {
    border: '1px solid #665544',
    borderRadius: 4,
    padding: '4px 12px',
    cursor: 'pointer',
    fontFamily: 'monospace',
    fontSize: '12px',
    background: 'rgba(255, 255, 255, 0.05)',
  },
  templateToggle: {
    background: 'rgba(74, 222, 128, 0.08)',
    border: '1px dashed #665544',
    borderRadius: 4,
    padding: '6px 12px',
    color: '#ccbb88',
    cursor: 'pointer',
    fontSize: '12px',
    width: '100%',
    fontFamily: 'monospace',
  },
  templateGrid: {
    marginTop: 8,
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 6,
  },
  templateCard: {
    background: 'rgba(255, 255, 255, 0.05)',
    border: '1px solid #44382a',
    borderRadius: 4,
    padding: '8px',
    cursor: 'pointer',
    textAlign: 'left' as const,
    fontFamily: 'monospace',
  },
  createBtn: {
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
  cancelBtn: {
    background: 'none',
    border: '1px solid #665544',
    borderRadius: 4,
    color: '#998877',
    padding: '8px 16px',
    cursor: 'pointer',
    fontFamily: 'monospace',
    fontSize: '13px',
  },
};
