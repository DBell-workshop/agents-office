"""浮窗控制层 JS — 注入到电商页面中的采集控制 UI。

通过 Playwright page.add_init_script() 注入，每次导航自动重载。
通过 page.expose_function() 注册的回调与 Python 端通信。
"""
from __future__ import annotations

OVERLAY_JS = r"""
(function() {
  // 防止重复注入
  if (window.__collectorOverlayInit) return;
  window.__collectorOverlayInit = true;

  // ============================================================
  // 创建浮窗 DOM
  // ============================================================
  function createOverlay() {
    const overlay = document.createElement('div');
    overlay.id = '__collector_overlay';
    overlay.innerHTML = `
      <div id="__co_header" style="
        display:flex; align-items:center; justify-content:space-between;
        cursor:move; padding:6px 10px; background:#1a1a2e;
        border-bottom:1px solid #4ade80; user-select:none;
      ">
        <span style="color:#4ade80; font-weight:bold; font-size:13px;">采集控制台</span>
        <span id="__co_minimize" style="color:#999; cursor:pointer; font-size:16px; line-height:1;">−</span>
      </div>
      <div id="__co_body" style="padding:10px;">
        <div style="margin-bottom:8px;">
          <label style="color:#aaa; font-size:11px; display:block; margin-bottom:3px;">搜索关键词</label>
          <input id="__co_query" type="text" placeholder="输入商品关键词…"
            style="width:100%; box-sizing:border-box; padding:6px 8px; border:1px solid #555;
            border-radius:4px; background:#2a2a3e; color:#eee; font-size:13px; outline:none;"
          />
        </div>
        <div style="margin-bottom:8px;">
          <label style="color:#aaa; font-size:11px; display:block; margin-bottom:3px;">平台</label>
          <select id="__co_platform" style="
            width:100%; box-sizing:border-box; padding:6px 8px; border:1px solid #555;
            border-radius:4px; background:#2a2a3e; color:#eee; font-size:13px; outline:none;
          ">
            <option value="auto">自动识别</option>
            <option value="京东">京东</option>
            <option value="淘宝">淘宝</option>
            <option value="拼多多">拼多多</option>
            <option value="其他">其他</option>
          </select>
        </div>
        <div id="__co_status" style="
          color:#999; font-size:11px; margin-bottom:8px; min-height:16px;
        ">就绪 — 请登录后点击开始采集</div>
        <div id="__co_count" style="
          color:#ccaa66; font-size:12px; margin-bottom:8px; display:none;
        ">已采集: <span id="__co_count_num">0</span> 个商品</div>
        <div style="display:flex; gap:6px;">
          <button id="__co_start" style="
            flex:1; padding:7px 0; border:none; border-radius:4px;
            background:#4ade80; color:#000; font-weight:bold; font-size:13px;
            cursor:pointer;
          ">开始采集</button>
          <button id="__co_pause" style="
            flex:1; padding:7px 0; border:none; border-radius:4px;
            background:#f59e0b; color:#000; font-weight:bold; font-size:13px;
            cursor:pointer; display:none;
          ">暂停</button>
          <button id="__co_stop" style="
            padding:7px 12px; border:1px solid #ef4444; border-radius:4px;
            background:transparent; color:#ef4444; font-size:13px;
            cursor:pointer;
          ">结束</button>
        </div>
      </div>
    `;

    Object.assign(overlay.style, {
      position: 'fixed',
      top: '20px',
      right: '20px',
      width: '280px',
      background: 'rgba(20, 20, 40, 0.95)',
      border: '2px solid #4ade80',
      borderRadius: '8px',
      fontFamily: '-apple-system, "Segoe UI", Roboto, monospace',
      zIndex: '2147483647',
      boxShadow: '0 4px 24px rgba(0,0,0,0.5)',
      overflow: 'hidden',
    });

    document.body.appendChild(overlay);
    return overlay;
  }

  // ============================================================
  // 拖动逻辑
  // ============================================================
  function enableDrag(overlay) {
    const header = overlay.querySelector('#__co_header');
    let isDragging = false, startX, startY, startLeft, startTop;

    header.addEventListener('mousedown', (e) => {
      if (e.target.id === '__co_minimize') return;
      isDragging = true;
      const rect = overlay.getBoundingClientRect();
      startX = e.clientX; startY = e.clientY;
      startLeft = rect.left; startTop = rect.top;
      e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
      if (!isDragging) return;
      overlay.style.left = (startLeft + e.clientX - startX) + 'px';
      overlay.style.top = (startTop + e.clientY - startY) + 'px';
      overlay.style.right = 'auto';
    });

    document.addEventListener('mouseup', () => { isDragging = false; });
  }

  // ============================================================
  // 最小化/展开
  // ============================================================
  function enableMinimize(overlay) {
    const btn = overlay.querySelector('#__co_minimize');
    const body = overlay.querySelector('#__co_body');
    let minimized = false;

    btn.addEventListener('click', () => {
      minimized = !minimized;
      body.style.display = minimized ? 'none' : 'block';
      btn.textContent = minimized ? '+' : '−';
      overlay.style.width = minimized ? '140px' : '280px';
    });
  }

  // ============================================================
  // 按钮事件 — 通过 expose_function 回调到 Python
  // ============================================================
  function bindEvents(overlay) {
    const queryInput = overlay.querySelector('#__co_query');
    const platformSelect = overlay.querySelector('#__co_platform');
    const statusEl = overlay.querySelector('#__co_status');
    const countEl = overlay.querySelector('#__co_count');
    const countNum = overlay.querySelector('#__co_count_num');
    const startBtn = overlay.querySelector('#__co_start');
    const pauseBtn = overlay.querySelector('#__co_pause');
    const stopBtn = overlay.querySelector('#__co_stop');

    let collecting = false;

    startBtn.addEventListener('click', async () => {
      const query = queryInput.value.trim();
      if (!query) {
        statusEl.textContent = '⚠️ 请输入搜索关键词';
        statusEl.style.color = '#f59e0b';
        return;
      }
      const platform = platformSelect.value;
      statusEl.textContent = '🔄 采集中…';
      statusEl.style.color = '#4ade80';
      startBtn.textContent = '采集中';
      startBtn.style.background = '#888';
      startBtn.style.cursor = 'not-allowed';
      startBtn.disabled = true;
      pauseBtn.style.display = 'block';
      countEl.style.display = 'block';
      collecting = true;

      try {
        await window.__collector_start(query, platform);
      } catch (e) {
        statusEl.textContent = '❌ 启动失败: ' + e.message;
        statusEl.style.color = '#ef4444';
        startBtn.textContent = '开始采集';
        startBtn.style.background = '#4ade80';
        startBtn.style.cursor = 'pointer';
        startBtn.disabled = false;
        pauseBtn.style.display = 'none';
      }
    });

    pauseBtn.addEventListener('click', async () => {
      if (collecting) {
        collecting = false;
        pauseBtn.textContent = '继续';
        pauseBtn.style.background = '#4ade80';
        statusEl.textContent = '⏸ 已暂停';
        statusEl.style.color = '#f59e0b';
        await window.__collector_pause();
      } else {
        collecting = true;
        pauseBtn.textContent = '暂停';
        pauseBtn.style.background = '#f59e0b';
        statusEl.textContent = '🔄 采集中…';
        statusEl.style.color = '#4ade80';
        await window.__collector_resume();
      }
    });

    stopBtn.addEventListener('click', async () => {
      collecting = false;
      statusEl.textContent = '⏹ 已结束';
      statusEl.style.color = '#999';
      startBtn.textContent = '开始采集';
      startBtn.style.background = '#4ade80';
      startBtn.style.cursor = 'pointer';
      startBtn.disabled = false;
      pauseBtn.style.display = 'none';
      pauseBtn.textContent = '暂停';
      pauseBtn.style.background = '#f59e0b';
      await window.__collector_stop();
    });

    // Python 端可调用此函数更新状态
    window.__collector_update_ui = function(data) {
      if (data.status) {
        statusEl.textContent = data.status;
        statusEl.style.color = data.statusColor || '#999';
      }
      if (data.count !== undefined) {
        countNum.textContent = data.count;
        countEl.style.display = 'block';
      }
    };
  }

  // ============================================================
  // 初始化
  // ============================================================
  function init() {
    // 等待 body 存在
    if (!document.body) {
      document.addEventListener('DOMContentLoaded', init);
      return;
    }
    const overlay = createOverlay();
    enableDrag(overlay);
    enableMinimize(overlay);
    bindEvents(overlay);
  }

  init();
})();
"""
