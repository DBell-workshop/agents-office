/**
 * DashboardView — 双皮肤可切换数据大屏系统
 *
 * 支持两套皮肤：
 * - Aurora：浅色极光毛玻璃风格
 * - Genesis：深空暗色有机风格
 *
 * 保留原有数据获取/刷新逻辑（API调用、定时刷新、数据绑定）
 * 皮肤选择保存在 localStorage
 */
import React, { useCallback, useEffect, useRef, useState, useMemo } from 'react';

// ---- Types ----

interface ChartConfig {
  id: string;
  title: string;
  position?: { col: number; row: number; colSpan?: number; rowSpan?: number };
  chart_type: string;
  echarts_option?: Record<string, unknown>;
  kpi_items?: KpiItem[];
  data_query?: { sql?: string; refresh_interval?: number };
}

interface KpiItem {
  label: string;
  unit: string;
  sql?: string;
  format?: string;
  value?: number | string;
}

interface DashboardLayout {
  columns: number;
  rows: number;
  theme: string;
  title: string;
}

interface DashboardConfig {
  dashboard_id: string;
  name: string;
  slug: string;
  description?: string;
  layout: DashboardLayout;
  charts: ChartConfig[];
  refresh_config?: { mode?: string; default_interval?: number; description?: string };
  status: string;
  updated_at?: string;
}

interface DashboardViewProps {
  dashboardId?: string;
  onClose?: () => void;
}

type SkinType = 'aurora' | 'genesis';

// ---- Skin Themes ----

const AURORA = {
  bg: 'linear-gradient(-45deg, #f3e8ff, #e0f2fe, #f0fdf4, #ede9fe)',
  panelBg: 'rgba(255,255,255,0.45)',
  panelBorder: 'rgba(255,255,255,0.3)',
  panelShadow: '0 8px 32px 0 rgba(31,38,135,0.07)',
  panelBlur: 'blur(12px) saturate(180%)',
  cardBg: 'rgba(255,255,255,0.6)',
  cardBorder: 'rgba(255,255,255,0.5)',
  text: '#1e293b',
  textSecondary: '#64748b',
  textMuted: '#94a3b8',
  accent: '#8b5cf6',
  accentSecondary: '#6366f1',
  green: '#34d399',
  greenText: '#16a34a',
  sphereGlow: '0 0 60px 20px rgba(167,139,250,0.3)',
  kpiGradient: 'linear-gradient(135deg, #8b5cf6, #6366f1)',
  funnelColors: ['#ede9fe', '#ddd6fe', '#e0e7ff', '#ecfdf5'],
  funnelTextColors: ['#8b5cf6', '#6366f1', '#4f46e5', '#34d399'],
};

const GENESIS = {
  bg: '#0a0b14',
  panelBg: 'rgba(255,255,255,0.05)',
  panelBorder: 'rgba(255,255,255,0.1)',
  panelShadow: '0 8px 32px 0 rgba(0,0,0,0.37)',
  panelBlur: 'blur(12px)',
  cardBg: 'rgba(255,255,255,0.03)',
  cardBorder: 'rgba(255,255,255,0.08)',
  text: '#f8fafc',
  textSecondary: '#94a3b8',
  textMuted: '#64748b',
  accent: '#2dd4bf',
  accentSecondary: '#818cf8',
  green: '#2dd4bf',
  greenText: '#2dd4bf',
  sphereGlow: '0 0 60px 20px rgba(129,140,248,0.2)',
  kpiGradient: 'linear-gradient(135deg, #2dd4bf, #818cf8)',
  funnelColors: ['rgba(255,255,255,0.05)', 'rgba(45,212,191,0.2)', 'rgba(129,140,248,0.2)', 'rgba(255,255,255,0.1)'],
  funnelTextColors: ['#e2e8f0', '#e2e8f0', '#e2e8f0', '#e2e8f0'],
};

// ---- Keyframe Animations ----

const KEYFRAMES = `
@keyframes aurora {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}
@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-20px); }
}
@keyframes spinSlow {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
@keyframes pulseSlow {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}
@keyframes chartDraw {
  from { stroke-dashoffset: 1000; }
  to { stroke-dashoffset: 0; }
}
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes pingDot {
  75%, 100% { transform: scale(2); opacity: 0; }
}
@keyframes orderSlide {
  from { opacity: 0; transform: translateX(20px); }
  to { opacity: 1; transform: translateX(0); }
}
@keyframes breathGlow {
  0%, 100% { box-shadow: 0 0 40px 10px rgba(167,139,250,0.2); }
  50% { box-shadow: 0 0 80px 30px rgba(167,139,250,0.4); }
}
@keyframes genesisGlow {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 0.5; }
}
@keyframes dashScanline {
  0% { transform: translateY(-100%); }
  100% { transform: translateY(100vh); }
}
`;

// ---- Shared Data Hook ----

