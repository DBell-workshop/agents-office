import React, { useEffect, useState, useCallback } from 'react';

interface TableColumn {
  name: string;
  type: string;
}

interface TableInfo {
  table_name: string;
  row_count: number;
  columns: TableColumn[];
}

interface UploadedFile {
  file_name: string;
  file_path: string;
  size_bytes: number;
  extension: string;
}

interface FilePreview {
  file_name: string;
  total_rows: number;
  total_columns: number;
  columns: { original_name: string; safe_name: string; sql_type: string; null_count: number; unique_count: number; sample_values: string[] }[];
  preview: Record<string, any>[];
}

interface Props {
  onClose: () => void;
}

export const DatabasePanel: React.FC<Props> = ({ onClose }) => {
  const [tables, setTables] = useState<TableInfo[]>([]);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [tableData, setTableData] = useState<{ columns: string[]; rows: any[][] } | null>(null);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [filePreview, setFilePreview] = useState<FilePreview | null>(null);
  const [loadingTables, setLoadingTables] = useState(true);
  const [loadingData, setLoadingData] = useState(false);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState<'tables' | 'files'>('tables');

  // 加载表列表，返回表列表供后续自动选中
  const loadTables = useCallback(async (): Promise<TableInfo[]> => {
    setLoadingTables(true);
    setError('');
    try {
      const res = await fetch('/api/v1/office/user-tables');
      const envelope = await res.json();
      const data = envelope?.data;
      if (data?.error) {
        setError(data.error);
        return [];
      } else {
        const list: TableInfo[] = data?.tables || [];
        setTables(list);
        return list;
      }
    } catch {
      setError('无法连接到后端服务');
      return [];
    } finally {
      setLoadingTables(false);
    }
  }, []);

  // 加载文件列表
  const loadFiles = useCallback(async () => {
    try {
      const res = await fetch('/api/v1/office/uploads');
      const envelope = await res.json();
      setFiles(envelope?.data?.files || []);
    } catch {
      // 静默失败
    }
  }, []);

  useEffect(() => {
    loadTables().then((list) => {
      // 自动选中第一个表并加载数据
      if (list.length > 0) {
        loadTableData(list[0].table_name);
      }
    });
    loadFiles();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 查询表数据
  const loadTableData = useCallback(async (tableName: string) => {
    setSelectedTable(tableName);
    setLoadingData(true);
    setTableData(null);
    try {
      const res = await fetch(`/api/v1/office/user-tables/${tableName}/data?limit=100`);
      const envelope = await res.json();
      const data = envelope?.data;
      if (data?.error) {
        setError(data.error);
      } else if (data?.type === 'query') {
        // 后端返回 rows 为 dict 数组，转成二维数组供渲染
        const cols: string[] = data.columns || [];
        const arrayRows = (data.rows || []).map((row: any) =>
          Array.isArray(row) ? row : cols.map((c) => row[c] ?? null)
        );
        setTableData({ columns: cols, rows: arrayRows });
      }
    } catch {
      setError('查询数据失败');
    } finally {
      setLoadingData(false);
    }
  }, []);

  // 加载文件预览
  const loadFilePreview = useCallback(async (fileName: string) => {
    setSelectedFile(fileName);
    setLoadingData(true);
    setFilePreview(null);
    try {
      const res = await fetch(`/api/v1/office/uploads/${encodeURIComponent(fileName)}/preview`);
      const envelope = await res.json();
      const data = envelope?.data;
      if (data?.error) {
        setError(data.error);
      } else {
        setFilePreview(data as FilePreview);
      }
    } catch {
      setError('文件预览加载失败');
    } finally {
      setLoadingData(false);
    }
  }, []);

  const selectedTableInfo = tables.find((t) => t.table_name === selectedTable);

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  // SQL 类型 → 颜色映射
  const typeColor = (t: string) => {
    if (t.includes('int') || t.includes('numeric') || t.includes('float') || t.includes('double')) return '#60a5fa';
    if (t.includes('char') || t.includes('text')) return '#4ade80';
    if (t.includes('bool')) return '#f472b6';
    if (t.includes('date') || t.includes('time')) return '#fbbf24';
    return '#a78bfa';
  };

  return (
    <div style={S.overlay} onClick={onClose}>
      <div style={S.panel} onClick={(e) => e.stopPropagation()}>
        {/* 标题栏 */}
        <div style={S.titleBar}>
          <div style={S.titleLeft}>
            <span style={S.titleIcon}>🗄️</span>
            <span style={S.titleText}>数据库管理</span>
          </div>
          <button style={S.closeBtn} onClick={onClose}>✕</button>
        </div>

        {/* Tab 切换 */}
        <div style={S.tabBar}>
          <button
            style={activeTab === 'tables' ? { ...S.tab, ...S.tabActive } : S.tab}
            onClick={() => { setActiveTab('tables'); setSelectedFile(null); setFilePreview(null); }}
          >
            📊 数据表 ({tables.length})
          </button>
          <button
            style={activeTab === 'files' ? { ...S.tab, ...S.tabActive } : S.tab}
            onClick={() => { setActiveTab('files'); setSelectedTable(null); setTableData(null); }}
          >
            📁 上传文件 ({files.length})
          </button>
          <button style={S.refreshBtn} onClick={() => { loadTables(); loadFiles(); }}>🔄</button>
        </div>

        {error && <div style={S.errorMsg}>{error}</div>}

        <div style={S.body}>
          {/* 左栏：表列表 / 文件列表 */}
          <div style={S.sidebar}>
            {activeTab === 'tables' ? (
              loadingTables ? (
                <div style={S.loading}>加载中...</div>
              ) : tables.length === 0 ? (
                <div style={S.empty}>
                  <div style={{ fontSize: 32, marginBottom: 8 }}>📭</div>
                  <div>暂无数据表</div>
                  <div style={{ fontSize: 11, color: '#888', marginTop: 4 }}>
                    上传 CSV/Excel 文件并让数据工程师导入
                  </div>
                </div>
              ) : (
                tables.map((t) => (
                  <div
                    key={t.table_name}
                    style={{
                      ...S.tableItem,
                      ...(selectedTable === t.table_name ? S.tableItemActive : {}),
                    }}
                    onClick={() => loadTableData(t.table_name)}
                  >
                    <div style={S.tableItemName}>
                      <span style={{ color: '#60a5fa' }}>⊞</span>{' '}
                      {t.table_name.replace('ud_', '')}
                    </div>
                    <div style={S.tableItemMeta}>
                      {t.row_count} 行 · {t.columns.length} 列
                    </div>
                  </div>
                ))
              )
            ) : (
              files.length === 0 ? (
                <div style={S.empty}>
                  <div style={{ fontSize: 32, marginBottom: 8 }}>📂</div>
                  <div>暂无上传文件</div>
                </div>
              ) : (
                files.map((f) => (
                  <div
                    key={f.file_name}
                    style={{
                      ...S.tableItem,
                      ...(selectedFile === f.file_name ? S.tableItemActive : {}),
                    }}
                    onClick={() => loadFilePreview(f.file_name)}
                  >
                    <div style={S.tableItemName}>
                      <span style={{ color: '#4ade80' }}>
                        {f.extension === '.csv' ? '📄' : '📊'}
                      </span>{' '}
                      {f.file_name}
                    </div>
                    <div style={S.tableItemMeta}>
                      {formatBytes(f.size_bytes)} · {f.extension}
                    </div>
                  </div>
                ))
              )
            )}
          </div>

          {/* 右栏：表结构 + 数据预览 / 文件预览 */}
          <div style={S.main}>
            {loadingData ? (
              <div style={S.mainEmpty}>
                <div style={S.loading}>加载中...</div>
              </div>
            ) : selectedTable && selectedTableInfo ? (
              <>
                {/* 表头信息 */}
                <div style={S.tableHeader}>
                  <span style={S.tableName}>{selectedTableInfo.table_name}</span>
                  <span style={S.tableStats}>
                    {selectedTableInfo.row_count} 行 · {selectedTableInfo.columns.length} 列
                  </span>
                </div>

                {/* Schema 卡片 */}
                <div style={S.schemaCard}>
                  <div style={S.schemaTitle}>表结构 (Schema)</div>
                  <table style={S.schemaTable}>
                    <thead>
                      <tr>
                        <th style={S.schemaTh}>列名</th>
                        <th style={S.schemaTh}>数据类型</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedTableInfo.columns.map((col, i) => (
                        <tr key={col.name} style={i % 2 === 1 ? S.schemaRowAlt : undefined}>
                          <td style={S.schemaTd}>{col.name}</td>
                          <td style={{ ...S.schemaTd, color: typeColor(col.type) }}>{col.type}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* 数据预览 */}
                <div style={S.dataSection}>
                  <div style={S.schemaTitle}>数据预览 (前 100 行)</div>
                  {tableData ? (
                    <div style={S.dataTableWrap}>
                      <table style={S.dataTable}>
                        <thead>
                          <tr>
                            <th style={S.dataTh}>#</th>
                            {tableData.columns.map((col) => (
                              <th key={col} style={S.dataTh}>{col}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {tableData.rows.map((row, ri) => (
                            <tr key={ri} style={ri % 2 === 1 ? S.dataRowAlt : undefined}>
                              <td style={{ ...S.dataTd, color: '#666' }}>{ri + 1}</td>
                              {row.map((cell, ci) => (
                                <td key={ci} style={S.dataTd}>
                                  {cell === null ? (
                                    <span style={{ color: '#666', fontStyle: 'italic' }}>NULL</span>
                                  ) : (
                                    String(cell)
                                  )}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div style={S.loading}>暂无数据</div>
                  )}
                </div>
              </>
            ) : selectedFile && filePreview ? (
              <>
                {/* 文件预览头 */}
                <div style={S.tableHeader}>
                  <span style={S.tableName}>📄 {filePreview.file_name}</span>
                  <span style={S.tableStats}>
                    {filePreview.total_rows} 行 · {filePreview.total_columns} 列
                  </span>
                </div>

                {/* 文件列信息 */}
                <div style={S.schemaCard}>
                  <div style={S.schemaTitle}>文件结构 (Columns)</div>
                  <table style={S.schemaTable}>
                    <thead>
                      <tr>
                        <th style={S.schemaTh}>原始列名</th>
                        <th style={S.schemaTh}>安全列名</th>
                        <th style={S.schemaTh}>推断类型</th>
                        <th style={S.schemaTh}>空值</th>
                        <th style={S.schemaTh}>唯一值</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filePreview.columns.map((col, i) => (
                        <tr key={col.original_name} style={i % 2 === 1 ? S.schemaRowAlt : undefined}>
                          <td style={S.schemaTd}>{col.original_name}</td>
                          <td style={{ ...S.schemaTd, color: '#a78bfa' }}>{col.safe_name}</td>
                          <td style={{ ...S.schemaTd, color: typeColor(col.sql_type.toLowerCase()) }}>{col.sql_type}</td>
                          <td style={{ ...S.schemaTd, color: col.null_count > 0 ? '#fbbf24' : '#666' }}>{col.null_count}</td>
                          <td style={{ ...S.schemaTd, color: '#888' }}>{col.unique_count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* 文件数据预览 */}
                <div style={S.dataSection}>
                  <div style={S.schemaTitle}>数据预览 (前 {filePreview.preview.length} 行)</div>
                  {filePreview.preview.length > 0 ? (
                    <div style={S.dataTableWrap}>
                      <table style={S.dataTable}>
                        <thead>
                          <tr>
                            <th style={S.dataTh}>#</th>
                            {filePreview.columns.map((col) => (
                              <th key={col.original_name} style={S.dataTh}>{col.original_name}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {filePreview.preview.map((row, ri) => (
                            <tr key={ri} style={ri % 2 === 1 ? S.dataRowAlt : undefined}>
                              <td style={{ ...S.dataTd, color: '#666' }}>{ri + 1}</td>
                              {filePreview.columns.map((col) => (
                                <td key={col.original_name} style={S.dataTd}>
                                  {row[col.original_name] === null || row[col.original_name] === '' ? (
                                    <span style={{ color: '#666', fontStyle: 'italic' }}>
                                      {row[col.original_name] === null ? 'NULL' : '(空)'}
                                    </span>
                                  ) : (
                                    String(row[col.original_name])
                                  )}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div style={S.loading}>文件无数据行</div>
                  )}
                </div>
              </>
            ) : (
              <div style={S.mainEmpty}>
                <div style={{ fontSize: 48, marginBottom: 16, opacity: 0.3 }}>🗄️</div>
                <div style={{ color: '#888' }}>
                  {activeTab === 'tables' ? '选择左侧的数据表查看详情' : '选择左侧的文件查看预览'}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// ============================================================
// Supabase-inspired dark terminal styles
// ============================================================
const S: Record<string, React.CSSProperties> = {
  overlay: {
    position: 'fixed',
    top: 0,
    left: 0,
    width: '100%',
    height: '100%',
    background: 'rgba(0, 0, 0, 0.6)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 10000,
    pointerEvents: 'auto',
  },
  panel: {
    width: '90vw',
    maxWidth: 1100,
    height: '80vh',
    background: '#0d0d1a',
    border: '2px solid #333',
    borderRadius: 8,
    display: 'flex',
    flexDirection: 'column',
    fontFamily: 'monospace',
    color: '#e8e8e8',
    overflow: 'hidden',
  },
  titleBar: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '12px 16px',
    borderBottom: '1px solid #333',
    background: 'rgba(255, 255, 255, 0.03)',
  },
  titleLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  titleIcon: {
    fontSize: 20,
  },
  titleText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#ffd700',
  },
  closeBtn: {
    background: 'none',
    border: '1px solid #555',
    borderRadius: 4,
    color: '#999',
    fontSize: 16,
    cursor: 'pointer',
    padding: '4px 10px',
    fontFamily: 'monospace',
  },
  tabBar: {
    display: 'flex',
    gap: 0,
    padding: '0 16px',
    borderBottom: '1px solid #333',
    alignItems: 'center',
  },
  tab: {
    background: 'none',
    border: 'none',
    borderBottom: '2px solid transparent',
    color: '#888',
    padding: '10px 16px',
    cursor: 'pointer',
    fontSize: 13,
    fontFamily: 'monospace',
    transition: 'color 0.15s',
  },
  tabActive: {
    color: '#4ade80',
    borderBottomColor: '#4ade80',
  },
  refreshBtn: {
    background: 'none',
    border: 'none',
    color: '#888',
    cursor: 'pointer',
    fontSize: 14,
    padding: '8px',
    marginLeft: 'auto',
  },
  errorMsg: {
    padding: '8px 16px',
    background: 'rgba(255, 0, 0, 0.1)',
    color: '#ff6b6b',
    fontSize: 13,
    borderBottom: '1px solid #333',
  },
  body: {
    flex: 1,
    display: 'flex',
    overflow: 'hidden',
  },
  sidebar: {
    width: 240,
    borderRight: '1px solid #333',
    overflowY: 'auto',
    flexShrink: 0,
  },
  tableItem: {
    padding: '10px 14px',
    cursor: 'pointer',
    borderBottom: '1px solid rgba(255,255,255,0.05)',
    transition: 'background 0.1s',
  },
  tableItemActive: {
    background: 'rgba(74, 222, 128, 0.1)',
    borderLeft: '3px solid #4ade80',
  },
  tableItemName: {
    fontSize: 13,
    fontWeight: 'bold',
    marginBottom: 3,
  },
  tableItemMeta: {
    fontSize: 11,
    color: '#888',
  },
  empty: {
    padding: 30,
    textAlign: 'center' as const,
    color: '#aaa',
    fontSize: 13,
  },
  loading: {
    padding: 20,
    textAlign: 'center' as const,
    color: '#888',
    fontSize: 13,
  },
  main: {
    flex: 1,
    overflowY: 'auto',
    padding: 16,
  },
  mainEmpty: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
  },
  tableHeader: {
    display: 'flex',
    alignItems: 'baseline',
    gap: 12,
    marginBottom: 16,
  },
  tableName: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#ffd700',
  },
  tableStats: {
    fontSize: 12,
    color: '#888',
  },
  schemaCard: {
    border: '1px solid #333',
    borderRadius: 6,
    overflow: 'hidden',
    marginBottom: 16,
  },
  schemaTitle: {
    padding: '8px 12px',
    fontSize: 12,
    color: '#4ade80',
    fontWeight: 'bold',
    background: 'rgba(74, 222, 128, 0.05)',
    borderBottom: '1px solid #333',
  },
  schemaTable: {
    width: '100%',
    borderCollapse: 'collapse' as const,
    fontSize: 13,
  },
  schemaTh: {
    padding: '6px 12px',
    textAlign: 'left' as const,
    color: '#aaa',
    fontWeight: 'normal',
    borderBottom: '1px solid #333',
    fontSize: 11,
    textTransform: 'uppercase' as const,
    letterSpacing: 1,
  },
  schemaTd: {
    padding: '6px 12px',
    borderBottom: '1px solid rgba(255,255,255,0.04)',
  },
  schemaRowAlt: {
    background: 'rgba(255, 255, 255, 0.02)',
  },
  dataSection: {
    border: '1px solid #333',
    borderRadius: 6,
    overflow: 'hidden',
  },
  dataTableWrap: {
    overflowX: 'auto' as const,
    maxHeight: 400,
    overflowY: 'auto' as const,
  },
  dataTable: {
    width: '100%',
    borderCollapse: 'collapse' as const,
    fontSize: 12,
  },
  dataTh: {
    padding: '6px 10px',
    textAlign: 'left' as const,
    color: '#ffd700',
    fontWeight: 'bold',
    borderBottom: '2px solid #444',
    whiteSpace: 'nowrap' as const,
    position: 'sticky' as const,
    top: 0,
    background: '#0d0d1a',
  },
  dataTd: {
    padding: '5px 10px',
    borderBottom: '1px solid rgba(255,255,255,0.04)',
    whiteSpace: 'nowrap' as const,
    maxWidth: 200,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  dataRowAlt: {
    background: 'rgba(255, 255, 255, 0.02)',
  },
};
