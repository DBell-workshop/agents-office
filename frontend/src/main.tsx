import React from 'react';
import ReactDOM from 'react-dom/client';
import Phaser from 'phaser';
import { gameConfig } from './phaser/config';
import { ReactOverlay } from './react/ReactOverlay';
import { EventBus } from './shared/events/EventBus';

// 1. 启动 Phaser Game
const game = new Phaser.Game(gameConfig);

// 2. 注入 game 实例到 EventBus
EventBus.setGameInstance(game);

// 3. 挂载 React Overlay
const uiRoot = document.getElementById('ui-overlay');
if (uiRoot) {
  ReactDOM.createRoot(uiRoot).render(
    <React.StrictMode>
      <ReactOverlay />
    </React.StrictMode>
  );
}