function useDashboardData(selectedId: string | undefined) {
  const [dashboard, setDashboard] = useState<DashboardConfig | null>(null);
  const [dashboardList, setDashboardList] = useState<DashboardConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<string>('');
  const [liveData, setLiveData] = useState<Record<string, unknown>>({});
  const refreshTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadList = useCallback(async () => {
    try {
      const res = await fetch('/api/v1/office/dashboards');
      const json = await res.json();
      if (json.data?.dashboards) {
        setDashboardList(json.data.dashboards);
      }
    } catch { /* silent */ }
  }, []);

  const loadDashboard = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/v1/office/dashboards/${id}`);
      const json = await res.json();
      if (json.error) {
        setError(json.error);
      } else {
        setDashboard(json.data);
        setLastRefresh(new Date().toLocaleTimeString());
      }
    } catch (e) {
      setError(`加载失败: ${e}`);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleRefresh = useCallback(async () => {
    if (!selectedId) return;
    try {
      const res = await fetch(`/api/v1/office/dashboards/${selectedId}/refresh`, { method: 'POST' });
      const json = await res.json();
      const results = json.data?.results || {};
      setLiveData(results);
      setLastRefresh(new Date().toLocaleTimeString());
    } catch { /* silent */ }
  }, [selectedId]);

  useEffect(() => {
    loadList();
    if (selectedId) {
      loadDashboard(selectedId).then(() => {
        fetch(`/api/v1/office/dashboards/${selectedId}/refresh`, { method: 'POST' })
          .then(r => r.json())
          .then(json => {
            setLiveData(json.data?.results || {});
            setLastRefresh(new Date().toLocaleTimeString());
          })
          .catch(() => {});
      });
    } else {
      setLoading(false);
    }
  }, [selectedId, loadDashboard, loadList]);

  useEffect(() => {
    if (refreshTimerRef.current) clearInterval(refreshTimerRef.current);
    if (!dashboard?.refresh_config?.default_interval || !selectedId) return;
    const interval = dashboard.refresh_config.default_interval * 1000;
    refreshTimerRef.current = setInterval(() => {
      handleRefresh();
    }, interval);
    return () => {
      if (refreshTimerRef.current) clearInterval(refreshTimerRef.current);
    };
  }, [dashboard, selectedId, handleRefresh]);

  return { dashboard, dashboardList, loading, error, lastRefresh, liveData, handleRefresh, loadList };
}

// ---- Data Binding Utilities (preserved from original) ----

function mergeDataIntoOption(
  baseOption: Record<string, unknown>,
  chartType: string,
  result: Record<string, unknown> | undefined,
): Record<string, unknown> {
  if (!result || result.status !== 'ok') {
    if (chartType === 'funnel') {
      const option = JSON.parse(JSON.stringify(baseOption));
      const series = (option.series || []) as Array<Record<string, unknown>>;
      if (series[0]) {
        series[0].data = [
          { value: 10000, name: '浏览' },
          { value: 5200, name: '加购' },
          { value: 3100, name: '下单' },
          { value: 2000, name: '支付' },
        ];
        series[0].sort = 'descending';
        series[0].gap = 4;
        series[0].min = 0;
        series[0].max = 10000;
      }
      return option;
    }
    return baseOption;
  }
  const data = result.data as { rows?: Array<Record<string, unknown>>; columns?: string[] } | undefined;
  if (!data?.rows?.length) return baseOption;

  const rows = data.rows;
  const option = JSON.parse(JSON.stringify(baseOption));

  if (chartType === 'line' || chartType === 'bar') {
    const cols = data.columns || Object.keys(rows[0]);
    const xKey = cols[0];
    const yKeys = cols.slice(1);
    const xData = rows.map(r => {
      const v = r[xKey];
      if (typeof v === 'string' && v.includes('T')) {
        const d = new Date(v);
        return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
      }
      return String(v);
    });
    if (option.xAxis) {
      const xAxis = Array.isArray(option.xAxis) ? option.xAxis[0] : option.xAxis;
      (xAxis as Record<string, unknown>).data = xData;
    }
    const series = (option.series || []) as Array<Record<string, unknown>>;
    yKeys.forEach((yKey, i) => {
      if (series[i]) {
        series[i].data = rows.map(r => Number(r[yKey]) || 0);
      } else {
        series.push({ type: chartType, data: rows.map(r => Number(r[yKey]) || 0) });
      }
    });
    option.series = series;
  } else if (chartType === 'pie') {
    const cols = data.columns || Object.keys(rows[0]);
    const nameKey = cols[0];
    const valueKey = cols[1];
    const series = (option.series || []) as Array<Record<string, unknown>>;
    if (series[0]) {
      series[0].data = rows.map(r => ({ name: String(r[nameKey]), value: Number(r[valueKey]) || 0 }));
    }
  } else if (chartType === 'gauge') {
    const firstRow = rows[0];
    const val = Number(Object.values(firstRow)[0]) || 0;
    const series = (option.series || []) as Array<Record<string, unknown>>;
    if (series[0]) {
      const gaugeData = (series[0].data || []) as Array<Record<string, unknown>>;
      if (gaugeData[0]) gaugeData[0].value = val;
    }
  } else if (chartType === 'funnel') {
    const series = (option.series || []) as Array<Record<string, unknown>>;
    if (series[0]) {
      series[0].data = [
        { value: 10000, name: '浏览' },
        { value: 5200, name: '加购' },
        { value: 3100, name: '下单' },
        { value: 2000, name: '支付' },
      ];
      series[0].type = 'funnel';
      series[0].left = '10%';
      series[0].width = '80%';
      series[0].top = 10;
      series[0].bottom = 10;
      series[0].min = 0;
      series[0].max = 10000;
      series[0].sort = 'descending';
      series[0].gap = 2;
      series[0].label = { show: true, position: 'inside', formatter: '{b}\n{c}', color: '#fff', fontSize: 12 };
      series[0].itemStyle = { borderColor: 'rgba(0,0,0,0.2)', borderWidth: 1 };
    }
  }
  return option;
}

function resolveKpiValues(
  items: KpiItem[],
  result: Record<string, unknown> | undefined,
): KpiItem[] {
  if (!result || result.status !== 'ok') return items;
  const kpiValues = result.kpi_values as Array<{ label: string; value: number | null }> | undefined;
  if (!kpiValues) return items;
  return items.map((item, i) => {
    const live = kpiValues[i];
    if (live?.value != null) {
      let formatted: string | number = live.value;
      if (item.format) {
        try {
          if (item.format.includes('d')) {
            formatted = Math.round(live.value).toLocaleString();
          } else if (item.format.includes('f')) {
            const decimals = parseInt(item.format.match(/\.(\d+)/)?.[1] || '1');
            formatted = live.value.toLocaleString(undefined, {
              minimumFractionDigits: decimals,
              maximumFractionDigits: decimals,
            });
          } else {
            formatted = live.value;
          }
        } catch {
          formatted = live.value;
        }
      }
      return { ...item, value: formatted };
    }
    return item;
  });
}

// ---- Extract KPI data from dashboard for skins ----

interface ExtractedData {
  gmv: number;
  orders: number;
  avgOrderValue: number;
  conversionRate: number;
  uv: number;
  trendPoints: number[];
  channels: Array<{ name: string; value: number; percent: number }>;
  funnelSteps: Array<{ name: string; percent: number }>;
}

function extractDashboardData(
  dashboard: DashboardConfig | null,
  liveData: Record<string, unknown>,
): ExtractedData {
  const defaults: ExtractedData = {
    gmv: 4285120,
    orders: 12840,
    avgOrderValue: 333.85,
    conversionRate: 3.5,
    uv: 1800000,
    trendPoints: [40, 45, 38, 52, 48, 60, 55, 65, 50, 70, 68, 80],
    channels: [
      { name: '社交媒体', value: 42, percent: 42 },
      { name: '自然搜索', value: 38, percent: 38 },
      { name: '直接访问', value: 12, percent: 12 },
      { name: '付费推广', value: 8, percent: 8 },
    ],
    funnelSteps: [
      { name: '浏览', percent: 100 },
      { name: '加购', percent: 42.8 },
      { name: '下单', percent: 18.2 },
      { name: '支付', percent: 3.5 },
    ],
  };

  if (!dashboard) return defaults;

  // Try to extract KPI values from charts
  for (const chart of dashboard.charts) {
    if (chart.chart_type === 'kpi_cards' && chart.kpi_items) {
      const resolved = resolveKpiValues(chart.kpi_items, liveData[chart.id] as Record<string, unknown> | undefined);
      for (const item of resolved) {
        const val = typeof item.value === 'number' ? item.value : parseFloat(String(item.value || '').replace(/,/g, ''));
        if (isNaN(val)) continue;
        const label = item.label.toLowerCase();
        if (label.includes('gmv') || label.includes('销售额') || label.includes('交易额')) defaults.gmv = val;
        else if (label.includes('订单') || label.includes('order')) defaults.orders = val;
        else if (label.includes('客单价') || label.includes('avg')) defaults.avgOrderValue = val;
        else if (label.includes('转化') || label.includes('conversion')) defaults.conversionRate = val;
        else if (label.includes('uv') || label.includes('访客') || label.includes('活跃')) defaults.uv = val;
      }
    }
    // Try to extract trend data from line charts
    if (chart.chart_type === 'line' && chart.id.includes('gmv')) {
      const merged = mergeDataIntoOption(chart.echarts_option || {}, 'line', liveData[chart.id] as Record<string, unknown> | undefined);
      const series = (merged.series || []) as Array<Record<string, unknown>>;
      if (series[0]?.data && Array.isArray(series[0].data)) {
        defaults.trendPoints = (series[0].data as number[]).slice(-12);
      }
    }
    // Extract channel/pie data
    if (chart.chart_type === 'pie' && (chart.id.includes('channel') || chart.title.includes('渠道'))) {
      const merged = mergeDataIntoOption(chart.echarts_option || {}, 'pie', liveData[chart.id] as Record<string, unknown> | undefined);
      const series = (merged.series || []) as Array<Record<string, unknown>>;
      if (series[0]?.data && Array.isArray(series[0].data)) {
        const pieData = series[0].data as Array<{ name: string; value: number }>;
        const total = pieData.reduce((s, d) => s + d.value, 0);
        defaults.channels = pieData.map(d => ({
          name: d.name,
          value: d.value,
          percent: total > 0 ? Math.round((d.value / total) * 100) : 0,
        }));
      }
    }
  }

  return defaults;
}

// ---- Simulated orders for skin display ----

const MOCK_ORDERS = [
  { id: '8821', city: 'BJS', name: '高端科技礼盒', time: '2分钟前', price: 1420, status: '已付款' },
  { id: '8820', city: 'SHH', name: '有机护肤套装', time: '5分钟前', price: 245, status: '运送中' },
  { id: '8819', city: 'GZH', name: '设计师手表V2', time: '7分钟前', price: 890, status: '已付款' },
  { id: '8818', city: 'SZH', name: '智能家居中枢', time: '12分钟前', price: 512, status: '已付款' },
];

// ========================
// SKIN SWITCHER
// ========================

function SkinSwitcher({ skin, onChange, theme }: { skin: SkinType; onChange: (s: SkinType) => void; theme: typeof AURORA }) {
  const isAurora = skin === 'aurora';
  return (
    <div style={{
      display: 'flex',
      gap: 2,
      padding: 3,
      borderRadius: 10,
      background: isAurora ? 'rgba(255,255,255,0.4)' : 'rgba(255,255,255,0.08)',
      backdropFilter: 'blur(8px)',
      border: `1px solid ${isAurora ? 'rgba(255,255,255,0.5)' : 'rgba(255,255,255,0.1)'}`,
    }}>
      {(['aurora', 'genesis'] as SkinType[]).map(s => (
        <button
          key={s}
          onClick={() => onChange(s)}
          style={{
            padding: '5px 14px',
            fontSize: 11,
            fontWeight: skin === s ? 700 : 400,
            letterSpacing: 0.5,
            border: 'none',
            borderRadius: 8,
            cursor: 'pointer',
            transition: 'all 0.25s ease',
            background: skin === s
              ? (s === 'aurora' ? 'linear-gradient(135deg, #8b5cf6, #6366f1)' : 'linear-gradient(135deg, #2dd4bf, #818cf8)')
              : 'transparent',
            color: skin === s ? '#fff' : theme.textSecondary,
          }}
        >
          {s === 'aurora' ? 'Aurora' : 'Genesis'}
        </button>
      ))}
    </div>
  );
}

// ========================
// SKIN: AURORA (Light Aurora)
// ========================

function SkinAurora({
  data,
  dashboard,
  lastRefresh,
  onRefresh,
  onBack,
  onClose,
}: {
  data: ExtractedData;
  dashboard: DashboardConfig;
  lastRefresh: string;
  onRefresh: () => void;
  onBack: () => void;
  onClose?: () => void;
}) {
  const [gmvDisplay, setGmvDisplay] = useState(data.gmv);
  const [orderIndex, setOrderIndex] = useState(0);

  // GMV auto-increment
  useEffect(() => {
    const iv = setInterval(() => {
      setGmvDisplay(prev => prev + Math.floor(Math.random() * 500) + 100);
    }, 3000);
    return () => clearInterval(iv);
  }, []);

  // Order carousel
  useEffect(() => {
    const iv = setInterval(() => {
      setOrderIndex(prev => (prev + 1) % MOCK_ORDERS.length);
    }, 8000);
    return () => clearInterval(iv);
  }, []);

  const visibleOrders = useMemo(() => {
    const arr = [];
    for (let i = 0; i < 4; i++) {
      arr.push(MOCK_ORDERS[(orderIndex + i) % MOCK_ORDERS.length]);
    }
    return arr;
  }, [orderIndex]);

  const T = AURORA;

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999, overflow: 'hidden',
      background: T.bg,
      backgroundSize: '400% 400%',
      animation: 'aurora 15s ease infinite',
      fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      color: T.text,
      display: 'flex', flexDirection: 'column',
    }}>
      {/* Header */}
      <header style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '12px 24px',
        background: T.panelBg,
        backdropFilter: T.panelBlur,
        WebkitBackdropFilter: T.panelBlur,
        border: `1px solid ${T.panelBorder}`,
        borderRadius: 20,
        margin: '16px 24px 0',
        boxShadow: T.panelShadow,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button onClick={onBack} style={{ ...auroraBtn, fontSize: 13 }}>{'<-'} 返回</button>
          <div style={{
            width: 32, height: 32,
            background: 'linear-gradient(135deg, #8b5cf6, #dbeafe)',
            borderRadius: '50%',
            boxShadow: '0 2px 12px rgba(139,92,246,0.3)',
            animation: 'pulseSlow 4s ease infinite',
          }} />
          <h1 style={{
            fontSize: 18, fontWeight: 700, letterSpacing: -0.5, margin: 0,
            background: 'linear-gradient(90deg, #8b5cf6, #6366f1)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          } as React.CSSProperties}>
            {dashboard.layout.title || dashboard.name}
          </h1>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 10, color: T.textMuted, textTransform: 'uppercase', letterSpacing: 2 }}>Live Status</span>
          <span style={{
            width: 6, height: 6, borderRadius: '50%', background: '#22c55e',
            display: 'inline-block', animation: 'pulseSlow 2s ease infinite',
          }} />
          <span style={{ fontSize: 12, color: T.textSecondary }}>更新于 {lastRefresh}</span>
          <button onClick={onRefresh} style={auroraBtn}>刷新</button>
          {onClose && <button onClick={onClose} style={auroraBtn}>X</button>}
        </div>
      </header>

      {/* Main Grid: 3 - 6 - 3 */}
      <main style={{
        flex: 1, display: 'grid',
        gridTemplateColumns: '1fr 2fr 1fr',
        gap: 20, padding: '16px 24px 24px',
        overflow: 'hidden',
      }}>
        {/* Left Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, overflow: 'auto' }}>
          {/* Conversion Funnel */}
          <AuroraPanel style={{ flex: 1 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: T.text }}>转化漏斗</h3>
              <span style={{
                fontSize: 10, fontWeight: 700, color: T.accent,
                background: '#f5f3ff', padding: '3px 8px', borderRadius: 999,
              }}>Real-time</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {data.funnelSteps.map((step, i) => {
                const widths = ['100%', '90%', '80%', '70%'];
                return (
                  <div key={i} style={{
                    width: widths[i] || '60%',
                    margin: '0 auto',
                    height: 52,
                    clipPath: 'polygon(10% 0%, 90% 0%, 80% 100%, 20% 100%)',
                    background: T.funnelColors[i] || T.funnelColors[0],
                    color: T.funnelTextColors[i] || T.accent,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontWeight: 600, fontSize: 13,
                  }}>
                    {step.name}: {step.percent}%
                  </div>
                );
              })}
            </div>
            <p style={{ marginTop: 12, fontSize: 11, color: T.textMuted, textAlign: 'center' }}>
              转化率较上时段 <span style={{ color: T.greenText, fontWeight: 700 }}>+2.4%</span>
            </p>
          </AuroraPanel>

          {/* Regional Performance */}
          <AuroraPanel style={{ minHeight: 180, position: 'relative', overflow: 'hidden' }}>
            <h3 style={{ margin: '0 0 12px', fontSize: 14, fontWeight: 700, color: T.text }}>区域表现</h3>
            {/* Background SVG decoration */}
            <svg style={{ position: 'absolute', inset: 0, opacity: 0.15, pointerEvents: 'none' }} viewBox="0 0 400 300">
              <path d="M50 150 Q 100 100 200 150 T 350 150" fill="none" stroke="#8b5cf6" strokeWidth="1" />
              <circle cx="80" cy="120" fill="#8b5cf6" r="15" style={{ animation: 'pulseSlow 3s ease infinite' }} />
              <circle cx="220" cy="180" fill="#34d399" r="25" style={{ animation: 'pulseSlow 3s ease infinite 1s' }} />
              <circle cx="310" cy="130" fill="#6366f1" r="10" style={{ animation: 'pulseSlow 3s ease infinite 2s' }} />
            </svg>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0, position: 'relative', zIndex: 1 }}>
              {[
                { region: '华东地区', val: '$2.1M' },
                { region: '华南地区', val: '$1.2M' },
                { region: '华北地区', val: '$980K' },
              ].map((r, i) => (
                <li key={i} style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  fontSize: 13, padding: '8px 0',
                  borderBottom: i < 2 ? '1px solid rgba(0,0,0,0.05)' : 'none',
                }}>
                  <span style={{ color: T.textSecondary }}>{r.region}</span>
                  <span style={{ fontWeight: 700 }}>{r.val}</span>
                </li>
              ))}
            </ul>
          </AuroraPanel>
        </div>

        {/* Center Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
          <AuroraPanel style={{
            flex: 1, borderRadius: 40, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', position: 'relative',
            textAlign: 'center', padding: '32px 40px',
          }}>
            {/* Floating sphere */}
            <div style={{ position: 'relative', marginBottom: 32 }}>
              <div style={{
                width: 200, height: 200, borderRadius: '50%',
                background: 'linear-gradient(135deg, #fff, #dbeafe, #ddd6fe)',
                boxShadow: T.sphereGlow,
                animation: 'float 6s ease-in-out infinite, breathGlow 4s ease infinite',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                overflow: 'hidden',
                position: 'relative',
              }}>
                {/* Inner glow */}
                <div style={{
                  position: 'absolute', inset: 0, opacity: 0.4,
                  background: 'radial-gradient(circle at center, #8b5cf6, #34d399, transparent)',
                  filter: 'blur(30px)',
                  animation: 'pulseSlow 4s ease infinite',
                }} />
                <div style={{ position: 'relative', zIndex: 1, textAlign: 'center' }}>
                  <span style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: 2, color: '#6366f1', fontWeight: 700, display: 'block', marginBottom: 2 }}>Vitality</span>
                  <span style={{ fontSize: 36, fontWeight: 900, color: '#4f46e5' }}>98.2</span>
                </div>
              </div>
            </div>

            {/* GMV */}
            <h2 style={{ fontSize: 14, fontWeight: 600, color: T.textSecondary, marginBottom: 8 }}>实时销售总额 (GMV)</h2>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'center' }}>
              <span style={{
                fontSize: 56, fontWeight: 900, letterSpacing: -2,
                fontFamily: '"DIN Alternate", "Roboto Mono", monospace',
                color: T.text,
                fontVariantNumeric: 'tabular-nums',
                transition: 'all 0.3s ease',
              }}>
                ${gmvDisplay.toLocaleString('en-US')}
              </span>
              <span style={{ fontSize: 24, color: T.textMuted }}>.00</span>
            </div>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: 8,
              background: 'rgba(255,255,255,0.6)', padding: '6px 16px', borderRadius: 999,
              border: '1px solid rgba(255,255,255,0.5)', marginTop: 8,
              boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
            }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#22c55e', display: 'inline-block' }} />
              <span style={{ color: '#16a34a', fontWeight: 700, fontSize: 13 }}>+12.5%</span>
              <span style={{ color: T.textMuted, fontSize: 12 }}>vs 上时段</span>
            </div>

            {/* SVG Trend Line */}
            <div style={{ width: '100%', height: 80, marginTop: 32, padding: '0 20px', position: 'relative' }}>
              <AuroraTrendSVG points={data.trendPoints} />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: T.textMuted, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 2, marginTop: 4, padding: '0 4px' }}>
                <span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>Now</span>
              </div>
            </div>
          </AuroraPanel>
        </div>

        {/* Right Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, overflow: 'auto' }}>
          {/* KPI cards */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <AuroraGlassCard label="活跃买家" value={`${(data.uv / 1e6).toFixed(1)}M`} change="+8%" />
            <AuroraGlassCard label="平均客单价" value={`$${data.avgOrderValue.toFixed(2)}`} change="稳定" changeColor={T.textMuted} />
            <AuroraGlassCard label="订单总数" value={data.orders.toLocaleString()} change="+5.2%" />
          </div>

          {/* Order Feed */}
          <AuroraPanel style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <h3 style={{ margin: '0 0 12px', fontSize: 14, fontWeight: 700, color: T.text }}>高价值订单</h3>
            <div style={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 10 }}>
              {visibleOrders.map((order, i) => (
                <div key={`${order.id}-${i}`} style={{
                  display: 'flex', alignItems: 'center', gap: 10, padding: 10,
                  borderRadius: 14,
                  background: 'rgba(255,255,255,0.4)',
                  border: '1px solid rgba(255,255,255,0.5)',
                  animation: 'orderSlide 0.5s ease',
                  transition: 'all 0.5s ease',
                }}>
                  <div style={{
                    width: 36, height: 36, borderRadius: 10,
                    background: i % 2 === 0 ? '#ede9fe' : '#ecfdf5',
                    color: i % 2 === 0 ? '#8b5cf6' : '#34d399',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 10, fontWeight: 700,
                  }}>{order.city}</div>
                  <div style={{ flex: 1 }}>
                    <p style={{ margin: 0, fontSize: 12, fontWeight: 700, color: T.text }}>{order.name}</p>
                    <p style={{ margin: 0, fontSize: 9, color: T.textMuted }}>{order.time}</p>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <p style={{ margin: 0, fontSize: 13, fontWeight: 900, color: T.text }}>${order.price}</p>
                    <span style={{
                      fontSize: 8, padding: '1px 6px', borderRadius: 999,
                      background: order.status === '已付款' ? '#dcfce7' : '#e0e7ff',
                      color: order.status === '已付款' ? '#16a34a' : '#4f46e5',
                      fontWeight: 700,
                    }}>{order.status}</span>
                  </div>
                </div>
              ))}
            </div>
          </AuroraPanel>
        </div>
      </main>

      {/* Footer */}
      <footer style={{
        padding: '8px 32px',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        fontSize: 9, color: T.textMuted, fontWeight: 500, letterSpacing: 2, textTransform: 'uppercase',
      }}>
        <span>Operational Intelligence v4.0 -- System: Stable</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#818cf8', display: 'inline-block', animation: 'pulseSlow 2s ease infinite' }} />
          Streaming Live Data
        </span>
      </footer>
    </div>
  );
}

function AuroraPanel({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{
      background: AURORA.panelBg,
      backdropFilter: AURORA.panelBlur,
      WebkitBackdropFilter: AURORA.panelBlur,
      border: `1px solid ${AURORA.panelBorder}`,
      boxShadow: AURORA.panelShadow,
      borderRadius: 24,
      padding: 20,
      ...style,
    }}>
      {children}
    </div>
  );
}

function AuroraGlassCard({ label, value, change, changeColor }: {
  label: string; value: string; change: string; changeColor?: string;
}) {
  const [hovered, setHovered] = useState(false);
  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: hovered ? 'rgba(255,255,255,0.8)' : AURORA.cardBg,
        backdropFilter: 'blur(8px)',
        border: `1px solid ${AURORA.cardBorder}`,
        borderRadius: 20,
        padding: '14px 18px',
        transition: 'all 0.3s ease',
        transform: hovered ? 'translateY(-2px)' : 'none',
      }}
    >
      <p style={{ fontSize: 10, color: AURORA.textMuted, fontWeight: 700, margin: '0 0 4px', textTransform: 'uppercase' }}>{label}</p>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <span style={{ fontSize: 22, fontWeight: 700, color: AURORA.text }}>{value}</span>
        <span style={{ fontSize: 9, color: changeColor || AURORA.greenText, fontWeight: 600 }}>{change}</span>
      </div>
    </div>
  );
}

function AuroraTrendSVG({ points }: { points: number[] }) {
  const pathData = points.map((p, i) => {
    const x = (i / (points.length - 1)) * 1000;
    const y = 100 - p;
    return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
  }).join(' ');

  return (
    <svg style={{ width: '100%', height: '100%', overflow: 'visible' }} viewBox="0 0 1000 100" preserveAspectRatio="none">
      <defs>
        <linearGradient id="auroraLineGrad" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0} />
          <stop offset="50%" stopColor="#8b5cf6" stopOpacity={1} />
          <stop offset="100%" stopColor="#34d399" stopOpacity={1} />
        </linearGradient>
      </defs>
      <path
        d={pathData}
        fill="none"
        stroke="url(#auroraLineGrad)"
        strokeWidth="4"
        strokeLinecap="round"
        strokeDasharray="1000"
        strokeDashoffset="1000"
        style={{ animation: 'chartDraw 3s ease-out forwards' }}
      />
      <circle cx="1000" cy={100 - points[points.length - 1]} r="6" fill="#34d399">
        <animate attributeName="r" values="6;10;6" dur="2s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="1;0.4;1" dur="2s" repeatCount="indefinite" />
      </circle>
    </svg>
  );
}

const auroraBtn: React.CSSProperties = {
  background: 'rgba(255,255,255,0.5)',
  border: '1px solid rgba(255,255,255,0.5)',
  borderRadius: 10,
  padding: '5px 14px',
  fontSize: 12,
  fontWeight: 500,
  cursor: 'pointer',
  color: '#64748b',
  backdropFilter: 'blur(4px)',
  transition: 'all 0.2s',
};


// ========================
// SKIN: GENESIS (Deep Space Dark)
// ========================

function SkinGenesis({
  data,
  dashboard,
  lastRefresh,
  onRefresh,
  onBack,
  onClose,
}: {
  data: ExtractedData;
  dashboard: DashboardConfig;
  lastRefresh: string;
  onRefresh: () => void;
  onBack: () => void;
  onClose?: () => void;
}) {
  const [gmvDisplay, setGmvDisplay] = useState(data.gmv);

  useEffect(() => {
    const iv = setInterval(() => {
      setGmvDisplay(prev => prev + Math.floor(Math.random() * 500) + 100);
    }, 3000);
    return () => clearInterval(iv);
  }, []);

  const T = GENESIS;

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999, overflow: 'hidden',
      backgroundColor: T.bg,
      fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      color: T.text,
    }}>
      {/* Background Atmosphere */}
      <div style={{ position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 0 }}>
        {/* Purple glow - top left */}
        <div style={{
          position: 'absolute', top: '-10%', left: '-10%', width: '50%', height: '50%',
          borderRadius: '50%',
          background: 'radial-gradient(circle, #818cf8 0%, #c084fc 100%)',
          filter: 'blur(60px)', opacity: 0.4,
          animation: 'genesisGlow 8s ease infinite',
        }} />
        {/* Teal glow - bottom right */}
        <div style={{
          position: 'absolute', bottom: '-10%', right: '-10%', width: '50%', height: '50%',
          borderRadius: '50%',
          background: 'radial-gradient(circle, #2dd4bf 0%, #818cf8 100%)',
          filter: 'blur(60px)', opacity: 0.4,
          animation: 'genesisGlow 8s ease infinite 4s',
        }} />
      </div>

      {/* Main Layout */}
      <main style={{ height: '100vh', width: '100%', display: 'flex', padding: 20, gap: 20, position: 'relative', zIndex: 1 }}>
        {/* Left Sidebar */}
        <aside style={{
          width: 64,
          background: T.panelBg,
          backdropFilter: T.panelBlur,
          WebkitBackdropFilter: T.panelBlur,
          border: `1px solid ${T.panelBorder}`,
          boxShadow: T.panelShadow,
          borderRadius: 24,
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          padding: '24px 0', gap: 24,
          flexShrink: 0,
        }}>
          {/* Logo blob */}
          <div style={{
            width: 36, height: 36,
            background: 'linear-gradient(135deg, #a5f3fc, #e9d5ff, #fbcfe8)',
            borderRadius: '40% 60% 70% 30% / 40% 50% 60% 50%',
            filter: 'blur(1px)',
            boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
            animation: 'spinSlow 12s linear infinite',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0a0b14" strokeWidth="2">
              <path d="M13 10V3L4 14h7v7l9-11h-7z" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          {/* Nav icons */}
          <nav style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {[
              'M4 4h16v16H4z', // grid
              'M3 3v18h18', // chart
              'M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2', // users
              'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z', // settings
            ].map((d, i) => (
              <button key={i} style={{
                background: 'transparent', border: 'none', cursor: 'pointer', padding: 6,
                color: '#94a3b8', transition: 'color 0.2s',
              }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d={d} strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            ))}
          </nav>
          <div style={{ marginTop: 'auto' }}>
            <button onClick={onBack} style={{
              background: 'rgba(255,255,255,0.1)', border: 'none', borderRadius: 10,
              padding: 8, cursor: 'pointer', color: '#94a3b8', fontSize: 10,
            }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M19 12H5M12 19l-7-7 7-7" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
        </aside>

        {/* Dashboard Body */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 20, overflow: 'hidden' }}>
          {/* Header */}
          <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', paddingBottom: 4 }}>
            <div>
              <h1 style={{ margin: 0, fontSize: 28, fontWeight: 600, letterSpacing: -0.5, fontFamily: "'Inter', sans-serif" }}>
                {dashboard.layout.title || dashboard.name}
              </h1>
              <p style={{ margin: '4px 0 0', color: T.textMuted, fontWeight: 300, fontSize: 13 }}>Real-time ecosystem intelligence</p>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ textAlign: 'right' }}>
                <span style={{ display: 'block', fontSize: 9, textTransform: 'uppercase', letterSpacing: 2, color: T.textMuted }}>Node Status</span>
                <span style={{ color: '#b2f5ea', fontSize: 12, display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'flex-end' }}>
                  <span style={{ position: 'relative', display: 'inline-flex', width: 8, height: 8 }}>
                    <span style={{
                      position: 'absolute', inset: 0, borderRadius: '50%', background: '#2dd4bf',
                      opacity: 0.75, animation: 'pingDot 1s cubic-bezier(0,0,0.2,1) infinite',
                    }} />
                    <span style={{ position: 'relative', width: 8, height: 8, borderRadius: '50%', background: '#14b8a6', display: 'inline-flex' }} />
                  </span>
                  Operational
                </span>
              </div>
              <span style={{ fontSize: 11, color: T.textMuted }}>更新于 {lastRefresh}</span>
              <button onClick={onRefresh} style={genesisBtn}>刷新</button>
              {onClose && <button onClick={onClose} style={genesisBtn}>X</button>}
            </div>
          </header>

          {/* Dashboard Grid: 12-col, 6-row */}
          <div style={{
            flex: 1, display: 'grid',
            gridTemplateColumns: 'repeat(12, 1fr)',
            gridTemplateRows: 'repeat(6, 1fr)',
            gap: 16, overflow: 'hidden',
          }}>
            {/* Live GMV - col 1-4, row 1-2 */}
            <GenesisPanel style={{ gridColumn: '1 / 5', gridRow: '1 / 3', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', position: 'relative', overflow: 'hidden' }}>
              <div style={{ position: 'absolute', top: -40, right: -40, width: 120, height: 120, background: 'rgba(129,140,248,0.2)', borderRadius: '50%', filter: 'blur(40px)' }} />
              <div>
                <h3 style={{ fontSize: 11, fontWeight: 500, color: T.textMuted, textTransform: 'uppercase', letterSpacing: 2, margin: 0 }}>Live GMV</h3>
                <div style={{ marginTop: 12, display: 'flex', alignItems: 'baseline', gap: 8 }}>
                  <span style={{ fontSize: 40, fontWeight: 600, color: '#fff', fontFamily: "'Inter', sans-serif" }}>
                    ${gmvDisplay.toLocaleString('en-US')}
                  </span>
                  <span style={{ color: '#b2f5ea', fontSize: 12, fontWeight: 500 }}>+12.4%</span>
                </div>
              </div>
              <div style={{ height: 48, width: '100%', opacity: 0.6 }}>
                <GenesisSparkline points={data.trendPoints} />
              </div>
            </GenesisPanel>

            {/* Market Vitality - col 5-8, row 1-4 */}
            <GenesisPanel style={{
              gridColumn: '5 / 9', gridRow: '1 / 5',
              borderRadius: 40, display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center', position: 'relative',
            }}>
              {/* Background organic blob */}
              <div style={{
                position: 'absolute', inset: 0, opacity: 0.15,
                background: 'linear-gradient(135deg, #a5f3fc, #e9d5ff, #fbcfe8)',
                filter: 'blur(100px)', borderRadius: '50%',
              }} />
              <div style={{ textAlign: 'center', marginBottom: 24, zIndex: 1 }}>
                <span style={{ fontSize: 10, fontWeight: 500, textTransform: 'uppercase', letterSpacing: 3, color: T.textMuted }}>Market Vitality</span>
              </div>

              {/* Organic blob sphere */}
              <div style={{ position: 'relative', width: 200, height: 200, zIndex: 1, animation: 'float 6s ease-in-out infinite', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <div style={{
                  position: 'absolute', inset: 0,
                  background: 'linear-gradient(135deg, rgba(165,243,252,0.4), rgba(192,132,252,0.4))',
                  borderRadius: '50%', filter: 'blur(20px)',
                  animation: 'pulseSlow 4s ease infinite',
                }} />
                <div style={{
                  width: 150, height: 150,
                  background: 'linear-gradient(135deg, #a5f3fc, #e9d5ff, #fbcfe8)',
                  borderRadius: '40% 60% 70% 30% / 40% 50% 60% 50%',
                  boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
                  animation: 'spinSlow 12s linear infinite',
                  opacity: 0.8,
                  border: '1px solid rgba(255,255,255,0.3)',
                  filter: 'blur(2px)',
                }} />
                {/* Light spot */}
                <div style={{
                  position: 'absolute', width: 40, height: 40,
                  background: 'rgba(255,255,255,0.2)', borderRadius: '50%',
                  filter: 'blur(10px)', top: '25%', left: '25%',
                }} />
                {/* Center text */}
                <div style={{ position: 'absolute', textAlign: 'center' }}>
                  <span style={{ fontSize: 48, fontWeight: 300, fontFamily: "'Inter', sans-serif", color: '#fff' }}>98</span>
                  <span style={{ display: 'block', fontSize: 10, fontWeight: 500, color: '#e9d5ff', letterSpacing: 1 }}>OPTIMAL</span>
                </div>
              </div>

              <div style={{ marginTop: 24, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, width: '60%', zIndex: 1 }}>
                <div style={{ textAlign: 'center' }}>
                  <span style={{ display: 'block', color: T.textMuted, fontSize: 10 }}>Liquidity</span>
                  <span style={{ fontSize: 18, fontWeight: 300 }}>8.4M</span>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <span style={{ display: 'block', color: T.textMuted, fontSize: 10 }}>Velocity</span>
                  <span style={{ fontSize: 18, fontWeight: 300 }}>1.2x</span>
                </div>
              </div>
            </GenesisPanel>

            {/* Conversion Funnel - col 9-12, row 1-3 */}
            <GenesisPanel style={{ gridColumn: '9 / 13', gridRow: '1 / 4', display: 'flex', flexDirection: 'column' }}>
              <h3 style={{ fontSize: 11, fontWeight: 500, color: T.textMuted, textTransform: 'uppercase', letterSpacing: 2, margin: '0 0 16px' }}>Experience Funnel</h3>
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
                {data.funnelSteps.map((step, i) => {
                  const widths = ['100%', '85%', '60%', '40%'];
                  const bgColors = ['rgba(255,255,255,0.05)', 'rgba(45,212,191,0.2)', 'rgba(129,140,248,0.2)', 'rgba(255,255,255,0.1)'];
                  const borderColors = ['rgba(255,255,255,0.1)', 'rgba(45,212,191,0.3)', 'rgba(129,140,248,0.3)', 'rgba(255,255,255,0.2)'];
                  return (
                    <div key={i} style={{
                      width: widths[i] || '40%',
                      margin: '0 auto',
                      height: 40,
                      background: bgColors[i],
                      border: `1px solid ${borderColors[i]}`,
                      borderRadius: 14,
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '0 14px', fontSize: 12,
                    }}>
                      <span style={{ color: '#e2e8f0' }}>{step.name}</span>
                      <span style={{ fontFamily: 'monospace', fontSize: 12 }}>{step.percent}%</span>
                    </div>
                  );
                })}
              </div>
            </GenesisPanel>

            {/* Channel Performance - col 1-4, row 3-4 */}
            <GenesisPanel style={{ gridColumn: '1 / 5', gridRow: '3 / 5' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <h3 style={{ fontSize: 11, fontWeight: 500, color: T.textMuted, textTransform: 'uppercase', letterSpacing: 2, margin: 0 }}>Top Channels</h3>
                <span style={{ fontSize: 9, color: T.textMuted }}>Live View</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {data.channels.slice(0, 2).map((ch, i) => {
                  const colors = ['rgba(236,72,153,0.6)', 'rgba(45,212,191,0.6)'];
                  const bgColors = ['rgba(236,72,153,0.2)', 'rgba(45,212,191,0.2)'];
                  const textColors = ['#f9a8d4', '#99f6e4'];
                  const labels = ['SS', 'SR'];
                  return (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div style={{
                        width: 28, height: 28, borderRadius: 8,
                        background: bgColors[i], display: 'flex', alignItems: 'center', justifyContent: 'center',
                        color: textColors[i], fontSize: 9, fontWeight: 600,
                      }}>{labels[i]}</div>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                          <span>{ch.name}</span>
                          <span>{ch.percent}%</span>
                        </div>
                        <div style={{ height: 3, width: '100%', background: 'rgba(255,255,255,0.05)', borderRadius: 999, overflow: 'hidden' }}>
                          <div style={{ height: '100%', width: `${ch.percent}%`, background: colors[i], borderRadius: 999 }} />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </GenesisPanel>

            {/* Live Transactions - col 9-12, row 4-6 */}
            <GenesisPanel style={{ gridColumn: '9 / 13', gridRow: '4 / 7', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              <h3 style={{ fontSize: 11, fontWeight: 500, color: T.textMuted, textTransform: 'uppercase', letterSpacing: 2, margin: '0 0 12px' }}>Live Transactions</h3>
              <div style={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }}>
                {MOCK_ORDERS.map((tx, i) => {
                  const gradients = [
                    'linear-gradient(135deg, #8b5cf6, #6366f1)',
                    'linear-gradient(135deg, #06b6d4, #14b8a6)',
                    'linear-gradient(135deg, #ec4899, #f43f5e)',
                    'linear-gradient(135deg, #8b5cf6, #6366f1)',
                  ];
                  return (
                    <div key={tx.id} style={{
                      padding: 10, background: 'rgba(255,255,255,0.05)', borderRadius: 14,
                      border: '1px solid rgba(255,255,255,0.05)',
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      transition: 'background 0.2s',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div style={{
                          width: 28, height: 28, borderRadius: '50%',
                          background: gradients[i % gradients.length],
                          opacity: 0.6,
                        }} />
                        <div>
                          <span style={{ fontSize: 11, fontWeight: 500, display: 'block' }}>Order #{tx.id}</span>
                          <span style={{ fontSize: 9, color: T.textMuted, textTransform: 'uppercase' }}>{tx.time}</span>
                        </div>
                      </div>
                      <span style={{ fontSize: 13, fontFamily: 'monospace', color: '#b2f5ea' }}>${tx.price.toFixed(2)}</span>
                    </div>
                  );
                })}
              </div>
            </GenesisPanel>

            {/* Customer Sentiment - col 1-4, row 5-6 */}
            <GenesisPanel style={{ gridColumn: '1 / 5', gridRow: '5 / 7', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <h3 style={{ fontSize: 11, fontWeight: 500, color: T.textMuted, textTransform: 'uppercase', letterSpacing: 2, margin: 0 }}>Customer Sentiment</h3>
                <span style={{ fontSize: 20, fontWeight: 300 }}>Positive (94%)</span>
                <div style={{ display: 'flex', gap: 3, marginTop: 4 }}>
                  {[1,2,3,4].map(i => (
                    <div key={i} style={{ width: 6, height: 6, borderRadius: '50%', background: '#2dd4bf' }} />
                  ))}
                  <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'rgba(255,255,255,0.2)' }} />
                </div>
              </div>
              <div style={{
                width: 72, height: 72,
                border: '2px dashed rgba(255,255,255,0.1)',
                borderRadius: '50%',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                position: 'relative',
              }}>
                {/* Heart icon SVG */}
                <svg width="32" height="32" viewBox="0 0 24 24" fill="rgba(129,140,248,0.5)" stroke="rgba(129,140,248,0.5)" strokeWidth="1">
                  <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
                </svg>
                {/* Rotating dot */}
                <div style={{ position: 'absolute', inset: 0, animation: 'spinSlow 12s linear infinite' }}>
                  <div style={{ width: 6, height: 6, background: '#fff', borderRadius: '50%', position: 'absolute', top: -3, left: '50%', marginLeft: -3 }} />
                </div>
              </div>
            </GenesisPanel>

            {/* KPI row - col 5-8, row 5-6 */}
            <GenesisPanel style={{ gridColumn: '5 / 9', gridRow: '5 / 7', display: 'flex', alignItems: 'center', justifyContent: 'space-around' }}>
              {[
                { label: '订单总数', value: data.orders.toLocaleString(), change: '+5.2%' },
                { label: '平均客单价', value: `$${data.avgOrderValue.toFixed(0)}`, change: '稳定' },
                { label: '转化率', value: `${data.conversionRate}%`, change: '+0.8%' },
              ].map((kpi, i) => (
                <div key={i} style={{ textAlign: 'center' }}>
                  <span style={{ display: 'block', fontSize: 10, color: T.textMuted, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>{kpi.label}</span>
                  <span style={{ fontSize: 24, fontWeight: 600 }}>{kpi.value}</span>
                  <span style={{ display: 'block', fontSize: 10, color: '#b2f5ea', marginTop: 2 }}>{kpi.change}</span>
                </div>
              ))}
            </GenesisPanel>
          </div>
        </div>
      </main>
    </div>
  );
}

function GenesisPanel({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{
      background: GENESIS.panelBg,
      backdropFilter: GENESIS.panelBlur,
      WebkitBackdropFilter: GENESIS.panelBlur,
      border: `1px solid ${GENESIS.panelBorder}`,
      boxShadow: GENESIS.panelShadow,
      borderRadius: 24,
      padding: 20,
      ...style,
    }}>
      {children}
    </div>
  );
}

function GenesisSparkline({ points }: { points: number[] }) {
  const pathData = points.map((p, i) => {
    const x = (i / (points.length - 1)) * 100;
    const y = 100 - p;
    return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
  }).join(' ');
  const fillPath = `${pathData} L 100 100 L 0 100 Z`;

  return (
    <svg viewBox="0 0 100 100" style={{ width: '100%', height: '100%' }} preserveAspectRatio="none">
      <defs>
        <linearGradient id="genesis-spark-fill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="rgba(45,212,191,0.2)" />
          <stop offset="100%" stopColor="rgba(45,212,191,0)" />
        </linearGradient>
      </defs>
      <path d={fillPath} fill="url(#genesis-spark-fill)" />
      <path d={pathData} fill="none" stroke="#2dd4bf" strokeWidth="2" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

const genesisBtn: React.CSSProperties = {
  background: 'rgba(255,255,255,0.08)',
  border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: 10,
  padding: '5px 14px',
  fontSize: 12,
  fontWeight: 500,
  cursor: 'pointer',
  color: '#94a3b8',
  backdropFilter: 'blur(4px)',
  transition: 'all 0.2s',
};


// ========================
// LIST VIEW (adapted to skin background)
// ========================

function DashboardListView({
  skin,
  dashboardList,
  onSelect,
  onDelete,
  onClose,
  onSkinChange,
}: {
  skin: SkinType;
  dashboardList: DashboardConfig[];
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onClose?: () => void;
  onSkinChange: (s: SkinType) => void;
}) {
  const T = skin === 'aurora' ? AURORA : GENESIS;
  const isAurora = skin === 'aurora';

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999, overflow: 'auto',
      background: isAurora ? T.bg : T.bg as string,
      backgroundSize: isAurora ? '400% 400%' : undefined,
      backgroundColor: isAurora ? undefined : T.bg as string,
      animation: isAurora ? 'aurora 15s ease infinite' : undefined,
      fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      color: T.text,
      padding: 24,
      display: 'flex', flexDirection: 'column',
    }}>
      {/* Background glows for Genesis */}
      {!isAurora && (
        <div style={{ position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 0 }}>
          <div style={{
            position: 'absolute', top: '-10%', left: '-10%', width: '50%', height: '50%', borderRadius: '50%',
            background: 'radial-gradient(circle, #818cf8 0%, #c084fc 100%)', filter: 'blur(60px)', opacity: 0.4,
          }} />
          <div style={{
            position: 'absolute', bottom: '-10%', right: '-10%', width: '50%', height: '50%', borderRadius: '50%',
            background: 'radial-gradient(circle, #2dd4bf 0%, #818cf8 100%)', filter: 'blur(60px)', opacity: 0.4,
          }} />
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', position: 'relative', zIndex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: isAurora ? '#8b5cf6' : '#2dd4bf',
            animation: 'pulseSlow 2s ease infinite',
          }} />
          <h2 style={{
            margin: 0, fontSize: 22, fontWeight: 700, letterSpacing: 2,
            background: isAurora ? 'linear-gradient(90deg, #8b5cf6, #6366f1)' : 'linear-gradient(90deg, #2dd4bf, #818cf8)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          } as React.CSSProperties}>
            数据大屏中心
          </h2>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <SkinSwitcher skin={skin} onChange={onSkinChange} theme={T} />
          {onClose && (
            <button onClick={onClose} style={isAurora ? auroraBtn : genesisBtn}>X</button>
          )}
        </div>
      </div>

      {dashboardList.length === 0 ? (
        <div style={{
          flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          paddingTop: 80, position: 'relative', zIndex: 1,
        }}>
          <svg width="64" height="64" viewBox="0 0 64 64" fill="none" style={{ marginBottom: 24, opacity: 0.6 }}>
            <rect x="4" y="12" width="56" height="40" rx="4" stroke={isAurora ? '#8b5cf6' : '#2dd4bf'} strokeWidth="2" opacity="0.4" />
            <rect x="10" y="20" width="18" height="12" rx="2" stroke={isAurora ? '#6366f1' : '#818cf8'} strokeWidth="1.5" opacity="0.6" />
            <rect x="36" y="20" width="18" height="24" rx="2" stroke={isAurora ? '#8b5cf6' : '#2dd4bf'} strokeWidth="1.5" opacity="0.6" />
          </svg>
          <p style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>尚无数据大屏</p>
          <p style={{ fontSize: 14, color: T.textSecondary, marginTop: 0 }}>通过对话让数据产品经理帮你创建，试试说：</p>
          <div style={{
            marginTop: 16, padding: '10px 24px',
            background: isAurora ? 'rgba(255,255,255,0.5)' : 'rgba(255,255,255,0.06)',
            backdropFilter: 'blur(12px)',
            border: `1px solid ${isAurora ? 'rgba(139,92,246,0.2)' : 'rgba(45,212,191,0.2)'}`,
            borderRadius: 12,
            color: isAurora ? T.accent : '#b2f5ea',
            fontSize: 15, fontWeight: 500, letterSpacing: 1,
          }}>
            「帮我做一个 618 作战大屏」
          </div>
        </div>
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
          gap: 20, marginTop: 20,
          position: 'relative', zIndex: 1,
        }}>
          {dashboardList.map((d, i) => (
            <ListCardSkinned key={d.dashboard_id} config={d} index={i} onSelect={onSelect} onDelete={onDelete} skin={skin} />
          ))}
        </div>
      )}
    </div>
  );
}

function ListCardSkinned({ config, index, onSelect, onDelete, skin }: {
  config: DashboardConfig; index: number; onSelect: (id: string) => void; onDelete: (id: string) => void; skin: SkinType;
}) {
  const [hovered, setHovered] = useState(false);
  const isAurora = skin === 'aurora';
  const T = isAurora ? AURORA : GENESIS;

  return (
    <div
      onClick={() => onSelect(config.dashboard_id)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        animation: `fadeInUp 0.4s ease ${index * 0.06}s both`,
        background: hovered
          ? (isAurora ? 'rgba(255,255,255,0.7)' : 'rgba(255,255,255,0.08)')
          : (isAurora ? T.panelBg : T.panelBg),
        backdropFilter: isAurora ? T.panelBlur : T.panelBlur,
        WebkitBackdropFilter: isAurora ? T.panelBlur : T.panelBlur,
        border: `1px solid ${hovered ? (isAurora ? 'rgba(139,92,246,0.4)' : 'rgba(45,212,191,0.4)') : T.panelBorder}`,
        boxShadow: hovered
          ? (isAurora ? '0 8px 32px rgba(139,92,246,0.15)' : '0 8px 32px rgba(45,212,191,0.15)')
          : T.panelShadow,
        borderRadius: 16,
        padding: 20,
        cursor: 'pointer',
        transform: hovered ? 'scale(1.02) translateY(-2px)' : 'scale(1)',
        transition: 'all 0.3s cubic-bezier(0.4,0,0.2,1)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <h3 style={{ color: T.text, margin: '0 0 8px', fontSize: 16, fontWeight: 600 }}>{config.name}</h3>
        <button
          onClick={(e) => {
            e.stopPropagation();
            if (window.confirm(`确定删除「${config.name}」？此操作不可撤销。`)) {
              onDelete(config.dashboard_id);
            }
          }}
          style={{
            background: 'transparent', border: 'none', cursor: 'pointer',
            color: T.textMuted, fontSize: 14, padding: '2px 6px', borderRadius: 6,
            opacity: hovered ? 1 : 0, transition: 'opacity 0.2s',
          }}
          title="删除此大屏"
        >🗑</button>
      </div>
      <p style={{ color: T.textSecondary, fontSize: 13, margin: 0, lineHeight: 1.5 }}>
        {config.description || '自定义大屏'}
      </p>
      <div style={{ marginTop: 14, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <span style={{
          display: 'inline-block',
          background: config.status === 'active'
            ? (isAurora ? 'rgba(52,211,153,0.15)' : 'rgba(52,211,153,0.15)')
            : (isAurora ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.06)'),
          color: config.status === 'active' ? T.green : T.textSecondary,
          fontSize: 11, padding: '3px 10px', borderRadius: 4,
          border: `1px solid ${config.status === 'active' ? 'rgba(52,211,153,0.3)' : T.panelBorder}`,
        }}>
          {config.status === 'active' ? '● 运行中' : '○ 草稿'}
        </span>
        <span style={{
          display: 'inline-block',
          background: isAurora ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.06)',
          color: T.textSecondary, fontSize: 11, padding: '3px 10px', borderRadius: 4,
          border: `1px solid ${T.panelBorder}`,
        }}>
          {config.charts?.length || 0} 个图表
        </span>
      </div>
    </div>
  );
}

// ========================
// MAIN COMPONENT
// ========================

export default function DashboardView({ dashboardId, onClose }: DashboardViewProps) {
  const [selectedId, setSelectedId] = useState<string | undefined>(dashboardId);
  const [skin, setSkin] = useState<SkinType>(() => {
    try {
      const saved = localStorage.getItem('dashboard-skin');
      if (saved === 'aurora' || saved === 'genesis') return saved;
    } catch { /* silent */ }
    return 'aurora';
  });

  const {
    dashboard, dashboardList, loading, error, lastRefresh, liveData, handleRefresh,
  } = useDashboardData(selectedId);

  const handleSkinChange = useCallback((s: SkinType) => {
    setSkin(s);
    try { localStorage.setItem('dashboard-skin', s); } catch { /* silent */ }
  }, []);

  const handleDeleteDashboard = useCallback(async (id: string) => {
    try {
      await fetch(`/api/v1/office/dashboards/${id}`, { method: 'DELETE' });
      // 触发列表刷新（useDashboardData 内部会重新 fetch）
      window.location.reload();
    } catch (err) {
      console.error('删除大屏失败:', err);
    }
  }, []);

  const extractedData = useMemo(
    () => extractDashboardData(dashboard, liveData),
    [dashboard, liveData],
  );

  const T = skin === 'aurora' ? AURORA : GENESIS;
  const isAurora = skin === 'aurora';

  // ---- List view ----
  if (!selectedId) {
    return (
      <>
        <style>{KEYFRAMES}</style>
        <DashboardListView
          skin={skin}
          dashboardList={dashboardList}
          onSelect={setSelectedId}
          onDelete={handleDeleteDashboard}
          onClose={onClose}
          onSkinChange={handleSkinChange}
        />
      </>
    );
  }

  // ---- Loading ----
  if (loading) {
    return (
      <div style={{
        position: 'fixed', inset: 0, zIndex: 9999,
        background: isAurora ? T.bg : T.bg as string,
        backgroundSize: isAurora ? '400% 400%' : undefined,
        backgroundColor: isAurora ? undefined : T.bg as string,
        animation: isAurora ? 'aurora 15s ease infinite' : undefined,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: "'Inter', sans-serif", color: T.text,
      }}>
        <style>{KEYFRAMES}</style>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 16 }}>
          <div style={{
            width: 20, height: 20, borderRadius: '50%',
            border: `2px solid ${T.panelBorder}`,
            borderTopColor: isAurora ? T.accent : '#2dd4bf',
            animation: 'spinSlow 1s linear infinite',
          }} />
          加载大屏配置中...
        </div>
      </div>
    );
  }

  // ---- Error ----
  if (error || !dashboard) {
    return (
      <div style={{
        position: 'fixed', inset: 0, zIndex: 9999,
        background: isAurora ? T.bg : T.bg as string,
        backgroundSize: isAurora ? '400% 400%' : undefined,
        backgroundColor: isAurora ? undefined : T.bg as string,
        animation: isAurora ? 'aurora 15s ease infinite' : undefined,
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        fontFamily: "'Inter', sans-serif", color: T.text,
      }}>
        <style>{KEYFRAMES}</style>
        <div style={{ color: '#f87171', fontSize: 16, marginBottom: 16 }}>{error || '大屏不存在'}</div>
        <button onClick={() => setSelectedId(undefined)} style={isAurora ? auroraBtn : genesisBtn}>
          {'<-'} 返回列表
        </button>
      </div>
    );
  }

  // ---- Detail view with skin ----
  return (
    <>
      <style>{KEYFRAMES}</style>
      {/* Skin switcher floating overlay */}
      <div style={{
        position: 'fixed', top: 16, right: 24, zIndex: 10001,
      }}>
        <SkinSwitcher skin={skin} onChange={handleSkinChange} theme={T} />
      </div>
      {skin === 'aurora' ? (
        <SkinAurora
          data={extractedData}
          dashboard={dashboard}
          lastRefresh={lastRefresh}
          onRefresh={handleRefresh}
          onBack={() => setSelectedId(undefined)}
          onClose={onClose}
        />
      ) : (
        <SkinGenesis
          data={extractedData}
          dashboard={dashboard}
          lastRefresh={lastRefresh}
          onRefresh={handleRefresh}
          onBack={() => setSelectedId(undefined)}
          onClose={onClose}
        />
      )}
      {/* 反馈对话框 */}
      {dashboard && <FeedbackChat dashboard={dashboard} skin={skin} />}
    </>
  );
}

// ========================
// FEEDBACK CHAT
// ========================

function FeedbackChat({ dashboard, skin }: { dashboard: DashboardConfig; skin: SkinType }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<{ role: 'user' | 'agent'; text: string }[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const isAurora = skin === 'aurora';
  const T = isAurora ? AURORA : GENESIS;

  const sendMessage = async () => {
    if (!input.trim() || sending) return;
    const userMsg = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', text: userMsg }]);
    setSending(true);

    try {
      // 携带大屏上下文发给数据产品经理
      const context = `[大屏反馈] 大屏名称: ${dashboard.name}, ID: ${dashboard.dashboard_id}, ` +
        `图表: ${dashboard.charts?.map(c => c.title).join('、') || '无'}\n\n用户反馈: ${userMsg}`;

      const res = await fetch('/api/v1/office/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: context,
          agent_slug: 'data_pm',
        }),
      });
      const json = await res.json();
      const reply = json.data?.reply || json.data?.response || json.error || '收到反馈，稍后处理。';
      setMessages(prev => [...prev, { role: 'agent', text: reply }]);
    } catch {
      setMessages(prev => [...prev, { role: 'agent', text: '发送失败，请稍后重试。' }]);
    } finally {
      setSending(false);
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        style={{
          position: 'fixed', bottom: 24, right: 24, zIndex: 10002,
          width: 56, height: 56, borderRadius: '50%',
          background: isAurora ? 'linear-gradient(135deg, #8b5cf6, #6366f1)' : 'linear-gradient(135deg, #2dd4bf, #818cf8)',
          border: 'none', cursor: 'pointer',
          boxShadow: isAurora ? '0 4px 20px rgba(139,92,246,0.4)' : '0 4px 20px rgba(45,212,191,0.4)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 24, color: '#fff',
          transition: 'transform 0.2s',
        }}
        onMouseEnter={e => (e.currentTarget.style.transform = 'scale(1.1)')}
        onMouseLeave={e => (e.currentTarget.style.transform = 'scale(1)')}
        title="对此大屏提反馈"
      >💬</button>
    );
  }

  return (
    <div style={{
      position: 'fixed', bottom: 24, right: 24, zIndex: 10002,
      width: 380, height: 480,
      background: isAurora ? 'rgba(255,255,255,0.85)' : 'rgba(15,15,30,0.95)',
      backdropFilter: 'blur(20px)',
      border: `1px solid ${isAurora ? 'rgba(139,92,246,0.2)' : 'rgba(45,212,191,0.2)'}`,
      borderRadius: 16,
      boxShadow: isAurora ? '0 8px 40px rgba(139,92,246,0.2)' : '0 8px 40px rgba(0,0,0,0.5)',
      display: 'flex', flexDirection: 'column',
      fontFamily: "'Inter', sans-serif",
    }}>
      {/* Header */}
      <div style={{
        padding: '14px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        borderBottom: `1px solid ${isAurora ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.08)'}`,
      }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: T.text }}>💬 大屏反馈</div>
          <div style={{ fontSize: 11, color: T.textMuted, marginTop: 2 }}>
            对「{dashboard.name}」提需求
          </div>
        </div>
        <button onClick={() => setOpen(false)} style={{
          background: 'transparent', border: 'none', cursor: 'pointer',
          color: T.textMuted, fontSize: 18, padding: '2px 6px',
        }}>✕</button>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflow: 'auto', padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {messages.length === 0 && (
          <div style={{ color: T.textMuted, fontSize: 13, textAlign: 'center', marginTop: 40 }}>
            试试说：「把转化漏斗改成柱状图」或「加一个退货率趋势」
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} style={{
            alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
            maxWidth: '80%',
            background: m.role === 'user'
              ? (isAurora ? 'linear-gradient(135deg, #8b5cf6, #6366f1)' : 'linear-gradient(135deg, #2dd4bf, #818cf8)')
              : (isAurora ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.08)'),
            color: m.role === 'user' ? '#fff' : T.text,
            padding: '8px 14px', borderRadius: 12, fontSize: 13, lineHeight: 1.5,
          }}>
            {m.text}
          </div>
        ))}
        {sending && (
          <div style={{ color: T.textMuted, fontSize: 12, padding: 4 }}>数据产品经理思考中...</div>
        )}
      </div>

      {/* Input */}
      <div style={{
        padding: '10px 12px', display: 'flex', gap: 8,
        borderTop: `1px solid ${isAurora ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.08)'}`,
      }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && sendMessage()}
          placeholder="输入反馈或需求..."
          style={{
            flex: 1, padding: '8px 12px', borderRadius: 10, fontSize: 13,
            background: isAurora ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.06)',
            border: `1px solid ${isAurora ? 'rgba(0,0,0,0.1)' : 'rgba(255,255,255,0.1)'}`,
            color: T.text, outline: 'none',
          }}
        />
        <button
          onClick={sendMessage}
          disabled={sending || !input.trim()}
          style={{
            padding: '8px 16px', borderRadius: 10, border: 'none', cursor: 'pointer',
            background: isAurora ? 'linear-gradient(135deg, #8b5cf6, #6366f1)' : 'linear-gradient(135deg, #2dd4bf, #818cf8)',
            color: '#fff', fontSize: 13, fontWeight: 600,
            opacity: sending || !input.trim() ? 0.5 : 1,
          }}
        >发送</button>
      </div>
    </div>
  );
}
