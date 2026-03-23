import React from 'react';
import { createRoot } from 'react-dom/client';
import DashboardView from './react/DashboardView';

// 从 URL 参数读取 dashboardId（可选）
const params = new URLSearchParams(window.location.search);
const dashboardId = params.get('id') || undefined;

const root = createRoot(document.getElementById('dashboard-root')!);
root.render(
  <React.StrictMode>
    <DashboardView dashboardId={dashboardId} />
  </React.StrictMode>
);
