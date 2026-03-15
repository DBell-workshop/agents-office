import React, { useCallback, useEffect, useRef, useState } from 'react';

interface CollectorStatus {
  status: string;
  platform: string;
  query: string;
  product_count: number;
}

interface CollectorProduct {
  name: string;
  brand?: string;
  price?: number;
  original_price?: number;
  platform?: string;
  shop_name?: string;
  product_id?: string;
}

interface Props {
  onClose: () => void;
}

const PLATFORMS = [
  { value: 'https://www.jd.com', label: '京东' },
  { value: 'https://www.taobao.com', label: '淘宝' },
  { value: 'https://www.pinduoduo.com', label: '拼多多' },
];

export const CollectorPanel: React.FC<Props> = ({ onClose }) => {
  const [status, setStatus] = useState<CollectorStatus>({
    status: 'idle', platform: '', query: '', product_count: 0,
  });
  const [products, setProducts] = useState<CollectorProduct[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedPlatform, setSelectedPlatform] = useState(PLATFORMS[0].value);
  const eventSourceRef = useRef<EventSource | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const addLog = useCallback((msg: string) => {
    const time = new Date().toLocaleTimeString('zh-CN', { hour12: false });
    setLogs((prev) => [...prev.slice(-200), `[${time}] ${msg}`]);
  }, []);

  // 从后端加载持久化日志
  const loadPersistedLogs = useCallback(() => {
    fetch('/api/v1/office/collector/logs')
      .then((r) => r.json())
      .then((env) => {
        const items = env?.data?.logs || [];
        if (items.length > 0) {
          const formatted = items.map((item: any) => {
            const ts = item.timestamp ? new Date(item.timestamp).toLocaleTimeString('zh-CN', { hour12: false }) : '??:??:??';
            const detail = item.message || item.error || `${item.query || ''}`;
            return `[${ts}] ${item.type}: ${detail}`;
          });
          setLogs(formatted);
        }
      })
      .catch(() => {});
  }, []);

  // 滚动日志到底部
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  // 轮询状态
  const syncStatus = useCallback(() => {
    fetch('/api/v1/office/collector/status')
      .then((r) => r.json())
      .then((env) => {
        if (env?.data) setStatus(env.data);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    syncStatus();
    loadPersistedLogs();
    const interval = setInterval(syncStatus, 3000);
    return () => clearInterval(interval);
  }, [syncStatus, loadPersistedLogs]);

  // 连接 SSE 事件流
  const connectSSE = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    const es = new EventSource('/api/v1/office/collector/events');
    eventSourceRef.current = es;

    es.addEventListener('collector', (e) => {
      try {
        const data = JSON.parse(e.data);
        addLog(`${data.type}: ${data.message || data.query || JSON.stringify(data).slice(0, 80)}`);

        if (data.type === 'products_extracted' && data.products) {
          setProducts((prev) => [...prev, ...data.products]);
          setStatus((prev) => ({ ...prev, product_count: data.total_count || prev.product_count }));
        }

        syncStatus();
      } catch { /* ignore parse errors */ }
    });

    es.addEventListener('heartbeat', () => { syncStatus(); });

    es.onerror = () => {
      es.close();
      eventSourceRef.current = null;
    };
  }, [addLog, syncStatus]);

  useEffect(() => {
    return () => {
      eventSourceRef.current?.close();
    };
  }, []);

  // 打开浏览器
  const handleOpen = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/v1/office/collector/open', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ start_url: selectedPlatform }),
      });
      const env = await res.json();
      if (env?.error) {
        addLog(`错误: ${env.error}`);
      } else {
        addLog('浏览器已启动');
        setStatus(env.data);
        connectSSE();
      }
    } catch (e: any) {
      addLog(`启动失败: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  // 关闭浏览器
  const handleClose = async () => {
    try {
      await fetch('/api/v1/office/collector/close', { method: 'POST' });
      addLog('浏览器已关闭');
      eventSourceRef.current?.close();
      eventSourceRef.current = null;
      setStatus({ status: 'idle', platform: '', query: '', product_count: 0 });
    } catch { /* ignore */ }
  };

  // 加载已采集商品
  const loadProducts = async () => {
    try {
      const res = await fetch('/api/v1/office/collector/products');
      const env = await res.json();
      if (env?.data?.products) {
        setProducts(env.data.products);
      }
    } catch { /* ignore */ }
  };

  useEffect(() => {
    if (status.status !== 'idle') loadProducts();
  }, [status.status]);

  const isOpen = status.status !== 'idle' && status.status !== 'closed';
  const statusLabels: Record<string, string> = {
    idle: '未启动',
    browser_open: '浏览器已打开',
    collecting: '采集中',
    paused: '已暂停',
    closed: '已关闭',
  };

  return (
    <div style={styles.backdrop} onClick={onClose}>
      <div style={styles.panel} onClick={(e) => e.stopPropagation()}>
        {/* 标题栏 */}
        <div style={styles.header}>
          <span style={{ color: '#4ade80', fontWeight: 'bold', fontSize: 15 }}>
            浏览器采集控制
          </span>
          <button onClick={onClose} style={styles.closeBtn}>×</button>
        </div>

        {/* 状态区 */}
        <div style={styles.section}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
              width: 10, height: 10, borderRadius: '50%',
              background: isOpen ? '#4ade80' : '#666',
              boxShadow: isOpen ? '0 0 6px #4ade80' : 'none',
            }} />
            <span style={{ color: '#ddd', fontSize: 13 }}>
              状态: {statusLabels[status.status] || status.status}
            </span>
            {status.platform && (
              <span style={{ color: '#ccaa66', fontSize: 12, marginLeft: 'auto' }}>
                {status.platform}
              </span>
            )}
          </div>
          {status.query && (
            <div style={{ color: '#aaa', fontSize: 12, marginTop: 4 }}>
              搜索词: {status.query} | 已采集: {status.product_count} 个商品
            </div>
          )}
        </div>

        {/* 操作区 */}
        {!isOpen ? (
          <div style={styles.section}>
            <label style={{ color: '#aaa', fontSize: 12, display: 'block', marginBottom: 4 }}>
              选择平台
            </label>
            <select
              value={selectedPlatform}
              onChange={(e) => setSelectedPlatform(e.target.value)}
              style={styles.select}
            >
              {PLATFORMS.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
            <button
              onClick={handleOpen}
              disabled={loading}
              style={{ ...styles.primaryBtn, marginTop: 8, opacity: loading ? 0.6 : 1 }}
            >
              {loading ? '启动中…' : '启动浏览器'}
            </button>
            <div style={{ color: '#888', fontSize: 11, marginTop: 6 }}>
              启动后会打开一个可见的浏览器窗口，请先手动登录电商平台账号，然后在浏览器中的浮窗控制台操作采集。
            </div>
          </div>
        ) : (
          <div style={styles.section}>
            <button onClick={handleClose} style={styles.dangerBtn}>
              关闭浏览器
            </button>
          </div>
        )}

        {/* 日志区 */}
        <div style={styles.section}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
            <span style={{ color: '#aaa', fontSize: 12 }}>采集日志 ({logs.length})</span>
            <div style={{ display: 'flex', gap: 4 }}>
              {logs.length > 0 && (
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(logs.join('\n')).then(() => {
                      const btn = document.getElementById('__copy_logs_btn');
                      if (btn) { btn.textContent = '已复制'; setTimeout(() => { btn.textContent = '复制日志'; }, 1500); }
                    });
                  }}
                  id="__copy_logs_btn"
                  style={{
                    background: 'none', border: '1px solid #4ade80', borderRadius: 3,
                    color: '#4ade80', fontSize: 10, padding: '1px 6px', cursor: 'pointer',
                    fontFamily: 'monospace',
                  }}
                >
                  复制日志
                </button>
              )}
              {logs.length > 0 && (
                <button
                  onClick={async () => {
                    await fetch('/api/v1/office/collector/logs', { method: 'DELETE' });
                    setLogs([]);
                  }}
                  style={{
                    background: 'none', border: '1px solid #666', borderRadius: 3,
                    color: '#888', fontSize: 10, padding: '1px 6px', cursor: 'pointer',
                    fontFamily: 'monospace',
                  }}
                >
                  清空日志
                </button>
              )}
            </div>
          </div>
          <div style={styles.logBox}>
            {logs.length === 0 && (
              <div style={{ color: '#555', fontSize: 12 }}>暂无日志</div>
            )}
            {logs.map((log, i) => (
              <div key={i} style={{ color: '#bbb', fontSize: 11, lineHeight: 1.5 }}>{log}</div>
            ))}
            <div ref={logsEndRef} />
          </div>
        </div>

        {/* 商品列表 */}
        {products.length > 0 && (
          <div style={styles.section}>
            <div style={{ color: '#aaa', fontSize: 12, marginBottom: 4 }}>
              已采集商品 ({products.length})
            </div>
            <div style={styles.productList}>
              {products.map((p, i) => (
                <div key={p.product_id || i} style={styles.productCard}>
                  <div style={{ color: '#eee', fontSize: 12, fontWeight: 'bold' }}>
                    {p.name?.slice(0, 40)}{p.name && p.name.length > 40 ? '…' : ''}
                  </div>
                  <div style={{ display: 'flex', gap: 8, marginTop: 2 }}>
                    {p.price != null && (
                      <span style={{ color: '#ef4444', fontSize: 12, fontWeight: 'bold' }}>
                        ¥{p.price}
                      </span>
                    )}
                    {p.platform && (
                      <span style={{ color: '#888', fontSize: 11 }}>{p.platform}</span>
                    )}
                    {p.shop_name && (
                      <span style={{ color: '#888', fontSize: 11, marginLeft: 'auto' }}>
                        {p.shop_name}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  backdrop: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.5)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 10000,
    pointerEvents: 'auto',
  },
  panel: {
    width: 460,
    maxHeight: '80vh',
    background: '#1a1a2e',
    border: '2px solid #4ade80',
    borderRadius: 10,
    fontFamily: 'monospace',
    overflow: 'auto',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '12px 16px',
    borderBottom: '1px solid #333',
  },
  closeBtn: {
    background: 'none',
    border: 'none',
    color: '#999',
    fontSize: 20,
    cursor: 'pointer',
    lineHeight: 1,
  },
  section: {
    padding: '10px 16px',
    borderBottom: '1px solid #222',
  },
  select: {
    width: '100%',
    boxSizing: 'border-box' as const,
    padding: '6px 8px',
    border: '1px solid #555',
    borderRadius: 4,
    background: '#2a2a3e',
    color: '#eee',
    fontSize: 13,
    outline: 'none',
    fontFamily: 'monospace',
  },
  primaryBtn: {
    width: '100%',
    padding: '8px 0',
    border: 'none',
    borderRadius: 4,
    background: '#4ade80',
    color: '#000',
    fontWeight: 'bold',
    fontSize: 14,
    cursor: 'pointer',
    fontFamily: 'monospace',
  },
  dangerBtn: {
    width: '100%',
    padding: '8px 0',
    border: '1px solid #ef4444',
    borderRadius: 4,
    background: 'transparent',
    color: '#ef4444',
    fontSize: 13,
    cursor: 'pointer',
    fontFamily: 'monospace',
  },
  logBox: {
    maxHeight: 120,
    overflow: 'auto',
    background: '#111',
    borderRadius: 4,
    padding: 8,
    border: '1px solid #333',
  },
  productList: {
    maxHeight: 200,
    overflow: 'auto',
  },
  productCard: {
    padding: '6px 0',
    borderBottom: '1px solid #222',
  },
};
