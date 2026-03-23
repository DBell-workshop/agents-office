/**
 * ScenarioTemplatePanel — 场景模板选择面板
 *
 * 功能：
 * - 展示内置 + 自定义场景模板
 * - 一键应用模板（批量创建 Agent）
 * - 保存当前配置为自定义模板
 */
import React, { useCallback, useEffect, useState } from 'react';

interface ScenarioTemplate {
  key: string;
  name: string;
  description: string;
  agent_count: number;
  agents: string[];
  is_builtin: boolean;
}

interface ScenarioTemplatePanelProps {
  onClose: () => void;
  onApplied?: () => void; // 模板应用成功后的回调
}

export function ScenarioTemplatePanel({ onClose, onApplied }: ScenarioTemplatePanelProps) {
  const [templates, setTemplates] = useState<ScenarioTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [showSaveForm, setShowSaveForm] = useState(false);
  const [saveName, setSaveName] = useState('');
  const [saveDesc, setSaveDesc] = useState('');
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const loadTemplates = useCallback(async () => {
    try {
      const res = await fetch('/api/v1/office/scenario-templates');
      const json = await res.json();
      if (json.data?.templates) {
        setTemplates(json.data.templates);
      }
    } catch {
      setMessage({ type: 'error', text: '加载模板列表失败' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadTemplates(); }, [loadTemplates]);

  const handleApply = async (templateKey: string, clearExisting: boolean) => {
    setApplying(templateKey);
    setMessage(null);
    try {
      const res = await fetch('/api/v1/office/scenario-templates/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ template_key: templateKey, clear_existing: clearExisting }),
      });
      const json = await res.json();
      if (json.error) {
        setMessage({ type: 'error', text: json.error });
      } else {
        const agents = json.data?.agents || [];
        const created = agents.filter((a: { status: string }) => a.status === 'created').length;
        const existing = agents.filter((a: { status: string }) => a.status === 'already_exists').length;
        setMessage({
          type: 'success',
          text: `模板应用成功！新建 ${created} 个 Agent${existing ? `，${existing} 个已存在` : ''}`,
        });
        onApplied?.();
      }
    } catch {
      setMessage({ type: 'error', text: '应用模板失败' });
    } finally {
      setApplying(null);
    }
  };

  const handleSave = async () => {
    if (!saveName.trim()) return;
    setSaving(true);
    setMessage(null);
    try {
      const res = await fetch('/api/v1/office/scenario-templates/save-current', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: saveName, description: saveDesc }),
      });
      const json = await res.json();
      if (json.error) {
        setMessage({ type: 'error', text: json.error });
      } else {
        setMessage({ type: 'success', text: `模板「${saveName}」保存成功！` });
        setShowSaveForm(false);
        setSaveName('');
        setSaveDesc('');
        loadTemplates(); // 刷新列表
      }
    } catch {
      setMessage({ type: 'error', text: '保存模板失败' });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (key: string) => {
    try {
      await fetch(`/api/v1/office/scenario-templates/${key}`, { method: 'DELETE' });
      loadTemplates();
    } catch { /* silent */ }
  };

  const builtinTemplates = templates.filter(t => t.is_builtin);
  const customTemplates = templates.filter(t => !t.is_builtin);

  return (
    <div style={styles.overlay}>
      <div style={styles.panel}>
        {/* Header */}
        <div style={styles.header}>
          <h2 style={styles.title}>场景模板</h2>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => setShowSaveForm(!showSaveForm)} style={styles.saveBtn}>
              💾 保存当前配置
            </button>
            <button onClick={onClose} style={styles.closeBtn}>✕</button>
          </div>
        </div>

        {/* Message */}
        {message && (
          <div style={{
            ...styles.message,
            background: message.type === 'success' ? '#1a3a1a' : '#3a1a1a',
            borderColor: message.type === 'success' ? '#4ade80' : '#ff6b6b',
          }}>
            {message.type === 'success' ? '✅' : '❌'} {message.text}
          </div>
        )}

        {/* Save Form */}
        {showSaveForm && (
          <div style={styles.saveForm}>
            <input
              value={saveName}
              onChange={e => setSaveName(e.target.value)}
              placeholder="模板名称（如：我的电商团队）"
              style={styles.input}
              autoFocus
            />
            <input
              value={saveDesc}
              onChange={e => setSaveDesc(e.target.value)}
              placeholder="简短描述（可选）"
              style={styles.input}
            />
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={handleSave} disabled={!saveName.trim() || saving} style={styles.applyBtn}>
                {saving ? '保存中...' : '保存'}
              </button>
              <button onClick={() => setShowSaveForm(false)} style={styles.cancelBtn}>取消</button>
            </div>
          </div>
        )}

        {/* Templates Grid */}
        <div style={styles.scrollArea}>
          {loading ? (
            <div style={{ textAlign: 'center', color: '#8892b0', padding: 40 }}>加载中...</div>
          ) : (
            <>
              {/* Builtin */}
              <div style={styles.sectionTitle}>📦 预设模板</div>
              <div style={styles.grid}>
                {builtinTemplates.map(tpl => (
                  <TemplateCard
                    key={tpl.key}
                    template={tpl}
                    applying={applying === tpl.key}
                    onApply={(clear) => handleApply(tpl.key, clear)}
                  />
                ))}
              </div>

              {/* Custom */}
              {customTemplates.length > 0 && (
                <>
                  <div style={styles.sectionTitle}>💾 我的模板</div>
                  <div style={styles.grid}>
                    {customTemplates.map(tpl => (
                      <TemplateCard
                        key={tpl.key}
                        template={tpl}
                        applying={applying === tpl.key}
                        onApply={(clear) => handleApply(tpl.key, clear)}
                        onDelete={() => handleDelete(tpl.key)}
                      />
                    ))}
                  </div>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}


function TemplateCard({
  template: tpl, applying, onApply, onDelete,
}: {
  template: ScenarioTemplate;
  applying: boolean;
  onApply: (clearExisting: boolean) => void;
  onDelete?: () => void;
}) {
  const [showConfirm, setShowConfirm] = useState(false);

  return (
    <div style={styles.card}>
      <div style={{ flex: 1 }}>
        <div style={styles.cardTitle}>
          {tpl.name}
          {!tpl.is_builtin && onDelete && (
            <button onClick={onDelete} style={styles.deleteBtn} title="删除模板">🗑</button>
          )}
        </div>
        <div style={styles.cardDesc}>{tpl.description}</div>
        <div style={styles.cardMeta}>
          {tpl.agent_count} 个 Agent · {tpl.agents.join('、')}
        </div>
      </div>

      {!showConfirm ? (
        <button
          onClick={() => setShowConfirm(true)}
          disabled={applying}
          style={styles.applyBtn}
        >
          {applying ? '应用中...' : '🚀 应用模板'}
        </button>
      ) : (
        <div style={styles.confirmArea}>
          <span style={{ fontSize: 12, color: '#8892b0' }}>如何处理现有 Agent？</span>
          <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
            <button onClick={() => { onApply(false); setShowConfirm(false); }} style={styles.optionBtn}>
              追加
            </button>
            <button onClick={() => { onApply(true); setShowConfirm(false); }} style={{ ...styles.optionBtn, borderColor: '#ff6b6b', color: '#ff6b6b' }}>
              替换
            </button>
            <button onClick={() => setShowConfirm(false)} style={styles.optionBtn}>
              取消
            </button>
          </div>
        </div>
      )}
    </div>
  );
}


const styles: Record<string, React.CSSProperties> = {
  overlay: {
    position: 'fixed',
    inset: 0,
    zIndex: 10000,
    background: 'rgba(0,0,0,0.7)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    pointerEvents: 'auto',
  },
  panel: {
    background: '#1a1a2e',
    border: '2px solid #4ade80',
    borderRadius: 12,
    width: '90%',
    maxWidth: 720,
    maxHeight: '85vh',
    display: 'flex',
    flexDirection: 'column',
    fontFamily: 'monospace',
    overflow: 'hidden',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '16px 20px',
    borderBottom: '1px solid #333',
  },
  title: {
    color: '#4ade80',
    fontSize: 18,
    fontWeight: 700,
    margin: 0,
  },
  closeBtn: {
    background: 'none',
    border: 'none',
    color: '#888',
    fontSize: 18,
    cursor: 'pointer',
    padding: '4px 8px',
  },
  saveBtn: {
    background: '#2a2a4e',
    border: '1px solid #555',
    color: '#ccc',
    fontSize: 12,
    cursor: 'pointer',
    padding: '6px 12px',
    borderRadius: 4,
    fontFamily: 'monospace',
  },
  message: {
    margin: '8px 20px 0',
    padding: '8px 12px',
    borderRadius: 4,
    fontSize: 13,
    border: '1px solid',
    color: '#e0e6ff',
  },
  saveForm: {
    padding: '12px 20px',
    borderBottom: '1px solid #333',
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
  },
  input: {
    background: '#111',
    border: '1px solid #444',
    color: '#e0e6ff',
    padding: '8px 12px',
    borderRadius: 4,
    fontSize: 13,
    fontFamily: 'monospace',
    outline: 'none',
  },
  scrollArea: {
    flex: 1,
    overflow: 'auto',
    padding: '12px 20px 20px',
  },
  sectionTitle: {
    color: '#8892b0',
    fontSize: 13,
    fontWeight: 600,
    marginBottom: 8,
    marginTop: 12,
  },
  grid: {
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
  },
  card: {
    background: '#16213e',
    border: '1px solid #333',
    borderRadius: 8,
    padding: 16,
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
  cardTitle: {
    color: '#e0e6ff',
    fontSize: 15,
    fontWeight: 600,
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  cardDesc: {
    color: '#8892b0',
    fontSize: 13,
    marginTop: 4,
  },
  cardMeta: {
    color: '#555',
    fontSize: 11,
    marginTop: 6,
  },
  applyBtn: {
    background: '#4ade80',
    color: '#000',
    border: 'none',
    borderRadius: 4,
    padding: '8px 16px',
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
    fontFamily: 'monospace',
    alignSelf: 'flex-start',
  },
  cancelBtn: {
    background: '#333',
    color: '#ccc',
    border: 'none',
    borderRadius: 4,
    padding: '8px 16px',
    fontSize: 13,
    cursor: 'pointer',
    fontFamily: 'monospace',
  },
  confirmArea: {
    padding: '8px 0',
  },
  optionBtn: {
    background: 'none',
    border: '1px solid #555',
    color: '#ccc',
    borderRadius: 4,
    padding: '4px 12px',
    fontSize: 12,
    cursor: 'pointer',
    fontFamily: 'monospace',
  },
  deleteBtn: {
    background: 'none',
    border: 'none',
    fontSize: 14,
    cursor: 'pointer',
    padding: '0 4px',
  },
};
