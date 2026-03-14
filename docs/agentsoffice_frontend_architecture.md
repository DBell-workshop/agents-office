# AgentsOffice Pixel RPG 前端技术架构设计

## 文档信息

| 项目     | 内容                                          |
| -------- | --------------------------------------------- |
| 项目名称 | AgentsOffice Pixel RPG 可视化界面             |
| 文档类型 | 前端技术架构设计                              |
| 创建日期 | 2026-03-12                                    |
| 技术栈   | Phaser 3 + React 19 + TypeScript + Vite       |
| 前置依赖 | AgentsOffice 容器层 API（FastAPI + PostgreSQL）|
| 设计原则 | RPG 即管理平台，游戏交互即管理操作            |

---

## 1. 整体架构设计

### 1.1 架构选型：方案 B -- Phaser 为主 + React HUD Overlay

**推荐方案 B：Phaser 全屏渲染，React 以 DOM overlay 形式覆盖其上做面板和 HUD。**

两种方案对比：

| 维度               | 方案 A：React 管路由 + Phaser 嵌入       | 方案 B：Phaser 为主 + React Overlay   |
| ------------------ | ---------------------------------------- | ------------------------------------- |
| 渲染层级           | React DOM -> Phaser Canvas 嵌套         | Phaser Canvas 全屏 -> React DOM 浮层  |
| 路由控制           | React Router 管页面切换                  | Phaser Scene 管场景，React 只管面板   |
| 性能               | DOM 和 Canvas 双重布局，性能一般         | Canvas 全屏渲染，面板按需挂载，性能好 |
| 游戏体验           | 游戏区域被 React 布局约束，像"嵌入的小游戏"| 全屏沉浸，像"真正的游戏"             |
| 开发复杂度         | React 生命周期和 Phaser 生命周期容易冲突  | 职责清晰：Phaser 管世界，React 管 UI  |
| 场景切换           | 需要 React Router + Phaser Scene 双重管理 | Phaser SceneManager 统一管理          |
| 状态同步           | React state 驱动 Phaser，双向同步复杂     | EventBus 单向通信，简洁               |
| 适合场景           | "游戏是页面的一部分"                       | "整个页面就是游戏"                     |

**选择方案 B 的核心理由：**

1. **产品定位决定了选择**：AgentsOffice 的定位是"RPG 界面本身就是管理平台"，不是"管理后台里嵌个小游戏"。用户打开浏览器看到的应该是一个像素风格的虚拟办公室全景，而不是一个传统 Web 页面里嵌了一个 Canvas 区域。

2. **性能更优**：Phaser 全屏渲染时，Canvas 尺寸固定为窗口大小，不受 DOM 布局影响。React 面板按需挂载（打开时才渲染），关闭时完全卸载，不消耗 DOM 资源。

3. **职责划分清晰**：
   - Phaser 负责：场景渲染、角色动画、寻路移动、交互热区、摄像机控制
   - React 负责：数据面板、配置表单、图表展示、通知提示
   - 两者通过 EventBus 通信，互不侵入

4. **Phaser 官方支持**：Phaser 官方提供了 React 项目模板（`phaser-react-template`），推荐的模式就是 Phaser 管游戏循环，React 做 UI overlay。

### 1.2 架构分层

```
┌──────────────────────────────────────────────────────────────────┐
│                        浏览器窗口 (100vw x 100vh)                │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Layer 4: React Overlay (position: absolute, z-index: 10) │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐     │  │
│  │  │ Agent    │ │ Cost     │ │ Task     │ │ Event    │     │  │
│  │  │ Config   │ │ Monitor  │ │ Center   │ │ Log      │     │  │
│  │  │ Panel    │ │ Panel    │ │ Panel    │ │ Panel    │     │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘     │  │
│  │  ┌──────────────────────────────────────────────────────┐ │  │
│  │  │  HUD: Mini-map / Notification Toast / Status Bar     │ │  │
│  │  └──────────────────────────────────────────────────────┘ │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Layer 3: Phaser UI Layer (Phaser DOM/BitmapText)         │  │
│  │  - 角色名称标签                                            │  │
│  │  - 头顶气泡                                                │  │
│  │  - 状态图标                                                │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Layer 2: Phaser Sprite Layer                              │  │
│  │  - Agent 角色 sprites                                      │  │
│  │  - 交互物件 sprites                                        │  │
│  │  - 动画特效                                                │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Layer 1: Phaser Tilemap Layer                             │  │
│  │  - 地面层 (Ground)                                         │  │
│  │  - 墙壁层 (Walls)                                          │  │
│  │  - 家具层 (Furniture)                                      │  │
│  │  - 装饰层 (Decor)                                          │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Layer 0: HTML Canvas (Phaser Game)                        │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### 1.3 Phaser + React 共存实现

```typescript
// src/main.tsx -- 应用入口
import React from 'react';
import ReactDOM from 'react-dom/client';
import Phaser from 'phaser';
import { gameConfig } from './phaser/config';
import { ReactOverlay } from './react/ReactOverlay';
import { EventBus } from './shared/events/EventBus';

// 1. 先启动 Phaser Game（挂载到 #game-container）
const game = new Phaser.Game({
  ...gameConfig,
  parent: 'game-container',
});

// 2. 将 game 实例注入 EventBus，供 React 访问
EventBus.setGameInstance(game);

// 3. 再挂载 React Overlay（挂载到 #ui-overlay）
ReactDOM.createRoot(document.getElementById('ui-overlay')!).render(
  <React.StrictMode>
    <ReactOverlay />
  </React.StrictMode>
);
```

```html
<!-- index.html -->
<body style="margin: 0; overflow: hidden;">
  <!-- Phaser Canvas 渲染目标 -->
  <div id="game-container" style="position: absolute; top: 0; left: 0;"></div>

  <!-- React UI 浮层，覆盖在 Canvas 之上 -->
  <div id="ui-overlay" style="position: absolute; top: 0; left: 0;
       width: 100%; height: 100%; pointer-events: none; z-index: 10;"></div>
</body>
```

关键点：`#ui-overlay` 设置 `pointer-events: none`，默认不拦截鼠标事件，让点击穿透到下方的 Phaser Canvas。只有面板和按钮等 React 组件设置 `pointer-events: auto`，允许接收交互。

### 1.4 EventBus -- Phaser 与 React 的通信桥梁

```typescript
// src/shared/events/EventBus.ts
import Phaser from 'phaser';

type EventCallback = (...args: any[]) => void;

class GameEventBus {
  private emitter = new Phaser.Events.EventEmitter();
  private gameInstance: Phaser.Game | null = null;

  setGameInstance(game: Phaser.Game) {
    this.gameInstance = game;
  }

  getGameInstance(): Phaser.Game | null {
    return this.gameInstance;
  }

  // Phaser -> React: 游戏事件通知 UI 层
  emit(event: string, ...args: any[]) {
    this.emitter.emit(event, ...args);
  }

  // React -> Phaser: UI 操作通知游戏层
  on(event: string, callback: EventCallback, context?: any) {
    this.emitter.on(event, callback, context);
  }

  once(event: string, callback: EventCallback, context?: any) {
    this.emitter.once(event, callback, context);
  }

  off(event: string, callback?: EventCallback, context?: any) {
    this.emitter.off(event, callback, context);
  }
}

export const EventBus = new GameEventBus();
```

**事件流向定义：**

| 方向 | 事件 | 说明 |
| --- | --- | --- |
| Phaser -> React | `agent:clicked` | 用户点击了一个 Agent 角色，携带 agentId |
| Phaser -> React | `object:clicked` | 用户点击了一个可交互物件（监控墙、公告栏等） |
| Phaser -> React | `scene:ready` | Phaser 场景加载完毕 |
| React -> Phaser | `agent:config-updated` | 用户在面板中修改了 Agent 配置 |
| React -> Phaser | `panel:opened` | 面板打开，Phaser 需要暂停某些交互 |
| React -> Phaser | `panel:closed` | 面板关闭，Phaser 恢复交互 |
| WebSocket -> Both | `ws:agent-event` | 后端推送的 Agent 事件，同时通知 Phaser 和 React |

---

## 2. 场景设计

### 2.1 Tilemap 格式与工具链

**采用 Tiled Map Editor 导出的 JSON 格式**，Phaser 3 原生支持 Tiled JSON。

工具链：
- **Tiled Map Editor**（免费，https://www.mapeditor.org）-- 绘制 tilemap
- 导出格式：Tiled JSON (`.json`)
- Tileset 引用格式：嵌入式（Embedded Tileset）或外部引用

Tiled 项目配置：

```
Tile Size: 16x16 pixels（像素风标准尺寸）
Map Size: 40x30 tiles（640x480 逻辑像素）
Display Scale: 3x（实际渲染 1920x1440，摄像机裁切到视口）
Orientation: Orthogonal（正交视角，俯视 2D）
Render Order: Right-Down
```

### 2.2 场景分层

地图在 Tiled 中分为以下图层，从底到顶：

| 图层名称 | Tiled 类型 | 深度 (depth) | 说明 |
| --- | --- | --- | --- |
| `Ground` | Tile Layer | 0 | 地面（地板、地毯、走道） |
| `Walls` | Tile Layer | 1 | 墙壁、门框、窗户 |
| `Furniture_Below` | Tile Layer | 2 | 角色脚下的家具（桌子底部、椅子） |
| `Objects` | Object Layer | - | 交互物件的位置和属性（不渲染，用于逻辑） |
| `Furniture_Above` | Tile Layer | 10 | 角色头顶的家具部分（桌面物品、灯具） |
| `Collision` | Object Layer | - | 碰撞区域（不渲染，用于寻路碰撞检测） |
| `SpawnPoints` | Object Layer | - | 角色出生点 / 工位座标 |

**为什么分 `Furniture_Below` 和 `Furniture_Above`：** 角色的 depth 设为 3-9 之间（基于 y 坐标动态计算），这样角色走到桌子后面时，桌面物品（depth=10）会遮挡角色上半身，桌子底部（depth=2）在角色脚下，产生正确的前后遮挡关系。

### 2.3 办公室功能区划分

```
┌─────────────────────────────────────────────────────────┐
│                       墙 (Wall)                         │
│  ┌─────────────┐  ┌──────────────────────────────────┐  │
│  │   前台区     │  │          监控墙区                 │  │
│  │  Reception   │  │       Monitor Wall               │  │
│  │             │  │  ┌──────┐ ┌──────┐ ┌──────┐     │  │
│  │  [接待台]   │  │  │Cost  │ │Status│ │Alert │     │  │
│  │  [沙发]     │  │  │Panel │ │Board │ │Board │     │  │
│  │             │  │  └──────┘ └──────┘ └──────┘     │  │
│  └─────────────┘  └──────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │                   工位区 Desk Area                │   │
│  │                                                  │   │
│  │  [Desk 1]    [Desk 2]    [Desk 3]               │   │
│  │  Orchestr.   SalesCoach  PitchEval              │   │
│  │                                                  │   │
│  │  [Desk 4]    [Desk 5]    [Desk 6]               │   │
│  │  PriceIntel  RiskQA      Experiment             │   │
│  │                                                  │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  ┌────────────────┐  ┌───────────────────────────────┐  │
│  │  会议室         │  │        公告栏区                │  │
│  │  Meeting Room   │  │     Bulletin Board            │  │
│  │                │  │                               │  │
│  │  [会议桌]      │  │  [TaskBoard]  [EventLog]      │  │
│  │  [白板]        │  │  任务中心      事件日志         │  │
│  │                │  │                               │  │
│  └────────────────┘  └───────────────────────────────┘  │
│                       门 (Door)                         │
└─────────────────────────────────────────────────────────┘
```

### 2.4 交互热区定义

在 Tiled 的 `Objects` 图层中定义可交互物件，每个物件包含自定义属性：

| 物件名称 | Tiled 类型 | 自定义属性 | 点击行为 |
| --- | --- | --- | --- |
| `desk_1` ~ `desk_6` | Rectangle | `type: "desk"`, `agent_id: "agt_xxx"` | 高亮工位，聚焦对应 Agent |
| `monitor_cost` | Rectangle | `type: "monitor"`, `panel: "cost"` | 打开成本监控面板 |
| `monitor_status` | Rectangle | `type: "monitor"`, `panel: "status"` | 打开 Agent 状态总览面板 |
| `monitor_alert` | Rectangle | `type: "monitor"`, `panel: "alerts"` | 打开告警面板 |
| `task_board` | Rectangle | `type: "board"`, `panel: "tasks"` | 打开任务中心面板 |
| `event_log` | Rectangle | `type: "board"`, `panel: "events"` | 打开事件日志面板 |
| `meeting_table` | Rectangle | `type: "meeting"` | 显示协作任务概览 |
| `whiteboard` | Rectangle | `type: "whiteboard"` | 显示系统架构/工作流概览 |
| `reception_desk` | Rectangle | `type: "reception"` | 注册新 Agent 入口 |

**Phaser 中加载交互热区：**

```typescript
// 从 Tiled Object Layer 读取交互区域
const objectLayer = map.getObjectLayer('Objects');

objectLayer?.objects.forEach(obj => {
  const zone = this.add.zone(
    obj.x! + obj.width! / 2,
    obj.y! + obj.height! / 2,
    obj.width!,
    obj.height!
  );
  zone.setInteractive({ useHandCursor: true });
  zone.setData('properties', obj.properties);

  zone.on('pointerdown', () => {
    const props = obj.properties?.reduce((acc, p) => {
      acc[p.name] = p.value;
      return acc;
    }, {} as Record<string, any>);

    if (props?.type === 'desk') {
      EventBus.emit('agent:clicked', { agentId: props.agent_id });
    } else if (props?.panel) {
      EventBus.emit('object:clicked', { panel: props.panel });
    }
  });
});
```

---

## 3. 角色系统

### 3.1 Sprite 动画状态机

每个 Agent 角色拥有以下动画状态，使用有限状态机（FSM）管理：

```
                    ┌──────────┐
        spawn       │          │       despawn
    ───────────────>│   IDLE   │──────────────────> [removed]
                    │          │
                    └────┬─────┘
                         │
              ┌──────────┼──────────┐
              │          │          │
              v          v          v
         ┌────────┐ ┌────────┐ ┌────────┐
         │  WALK  │ │ THINK  │ │  WORK  │
         │        │ │        │ │        │
         └───┬────┘ └───┬────┘ └───┬────┘
             │          │          │
             │     ┌────v────┐     │
             │     │  SPEAK  │     │
             │     │         │     │
             │     └────┬────┘     │
             │          │          │
             └──────────┼──────────┘
                        │
              ┌─────────┼─────────┐
              v                   v
         ┌────────┐          ┌────────┐
         │COMPLETE│          │ ERROR  │
         │   ✓    │          │   !    │
         └───┬────┘          └───┬────┘
             │                   │
             └─────────┬─────────┘
                       │
                       v
                  ┌────────┐
                  │  IDLE  │
                  └────────┘
```

**动画状态定义：**

| 状态 | Sprite 行 | 帧数 | 帧率 | 循环 | 视觉效果 |
| --- | --- | --- | --- | --- | --- |
| `idle` | row 0 | 4 帧 | 4fps | 循环 | 坐在工位，微小呼吸动作 |
| `walk` | row 1-4 | 4 帧/方向 | 8fps | 循环 | 四方向行走（下/左/右/上） |
| `think` | row 5 | 4 帧 | 2fps | 循环 | 头顶出现 `...` 思考气泡 |
| `speak` | row 6 | 4 帧 | 6fps | 循环 | 嘴巴动作 + 对话气泡 |
| `work` | row 7 | 6 帧 | 6fps | 循环 | 敲键盘 / 操作动作 |
| `complete` | row 8 | 6 帧 | 8fps | 单次 | 站起来 + 绿色星星特效 |
| `error` | row 9 | 4 帧 | 4fps | 单次 | 摇头 + 红色叹号标记 |

**状态机实现：**

```typescript
// src/phaser/sprites/AgentSprite.ts

import Phaser from 'phaser';
import { EventBus } from '../../shared/events/EventBus';

export type AgentAnimState =
  | 'idle' | 'walk' | 'think' | 'speak'
  | 'work' | 'complete' | 'error';

interface AgentConfig {
  agentId: string;
  name: string;
  slug: string;
  spriteKey: string;     // sprite sheet 的 texture key
  homePosition: { x: number; y: number };  // 工位坐标
}

export class AgentSprite extends Phaser.GameObjects.Container {
  private sprite: Phaser.GameObjects.Sprite;
  private nameLabel: Phaser.GameObjects.BitmapText;
  private statusIcon: Phaser.GameObjects.Sprite | null = null;
  private bubble: Phaser.GameObjects.Container | null = null;

  private currentState: AgentAnimState = 'idle';
  private config: AgentConfig;
  private moveTarget: { x: number; y: number } | null = null;
  private movePath: { x: number; y: number }[] = [];
  private moveSpeed: number = 80; // pixels per second

  constructor(scene: Phaser.Scene, config: AgentConfig) {
    super(scene, config.homePosition.x, config.homePosition.y);
    this.config = config;

    // 创建角色 sprite
    this.sprite = scene.add.sprite(0, 0, config.spriteKey);
    this.sprite.setOrigin(0.5, 1); // 底部中心为锚点
    this.add(this.sprite);

    // 创建名称标签
    this.nameLabel = scene.add.bitmapText(
      0, -this.sprite.height - 4,
      'pixel-font', config.name, 8
    );
    this.nameLabel.setOrigin(0.5, 1);
    this.add(this.nameLabel);

    // 设置交互
    this.sprite.setInteractive({ useHandCursor: true });
    this.sprite.on('pointerdown', () => {
      EventBus.emit('agent:clicked', { agentId: config.agentId });
    });

    // 初始播放 idle 动画
    this.setState('idle');

    scene.add.existing(this);
  }

  setState(newState: AgentAnimState, data?: any) {
    if (this.currentState === newState && newState !== 'speak') return;

    const prevState = this.currentState;
    this.currentState = newState;

    // 清理上一个状态的附属物
    this.clearBubble();
    this.clearStatusIcon();

    switch (newState) {
      case 'idle':
        this.sprite.play(`${this.config.spriteKey}_idle`);
        break;

      case 'walk':
        // 方向由 movePath 决定，在 update 中动态切换
        this.sprite.play(`${this.config.spriteKey}_walk_down`);
        break;

      case 'think':
        this.sprite.play(`${this.config.spriteKey}_idle`);
        this.showThinkBubble();
        break;

      case 'speak':
        this.sprite.play(`${this.config.spriteKey}_speak`);
        this.showSpeechBubble(data?.message || '...');
        break;

      case 'work':
        this.sprite.play(`${this.config.spriteKey}_work`);
        break;

      case 'complete':
        this.sprite.play(`${this.config.spriteKey}_complete`);
        this.showStatusIcon('complete');
        // 完成动画播放后回到 idle
        this.sprite.once('animationcomplete', () => {
          this.setState('idle');
        });
        break;

      case 'error':
        this.sprite.play(`${this.config.spriteKey}_error`);
        this.showStatusIcon('error');
        break;
    }
  }

  // 移动到目标位置
  moveTo(target: { x: number; y: number }, path?: { x: number; y: number }[]) {
    if (path && path.length > 0) {
      this.movePath = [...path];
      this.moveTarget = this.movePath.shift()!;
    } else {
      this.movePath = [];
      this.moveTarget = target;
    }
    this.setState('walk');
  }

  // 回到工位
  returnHome() {
    this.moveTo(this.config.homePosition);
  }

  update(time: number, delta: number) {
    if (this.currentState === 'walk' && this.moveTarget) {
      const dx = this.moveTarget.x - this.x;
      const dy = this.moveTarget.y - this.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const step = (this.moveSpeed * delta) / 1000;

      if (dist <= step) {
        // 到达当前路径点
        this.x = this.moveTarget.x;
        this.y = this.moveTarget.y;

        if (this.movePath.length > 0) {
          this.moveTarget = this.movePath.shift()!;
        } else {
          this.moveTarget = null;
          this.setState('idle');
        }
      } else {
        // 移动中
        const vx = (dx / dist) * step;
        const vy = (dy / dist) * step;
        this.x += vx;
        this.y += vy;

        // 根据移动方向切换动画
        this.updateWalkDirection(dx, dy);
      }

      // 动态更新 depth（y 轴排序，模拟前后遮挡）
      this.setDepth(3 + this.y / 1000);
    }
  }

  private updateWalkDirection(dx: number, dy: number) {
    const absX = Math.abs(dx);
    const absY = Math.abs(dy);
    let dir: string;

    if (absY > absX) {
      dir = dy > 0 ? 'down' : 'up';
    } else {
      dir = dx > 0 ? 'right' : 'left';
    }

    const animKey = `${this.config.spriteKey}_walk_${dir}`;
    if (this.sprite.anims.currentAnim?.key !== animKey) {
      this.sprite.play(animKey, true);
    }
  }

  private showThinkBubble() {
    this.bubble = this.scene.add.container(0, -this.sprite.height - 16);

    const bg = this.scene.add.graphics();
    bg.fillStyle(0xffffff, 0.9);
    bg.fillRoundedRect(-12, -10, 24, 16, 4);
    this.bubble.add(bg);

    const dots = this.scene.add.bitmapText(0, -2, 'pixel-font', '...', 8);
    dots.setOrigin(0.5, 0.5);
    this.bubble.add(dots);

    // 思考气泡跳动动画
    this.scene.tweens.add({
      targets: this.bubble,
      y: this.bubble.y - 3,
      duration: 600,
      yoyo: true,
      repeat: -1,
      ease: 'Sine.easeInOut',
    });

    this.add(this.bubble);
  }

  private showSpeechBubble(message: string) {
    this.bubble = this.scene.add.container(0, -this.sprite.height - 20);

    // 限制显示文字长度
    const displayText = message.length > 30
      ? message.substring(0, 27) + '...'
      : message;

    const text = this.scene.add.bitmapText(0, 0, 'pixel-font', displayText, 8);
    text.setOrigin(0.5, 0.5);
    text.setMaxWidth(120);

    const bounds = text.getTextBounds();
    const padding = 6;
    const bg = this.scene.add.graphics();
    bg.fillStyle(0xffffff, 0.95);
    bg.fillRoundedRect(
      -bounds.global.width / 2 - padding,
      -bounds.global.height / 2 - padding,
      bounds.global.width + padding * 2,
      bounds.global.height + padding * 2,
      4
    );
    // 气泡小尾巴
    bg.fillTriangle(
      -4, bounds.global.height / 2 + padding,
      4, bounds.global.height / 2 + padding,
      0, bounds.global.height / 2 + padding + 6
    );

    this.bubble.add(bg);
    this.bubble.add(text);
    this.add(this.bubble);

    // 对话气泡 5 秒后自动消失
    this.scene.time.delayedCall(5000, () => {
      this.clearBubble();
    });
  }

  private showStatusIcon(type: 'complete' | 'error') {
    const iconKey = type === 'complete' ? 'icon_check' : 'icon_error';
    this.statusIcon = this.scene.add.sprite(
      8, -this.sprite.height - 4,
      'ui_icons', iconKey
    );
    this.add(this.statusIcon);

    // 闪烁效果
    this.scene.tweens.add({
      targets: this.statusIcon,
      alpha: { from: 1, to: 0.3 },
      duration: 500,
      yoyo: true,
      repeat: type === 'error' ? -1 : 3,
    });
  }

  private clearBubble() {
    if (this.bubble) {
      this.bubble.destroy();
      this.bubble = null;
    }
  }

  private clearStatusIcon() {
    if (this.statusIcon) {
      this.statusIcon.destroy();
      this.statusIcon = null;
    }
  }

  getAgentId(): string {
    return this.config.agentId;
  }

  getCurrentState(): AgentAnimState {
    return this.currentState;
  }
}
```

### 3.2 角色移动系统 -- 简化 A* 寻路

选择 **EasyStar.js** 作为寻路库，原因：
- 轻量（~10KB），专为 tile-based 游戏设计
- 异步计算不阻塞游戏循环
- 与 Phaser tilemap 集成简单

```typescript
// src/phaser/systems/PathfindingSystem.ts

import EasyStar from 'easystarjs';

export class PathfindingSystem {
  private easystar: EasyStar.js;
  private tileWidth: number;
  private tileHeight: number;

  constructor(collisionLayer: Phaser.Tilemaps.TilemapLayer) {
    this.easystar = new EasyStar.js();
    this.tileWidth = collisionLayer.tilemap.tileWidth;
    this.tileHeight = collisionLayer.tilemap.tileHeight;

    // 从 tilemap 碰撞层构建寻路网格
    const grid: number[][] = [];
    for (let y = 0; y < collisionLayer.tilemap.height; y++) {
      const row: number[] = [];
      for (let x = 0; x < collisionLayer.tilemap.width; x++) {
        const tile = collisionLayer.getTileAt(x, y);
        // 有 tile 的位置是障碍物（1），空位置可通行（0）
        row.push(tile ? 1 : 0);
      }
      grid.push(row);
    }

    this.easystar.setGrid(grid);
    this.easystar.setAcceptableTiles([0]);
    this.easystar.enableDiagonals();
    this.easystar.enableCornerCutting();
  }

  findPath(
    fromX: number, fromY: number,
    toX: number, toY: number
  ): Promise<{ x: number; y: number }[]> {
    // 世界坐标 -> tile 坐标
    const startTileX = Math.floor(fromX / this.tileWidth);
    const startTileY = Math.floor(fromY / this.tileHeight);
    const endTileX = Math.floor(toX / this.tileWidth);
    const endTileY = Math.floor(toY / this.tileHeight);

    return new Promise((resolve) => {
      this.easystar.findPath(
        startTileX, startTileY, endTileX, endTileY,
        (path) => {
          if (path === null) {
            resolve([]);
            return;
          }
          // tile 坐标 -> 世界坐标（tile 中心）
          const worldPath = path.map(p => ({
            x: p.x * this.tileWidth + this.tileWidth / 2,
            y: p.y * this.tileHeight + this.tileHeight / 2,
          }));
          resolve(worldPath);
        }
      );
      this.easystar.calculate();
    });
  }
}
```

### 3.3 头顶信息显示

角色头顶信息分三层：

```
        ┌─────────────────────┐
        │  对话/思考气泡       │  <- Layer 3 (动态，按需显示)
        └─────────────────────┘
        ┌────────┐
        │ ✓ / !  │               <- Layer 2 (状态图标，按需显示)
        └────────┘
        ┌─────────────────────┐
        │  Agent 名称          │  <- Layer 1 (常驻显示)
        └─────────────────────┘
        ╔═════════════════════╗
        ║                     ║
        ║   角色 Sprite       ║
        ║                     ║
        ╚═════════════════════╝
```

名称标签使用 BitmapText（像素字体），气泡和图标使用 Sprite + Graphics 组合。所有头顶元素作为 Container 的子对象跟随角色移动。

### 3.4 角色之间的交互动画

当两个 Agent 需要协作时（例如 Orchestrator 向 PriceIntel 下发任务），动画序列：

```
1. Orchestrator 从工位站起 (idle -> walk)
2. 寻路走到 PriceIntel 工位旁 (A* 路径)
3. 面向 PriceIntel (调整 sprite 朝向)
4. 播放 speak 动画 + 显示对话气泡 "下发任务: 比价分析"
5. PriceIntel 播放 think 动画 (表示接收任务)
6. PriceIntel 切换到 work 动画 (开始执行)
7. Orchestrator 走回工位 (walk -> idle)
```

实现为动画序列编排器：

```typescript
// src/phaser/systems/InteractionSequencer.ts

interface SequenceStep {
  type: 'move' | 'anim' | 'speak' | 'wait' | 'callback';
  target: string;          // agentId
  data?: any;
  duration?: number;       // ms
}

export class InteractionSequencer {
  private scene: Phaser.Scene;
  private agentManager: AgentManager;
  private pathfinding: PathfindingSystem;

  async playSequence(steps: SequenceStep[]) {
    for (const step of steps) {
      const agent = this.agentManager.getAgent(step.target);
      if (!agent) continue;

      switch (step.type) {
        case 'move':
          const path = await this.pathfinding.findPath(
            agent.x, agent.y,
            step.data.x, step.data.y
          );
          agent.moveTo(step.data, path);
          // 等待到达
          await this.waitUntilArrived(agent);
          break;

        case 'anim':
          agent.setState(step.data.state, step.data);
          if (step.duration) {
            await this.delay(step.duration);
          }
          break;

        case 'speak':
          agent.setState('speak', { message: step.data.message });
          await this.delay(step.duration || 3000);
          break;

        case 'wait':
          await this.delay(step.duration || 1000);
          break;

        case 'callback':
          if (step.data?.fn) step.data.fn();
          break;
      }
    }
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => {
      this.scene.time.delayedCall(ms, resolve);
    });
  }

  private waitUntilArrived(agent: AgentSprite): Promise<void> {
    return new Promise(resolve => {
      const check = () => {
        if (agent.getCurrentState() !== 'walk') {
          resolve();
        } else {
          this.scene.time.delayedCall(100, check);
        }
      };
      check();
    });
  }
}
```

---

## 4. WebSocket 事件 -> 角色行为映射

### 4.1 WebSocket 连接管理

```typescript
// src/shared/api/WebSocketClient.ts

import { EventBus } from '../events/EventBus';

export interface AgentEvent {
  event_id: number;
  trace_id: string;
  agent_name: string;      // agent slug
  event_type: string;
  session_id?: string;
  payload: Record<string, any>;
  created_at: string;
}

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectDelay = 1000;
  private heartbeatInterval: number | null = null;

  constructor(url: string = `ws://${window.location.host}/api/v1/office/ws/events`) {
    this.url = url;
  }

  connect() {
    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      console.log('[WS] Connected');
      this.reconnectAttempts = 0;
      this.startHeartbeat();
      EventBus.emit('ws:connected');
    };

    this.ws.onmessage = (event) => {
      try {
        const data: AgentEvent = JSON.parse(event.data);
        this.handleEvent(data);
      } catch (e) {
        console.warn('[WS] Failed to parse message:', e);
      }
    };

    this.ws.onclose = (event) => {
      console.log('[WS] Disconnected:', event.code);
      this.stopHeartbeat();
      EventBus.emit('ws:disconnected');
      this.attemptReconnect();
    };

    this.ws.onerror = (error) => {
      console.error('[WS] Error:', error);
    };
  }

  private handleEvent(event: AgentEvent) {
    // 统一分发到 EventBus
    EventBus.emit('ws:agent-event', event);

    // 按事件类型分发到具体频道
    EventBus.emit(`ws:${event.event_type}`, event);
  }

  private attemptReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[WS] Max reconnect attempts reached');
      EventBus.emit('ws:reconnect-failed');
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
    console.log(`[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

    setTimeout(() => this.connect(), delay);
  }

  private startHeartbeat() {
    this.heartbeatInterval = window.setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);
  }

  private stopHeartbeat() {
    if (this.heartbeatInterval !== null) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  disconnect() {
    this.stopHeartbeat();
    this.ws?.close();
  }
}
```

### 4.2 事件 -> 行为映射表

后端 `agent_events` 表的 `event_type` 与前端角色行为的完整映射：

| 后端 event_type | Phaser 角色行为 | payload 关键字段 | React UI 行为 |
| --- | --- | --- | --- |
| `agent_spawn` | 角色在工位位置出现（淡入动画） | `agent_id`, `position` | 通知栏提示 "Agent 上线" |
| `agent_think` | 切换到 think 状态，头顶 `...` 气泡 | `agent_id`, `thought` | 事件流新增一条 |
| `agent_speak` | 切换到 speak 状态，显示对话气泡 | `agent_id`, `message`, `target_agent` | 事件流 + 对话气泡内容 |
| `agent_act` | 切换到 work 状态，敲键盘动画 | `agent_id`, `action`, `skill_used` | 任务进度更新 |
| `agent_move` | 使用 A* 寻路移动到目标位置 | `agent_id`, `x`, `y`, `target_agent` | 事件流记录移动 |
| `agent_complete` | 播放完成特效，回到工位 | `agent_id`, `result_summary` | 任务状态更新为 "完成" |
| `agent_error` | 播放错误动画，头顶红色叹号 | `agent_id`, `error_message` | 告警通知 + 错误详情 |
| `agent_idle` | 回到 idle 状态 | `agent_id` | Agent 状态卡片更新 |
| `task_created` | Orchestrator 角色站起来 | `task_id`, `task_type` | 任务中心新增条目 |
| `task_assigned` | Orchestrator 走向目标 Agent 对话 | `task_id`, `agent_id` | 任务关联 Agent |
| `cost_recorded` | 角色头顶短暂显示费用数字 | `agent_id`, `total_cost` | 成本面板实时更新 |

### 4.3 事件处理器实现

```typescript
// src/phaser/systems/EventHandler.ts

import { EventBus } from '../../shared/events/EventBus';
import type { AgentEvent } from '../../shared/api/WebSocketClient';

export class AgentEventHandler {
  private scene: Phaser.Scene;
  private agentManager: AgentManager;
  private sequencer: InteractionSequencer;

  constructor(scene: Phaser.Scene, agentManager: AgentManager) {
    this.scene = scene;
    this.agentManager = agentManager;
    this.sequencer = new InteractionSequencer(scene, agentManager);

    this.registerListeners();
  }

  private registerListeners() {
    EventBus.on('ws:agent-event', this.handleAgentEvent, this);
  }

  private async handleAgentEvent(event: AgentEvent) {
    const agent = this.agentManager.getAgentBySlug(event.agent_name);

    switch (event.event_type) {
      case 'agent_spawn':
        this.handleSpawn(event);
        break;

      case 'agent_think':
        if (agent) {
          agent.setState('think');
        }
        break;

      case 'agent_speak':
        if (agent) {
          agent.setState('speak', { message: event.payload.message });
        }
        // 如果有 target_agent，编排走过去对话的序列
        if (event.payload.target_agent) {
          await this.handleAgentInteraction(event);
        }
        break;

      case 'agent_act':
        if (agent) {
          agent.setState('work');
        }
        break;

      case 'agent_move':
        if (agent && event.payload.x !== undefined) {
          const targetAgent = event.payload.target_agent
            ? this.agentManager.getAgentBySlug(event.payload.target_agent)
            : null;

          const targetPos = targetAgent
            ? { x: targetAgent.x + 20, y: targetAgent.y }
            : { x: event.payload.x, y: event.payload.y };

          agent.moveTo(targetPos);
        }
        break;

      case 'agent_complete':
        if (agent) {
          agent.setState('complete');
          // 完成后延迟回到工位
          this.scene.time.delayedCall(2000, () => {
            agent.returnHome();
          });
        }
        break;

      case 'agent_error':
        if (agent) {
          agent.setState('error');
        }
        break;

      case 'agent_idle':
        if (agent) {
          agent.setState('idle');
        }
        break;

      case 'task_assigned':
        await this.handleTaskAssignment(event);
        break;
    }
  }

  private handleSpawn(event: AgentEvent) {
    const existingAgent = this.agentManager.getAgentBySlug(event.agent_name);
    if (existingAgent) return; // 已存在则忽略

    // 创建新角色（从 API 获取配置后实例化）
    // 这里简化处理，实际应从 agent registry 获取完整配置
    this.agentManager.spawnAgent({
      agentId: event.payload.agent_id,
      name: event.agent_name,
      slug: event.agent_name,
      spriteKey: event.payload.sprite_key || 'agent_default',
      homePosition: event.payload.position || { x: 200, y: 200 },
    });
  }

  private async handleAgentInteraction(event: AgentEvent) {
    const source = this.agentManager.getAgentBySlug(event.agent_name);
    const target = this.agentManager.getAgentBySlug(event.payload.target_agent);
    if (!source || !target) return;

    await this.sequencer.playSequence([
      { type: 'move', target: source.getAgentId(), data: { x: target.x - 24, y: target.y } },
      { type: 'speak', target: source.getAgentId(), data: { message: event.payload.message }, duration: 3000 },
      { type: 'anim', target: target.getAgentId(), data: { state: 'think' }, duration: 1500 },
      { type: 'anim', target: target.getAgentId(), data: { state: 'work' } },
      { type: 'move', target: source.getAgentId(), data: source.config.homePosition },
    ]);
  }

  private async handleTaskAssignment(event: AgentEvent) {
    const orchestrator = this.agentManager.getAgentBySlug('orchestrator');
    const targetAgent = this.agentManager.getAgentBySlug(event.payload.agent_slug);
    if (!orchestrator || !targetAgent) return;

    await this.sequencer.playSequence([
      { type: 'move', target: orchestrator.getAgentId(), data: { x: targetAgent.x - 24, y: targetAgent.y } },
      { type: 'speak', target: orchestrator.getAgentId(), data: { message: `分配任务: ${event.payload.task_type}` }, duration: 2500 },
      { type: 'wait', target: orchestrator.getAgentId(), duration: 500 },
      { type: 'anim', target: targetAgent.getAgentId(), data: { state: 'think' }, duration: 1000 },
      { type: 'anim', target: targetAgent.getAgentId(), data: { state: 'work' } },
      { type: 'move', target: orchestrator.getAgentId(), data: { x: orchestrator.x, y: orchestrator.y } },
    ]);
  }

  destroy() {
    EventBus.off('ws:agent-event', this.handleAgentEvent, this);
  }
}
```

---

## 5. React UI 面板设计

### 5.1 面板系统架构

所有 React 面板共享统一的面板管理器，支持多面板同时打开、拖拽移动、层级管理。

```typescript
// src/react/hooks/usePanelManager.ts

import { create } from 'zustand';

export type PanelType =
  | 'agent-config'
  | 'cost-monitor'
  | 'task-center'
  | 'event-log'
  | 'agent-status'
  | 'alerts';

interface PanelState {
  id: string;
  type: PanelType;
  title: string;
  props: Record<string, any>;
  position: { x: number; y: number };
  size: { width: number; height: number };
  zIndex: number;
  isMinimized: boolean;
}

interface PanelStore {
  panels: PanelState[];
  nextZIndex: number;

  openPanel: (type: PanelType, props?: Record<string, any>) => void;
  closePanel: (id: string) => void;
  focusPanel: (id: string) => void;
  minimizePanel: (id: string) => void;
  movePanel: (id: string, position: { x: number; y: number }) => void;
  closeAll: () => void;
}

export const usePanelStore = create<PanelStore>((set, get) => ({
  panels: [],
  nextZIndex: 100,

  openPanel: (type, props = {}) => {
    const { panels, nextZIndex } = get();

    // 如果同类型面板已打开，聚焦它
    const existing = panels.find(p => p.type === type && !p.props.agentId || p.props.agentId === props.agentId);
    if (existing) {
      get().focusPanel(existing.id);
      return;
    }

    const panelConfigs: Record<PanelType, { title: string; size: { width: number; height: number } }> = {
      'agent-config': { title: 'Agent 配置', size: { width: 480, height: 600 } },
      'cost-monitor': { title: '成本监控', size: { width: 640, height: 480 } },
      'task-center': { title: '任务中心', size: { width: 560, height: 500 } },
      'event-log': { title: '事件日志', size: { width: 520, height: 440 } },
      'agent-status': { title: 'Agent 总览', size: { width: 720, height: 500 } },
      'alerts': { title: '告警中心', size: { width: 400, height: 360 } },
    };

    const config = panelConfigs[type];
    const id = `${type}-${Date.now()}`;

    // 居中打开，稍有偏移避免完全重叠
    const offsetIndex = panels.length;
    const position = {
      x: Math.max(40, (window.innerWidth - config.size.width) / 2 + offsetIndex * 20),
      y: Math.max(40, (window.innerHeight - config.size.height) / 2 + offsetIndex * 20),
    };

    set({
      panels: [...panels, {
        id,
        type,
        title: config.title,
        props,
        position,
        size: config.size,
        zIndex: nextZIndex,
        isMinimized: false,
      }],
      nextZIndex: nextZIndex + 1,
    });

    // 通知 Phaser 有面板打开
    EventBus.emit('panel:opened', { panelType: type });
  },

  closePanel: (id) => {
    set(state => ({
      panels: state.panels.filter(p => p.id !== id),
    }));

    const { panels } = get();
    if (panels.length === 0) {
      EventBus.emit('panel:closed');
    }
  },

  focusPanel: (id) => {
    const { nextZIndex } = get();
    set(state => ({
      panels: state.panels.map(p =>
        p.id === id ? { ...p, zIndex: nextZIndex, isMinimized: false } : p
      ),
      nextZIndex: nextZIndex + 1,
    }));
  },

  minimizePanel: (id) => {
    set(state => ({
      panels: state.panels.map(p =>
        p.id === id ? { ...p, isMinimized: !p.isMinimized } : p
      ),
    }));
  },

  movePanel: (id, position) => {
    set(state => ({
      panels: state.panels.map(p =>
        p.id === id ? { ...p, position } : p
      ),
    }));
  },

  closeAll: () => {
    set({ panels: [] });
    EventBus.emit('panel:closed');
  },
}));
```

### 5.2 面板容器组件

```tsx
// src/react/components/PanelContainer.tsx

import React, { useRef, useCallback } from 'react';
import type { PanelState } from '../hooks/usePanelManager';
import { usePanelStore } from '../hooks/usePanelManager';

interface Props {
  panel: PanelState;
  children: React.ReactNode;
}

export const PanelContainer: React.FC<Props> = ({ panel, children }) => {
  const { closePanel, focusPanel, movePanel, minimizePanel } = usePanelStore();
  const dragRef = useRef<{ startX: number; startY: number; panelX: number; panelY: number } | null>(null);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    focusPanel(panel.id);
    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      panelX: panel.position.x,
      panelY: panel.position.y,
    };

    const handleMouseMove = (e: MouseEvent) => {
      if (!dragRef.current) return;
      movePanel(panel.id, {
        x: dragRef.current.panelX + (e.clientX - dragRef.current.startX),
        y: dragRef.current.panelY + (e.clientY - dragRef.current.startY),
      });
    };

    const handleMouseUp = () => {
      dragRef.current = null;
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, [panel.id, panel.position]);

  return (
    <div
      className="pixel-panel"
      style={{
        position: 'absolute',
        left: panel.position.x,
        top: panel.position.y,
        width: panel.size.width,
        height: panel.isMinimized ? 36 : panel.size.height,
        zIndex: panel.zIndex,
        pointerEvents: 'auto',
        fontFamily: '"Press Start 2P", monospace',
      }}
      onClick={() => focusPanel(panel.id)}
    >
      {/* 像素风标题栏 */}
      <div
        className="pixel-panel-header"
        onMouseDown={handleMouseDown}
        style={{
          height: 32,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 8px',
          cursor: 'move',
          userSelect: 'none',
          background: '#2a2a4a',
          color: '#fff',
          fontSize: 10,
          borderBottom: '2px solid #1a1a3a',
          imageRendering: 'pixelated',
        }}
      >
        <span>{panel.title}</span>
        <div style={{ display: 'flex', gap: 4 }}>
          <button
            onClick={(e) => { e.stopPropagation(); minimizePanel(panel.id); }}
            className="pixel-btn"
            aria-label={panel.isMinimized ? '展开面板' : '最小化面板'}
          >
            {panel.isMinimized ? '+' : '-'}
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); closePanel(panel.id); }}
            className="pixel-btn"
            aria-label="关闭面板"
          >
            x
          </button>
        </div>
      </div>

      {/* 面板内容 */}
      {!panel.isMinimized && (
        <div
          className="pixel-panel-body"
          style={{
            height: panel.size.height - 36,
            overflow: 'auto',
            background: '#1a1a2e',
            color: '#e0e0e0',
            padding: 12,
            fontSize: 10,
          }}
        >
          {children}
        </div>
      )}
    </div>
  );
};
```

### 5.3 各面板功能定义

#### Agent 配置面板

```
┌───────────────────────────────────────────────┐
│ Agent 配置 - Sales Coach Agent            _ x │
├───────────────────────────────────────────────┤
│                                               │
│  基本信息                                     │
│  ┌─────────────────────────────────────────┐  │
│  │ 名称:  Sales Coach Agent               │  │
│  │ 标识:  sales_coach                      │  │
│  │ 类型:  [generator ▼]                    │  │
│  │ 状态:  ● 运行中                         │  │
│  │ 描述:  生成卖点、话术、模拟问答...       │  │
│  └─────────────────────────────────────────┘  │
│                                               │
│  模型配置                                     │
│  ┌─────────────────────────────────────────┐  │
│  │ 模型:    [gpt-4o ▼]                     │  │
│  │ 温度:    [0.7 ═══════●═══]              │  │
│  │ Max Tok: [4096]                         │  │
│  └─────────────────────────────────────────┘  │
│                                               │
│  Skills                                       │
│  ┌─────────────────────────────────────────┐  │
│  │ [x] LLM 生成      [x] 语音合成          │  │
│  │ [x] 知识检索      [ ] 事实核验           │  │
│  │ [ ] 语音转写      [ ] 页面采集           │  │
│  │                         [+ 添加 Skill]   │  │
│  └─────────────────────────────────────────┘  │
│                                               │
│  最近活动                                     │
│  ┌─────────────────────────────────────────┐  │
│  │ 12:03  完成  导购话术生成任务            │  │
│  │ 11:45  执行  培训内容生成                │  │
│  │ 11:30  空闲  ---                         │  │
│  └─────────────────────────────────────────┘  │
│                                               │
│  费用统计                                     │
│  ┌─────────────────────────────────────────┐  │
│  │ 今日: ¥2.34 | 本周: ¥15.60 | 本月: ¥48 │  │
│  └─────────────────────────────────────────┘  │
│                                               │
│  [停用 Agent]                    [保存修改]    │
└───────────────────────────────────────────────┘
```

#### 成本监控面板

```
┌───────────────────────────────────────────────────────┐
│ 成本监控                                          _ x │
├───────────────────────────────────────────────────────┤
│                                                       │
│  总览                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│  │ 今日      │ │ 本周      │ │ 本月      │              │
│  │ ¥12.34   │ │ ¥85.60   │ │ ¥342.10  │              │
│  │ 156 calls│ │ 1.2K     │ │ 4.8K     │              │
│  └──────────┘ └──────────┘ └──────────┘              │
│                                                       │
│  费用趋势 (近 7 天)        [日 | 周 | 月]            │
│  ┌─────────────────────────────────────────────────┐  │
│  │     ╱╲                                          │  │
│  │    ╱  ╲    ╱╲                                   │  │
│  │   ╱    ╲  ╱  ╲   ╱╲                            │  │
│  │  ╱      ╲╱    ╲ ╱  ╲                           │  │
│  │ ╱              ╲    ╲_                          │  │
│  │ Mon Tue Wed Thu Fri Sat Sun                     │  │
│  └─────────────────────────────────────────────────┘  │
│                                                       │
│  按 Agent 排名                                        │
│  ┌─────────────────────────────────────────────────┐  │
│  │ 1. Sales Coach      ████████████████  ¥128.30  │  │
│  │ 2. Pitch Evaluator  ███████████       ¥ 89.50  │  │
│  │ 3. Price Intel      ████████          ¥ 67.20  │  │
│  │ 4. Risk QA          ████              ¥ 34.10  │  │
│  │ 5. Experiment       ██               ¥ 18.00  │  │
│  │ 6. Orchestrator     █                ¥  5.00  │  │
│  └─────────────────────────────────────────────────┘  │
│                                                       │
│  按模型排名                                           │
│  ┌─────────────────────────────────────────────────┐  │
│  │ gpt-4o        ██████████████████████  ¥285.00  │  │
│  │ gpt-4o-mini   ████████              ¥ 57.10  │  │
│  └─────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────┘
```

#### 任务中心面板

```
┌───────────────────────────────────────────────────────┐
│ 任务中心                                          _ x │
├───────────────────────────────────────────────────────┤
│                                                       │
│  筛选: [全部状态 ▼] [全部类型 ▼] [全部 Agent ▼]      │
│                                                       │
│  ┌─────────────────────────────────────────────────┐  │
│  │ ID        类型        Agent     状态   时间     │  │
│  ├─────────────────────────────────────────────────┤  │
│  │ tsk_a12   比价分析    PriceInt  ● 进行 12:05  │  │
│  │ tsk_a11   话术生成    SalesCo   ✓ 完成 11:58  │  │
│  │ tsk_a10   话术评分    PitchEv   ✓ 完成 11:45  │  │
│  │ tsk_a09   风险审核    RiskQA    ✓ 完成 11:30  │  │
│  │ tsk_a08   比价分析    PriceInt  ✗ 失败 11:15  │  │
│  └─────────────────────────────────────────────────┘  │
│                                                       │
│  任务详情: tsk_a12                                    │
│  ┌─────────────────────────────────────────────────┐  │
│  │ trace_id: tr_xxx                                │  │
│  │ 事件时间线:                                     │  │
│  │ 12:05 ▶ task_created                            │  │
│  │ 12:05 ▶ task_assigned -> PriceIntel             │  │
│  │ 12:06 ▶ agent_act: 页面采集                     │  │
│  │ 12:08 ▶ agent_act: 数据标准化                   │  │
│  │ 12:09 ● agent_think: 生成比价报告...            │  │
│  └─────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────┘
```

### 5.4 面板与 Phaser 的通信机制

```typescript
// src/react/hooks/useGameEvents.ts

import { useEffect, useCallback } from 'react';
import { EventBus } from '../../shared/events/EventBus';

/**
 * React Hook: 监听 Phaser/WebSocket 事件
 */
export function useGameEvent(
  eventName: string,
  callback: (...args: any[]) => void,
  deps: any[] = []
) {
  const memoizedCallback = useCallback(callback, deps);

  useEffect(() => {
    EventBus.on(eventName, memoizedCallback);
    return () => {
      EventBus.off(eventName, memoizedCallback);
    };
  }, [eventName, memoizedCallback]);
}

/**
 * React Hook: 监听 Agent 点击事件，自动打开配置面板
 */
export function useAgentClickHandler() {
  const { openPanel } = usePanelStore();

  useGameEvent('agent:clicked', ({ agentId }) => {
    openPanel('agent-config', { agentId });
  });

  useGameEvent('object:clicked', ({ panel }) => {
    const panelTypeMap: Record<string, PanelType> = {
      'cost': 'cost-monitor',
      'status': 'agent-status',
      'tasks': 'task-center',
      'events': 'event-log',
      'alerts': 'alerts',
    };
    const panelType = panelTypeMap[panel];
    if (panelType) {
      openPanel(panelType);
    }
  });
}
```

```typescript
// src/react/ReactOverlay.tsx

import React from 'react';
import { usePanelStore } from './hooks/usePanelManager';
import { useAgentClickHandler } from './hooks/useGameEvents';
import { PanelContainer } from './components/PanelContainer';
import { AgentConfigPanel } from './panels/AgentConfigPanel';
import { CostMonitorPanel } from './panels/CostMonitorPanel';
import { TaskCenterPanel } from './panels/TaskCenterPanel';
import { EventLogPanel } from './panels/EventLogPanel';
import { AgentStatusPanel } from './panels/AgentStatusPanel';
import { HUD } from './components/HUD';

const PANEL_COMPONENTS: Record<string, React.FC<any>> = {
  'agent-config': AgentConfigPanel,
  'cost-monitor': CostMonitorPanel,
  'task-center': TaskCenterPanel,
  'event-log': EventLogPanel,
  'agent-status': AgentStatusPanel,
  'alerts': EventLogPanel, // 临时复用
};

export const ReactOverlay: React.FC = () => {
  useAgentClickHandler();
  const { panels } = usePanelStore();

  return (
    <>
      {/* HUD 层: 常驻 UI */}
      <HUD />

      {/* 动态面板 */}
      {panels.map(panel => {
        const PanelContent = PANEL_COMPONENTS[panel.type];
        if (!PanelContent) return null;

        return (
          <PanelContainer key={panel.id} panel={panel}>
            <PanelContent {...panel.props} />
          </PanelContainer>
        );
      })}
    </>
  );
};
```

### 5.5 无障碍(Accessibility)设计要点

虽然是像素风格界面，React 面板仍需遵循 WCAG 2.1 AA 标准：

| 要素 | 实现方式 |
| --- | --- |
| 键盘导航 | 面板内所有控件可 Tab 切换，Escape 关闭面板 |
| 焦点管理 | 面板打开时焦点移入，关闭时焦点返回触发元素 |
| 屏幕阅读器 | 面板使用 `role="dialog"` + `aria-label`，状态变更使用 `aria-live` |
| 颜色对比 | 像素风色板确保文字与背景对比度 >= 4.5:1 |
| 替代文本 | 所有图标按钮提供 `aria-label` |
| 快捷键 | ESC=关闭面板, Ctrl+1~6=打开对应面板, Space=暂停/恢复场景 |

---

## 6. 项目结构

```
frontend/
├── index.html                         # 入口 HTML (game-container + ui-overlay)
├── package.json
├── tsconfig.json
├── vite.config.ts                     # Vite 构建配置
├── .eslintrc.cjs
├── .prettierrc
│
├── public/
│   └── fonts/
│       └── press-start-2p.ttf         # 像素字体
│
├── src/
│   ├── main.tsx                       # 应用入口 (Phaser + React 初始化)
│   ├── vite-env.d.ts
│   │
│   ├── phaser/                        # ======= Phaser 游戏层 =======
│   │   ├── config.ts                  # Phaser.Game 配置
│   │   │
│   │   ├── scenes/
│   │   │   ├── BootScene.ts           # 加载进度条、预加载资源
│   │   │   ├── PreloadScene.ts        # 资源加载（tilemap, sprites, audio）
│   │   │   └── OfficeScene.ts         # 主场景：办公室
│   │   │
│   │   ├── sprites/
│   │   │   ├── AgentSprite.ts         # Agent 角色类（动画状态机 + 头顶信息）
│   │   │   └── InteractiveObject.ts   # 可交互物件（高亮、工具提示）
│   │   │
│   │   ├── systems/
│   │   │   ├── AgentManager.ts        # Agent 角色生命周期管理
│   │   │   ├── PathfindingSystem.ts   # A* 寻路（EasyStar.js）
│   │   │   ├── EventHandler.ts        # WebSocket 事件 -> 角色行为映射
│   │   │   ├── InteractionSequencer.ts # 角色交互动画编排
│   │   │   └── CameraSystem.ts        # 摄像机跟随、缩放、边界限制
│   │   │
│   │   └── utils/
│   │       ├── AnimationFactory.ts    # 从 sprite sheet 批量创建动画
│   │       └── TilemapLoader.ts       # Tiled JSON 加载与图层解析
│   │
│   ├── react/                         # ======= React UI 层 =======
│   │   ├── ReactOverlay.tsx           # React 根组件（面板管理 + HUD）
│   │   │
│   │   ├── panels/
│   │   │   ├── AgentConfigPanel.tsx   # Agent 配置面板
│   │   │   ├── CostMonitorPanel.tsx   # 成本监控面板
│   │   │   ├── TaskCenterPanel.tsx    # 任务中心面板
│   │   │   ├── EventLogPanel.tsx      # 事件日志面板
│   │   │   └── AgentStatusPanel.tsx   # Agent 状态总览面板
│   │   │
│   │   ├── components/
│   │   │   ├── PanelContainer.tsx     # 像素风面板容器（拖拽、最小化、关闭）
│   │   │   ├── HUD.tsx               # 常驻 HUD（迷你地图、通知、状态栏）
│   │   │   ├── MiniMap.tsx           # 迷你地图组件
│   │   │   ├── NotificationToast.tsx  # 通知弹窗
│   │   │   ├── PixelButton.tsx        # 像素风按钮
│   │   │   ├── PixelInput.tsx         # 像素风输入框
│   │   │   ├── PixelSelect.tsx        # 像素风下拉框
│   │   │   ├── PixelSlider.tsx        # 像素风滑块
│   │   │   ├── PixelTable.tsx         # 像素风数据表格
│   │   │   └── PixelChart.tsx         # 像素风图表（基于 Recharts 自定义主题）
│   │   │
│   │   ├── hooks/
│   │   │   ├── usePanelManager.ts     # 面板状态管理 (Zustand)
│   │   │   ├── useGameEvents.ts       # EventBus 事件监听 Hook
│   │   │   ├── useAgentAPI.ts         # Agent CRUD API 调用
│   │   │   ├── useCostAPI.ts          # 成本数据 API 调用
│   │   │   ├── useTaskAPI.ts          # 任务数据 API 调用
│   │   │   └── useWebSocket.ts        # WebSocket 连接管理 Hook
│   │   │
│   │   └── styles/
│   │       ├── pixel-theme.css        # 像素风全局样式
│   │       └── panel.css              # 面板样式
│   │
│   ├── shared/                        # ======= 共享层 =======
│   │   ├── events/
│   │   │   ├── EventBus.ts            # Phaser <-> React 事件总线
│   │   │   └── eventTypes.ts          # 事件类型常量定义
│   │   │
│   │   ├── types/
│   │   │   ├── agent.ts               # Agent 相关 TypeScript 类型
│   │   │   ├── task.ts                # 任务相关类型
│   │   │   ├── cost.ts                # 成本相关类型
│   │   │   ├── event.ts               # 事件相关类型
│   │   │   └── game.ts                # 游戏相关类型（坐标、动画状态等）
│   │   │
│   │   └── api/
│   │       ├── httpClient.ts          # Axios/Fetch HTTP 客户端
│   │       ├── WebSocketClient.ts     # WebSocket 客户端（重连、心跳）
│   │       └── endpoints.ts           # API 端点常量
│   │
│   └── assets/                        # ======= 静态资源 =======
│       ├── tilesets/
│       │   ├── modern-interiors.png   # LimeZu Modern Interiors tileset
│       │   └── modern-interiors.json  # Tiled tileset 定义
│       │
│       ├── tilemaps/
│       │   └── office.json            # Tiled 导出的办公室地图 JSON
│       │
│       ├── sprites/
│       │   ├── agents/
│       │   │   ├── orchestrator.png   # 各 Agent 角色 sprite sheet
│       │   │   ├── sales_coach.png
│       │   │   ├── pitch_evaluator.png
│       │   │   ├── price_intel.png
│       │   │   ├── risk_qa.png
│       │   │   └── experiment.png
│       │   ├── effects/
│       │   │   ├── sparkle.png        # 完成特效
│       │   │   └── error_mark.png     # 错误标记
│       │   └── bubbles/
│       │       ├── think_bubble.png   # 思考气泡
│       │       └── speech_bubble.png  # 对话气泡框
│       │
│       ├── ui/
│       │   ├── panel-border.png       # 像素风面板边框 9-slice
│       │   ├── button-normal.png      # 按钮默认态
│       │   ├── button-hover.png       # 按钮悬停态
│       │   ├── button-pressed.png     # 按钮按下态
│       │   ├── icons.png              # UI 图标 sprite sheet
│       │   └── cursor.png             # 自定义像素光标
│       │
│       └── audio/
│           ├── click.wav              # 点击音效
│           ├── notification.wav       # 通知音效
│           └── complete.wav           # 完成音效
│
└── tiled/                             # ======= Tiled 工程文件 =======
    ├── office.tmx                     # Tiled 地图工程文件（不打包到产物）
    └── tilesets/
        └── modern-interiors.tsx       # Tiled tileset 工程文件
```

### 6.1 核心依赖清单

```json
{
  "dependencies": {
    "phaser": "^3.80.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "zustand": "^5.0.0",
    "easystarjs": "^0.4.4",
    "recharts": "^2.15.0",
    "axios": "^1.7.0"
  },
  "devDependencies": {
    "typescript": "^5.6.0",
    "vite": "^6.0.0",
    "@vitejs/plugin-react": "^4.3.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "eslint": "^9.0.0",
    "prettier": "^3.4.0"
  }
}
```

### 6.2 Vite 构建配置

```typescript
// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@phaser': path.resolve(__dirname, 'src/phaser'),
      '@react': path.resolve(__dirname, 'src/react'),
      '@shared': path.resolve(__dirname, 'src/shared'),
      '@assets': path.resolve(__dirname, 'src/assets'),
    },
  },
  build: {
    outDir: '../app/static/office',  // 构建输出到 FastAPI 静态文件目录
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks: {
          phaser: ['phaser'],         // Phaser 单独分包（~1.2MB）
          react: ['react', 'react-dom'],
          ui: ['zustand', 'recharts'],
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/api/v1/office/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
});
```

---

## 7. 素材方案落地

### 7.1 免费素材清单

| 素材 | 来源 | 许可证 | 用途 | 下载地址 |
| --- | --- | --- | --- | --- |
| Modern Interiors | LimeZu (itch.io) | Free 版可商用（需署名） | 办公室 tileset：地板、墙壁、桌椅、电脑、显示器 | https://limezu.itch.io/moderninteriors |
| Pixel UI Pack | Kenney | CC0 (公共领域) | UI 按钮、面板边框、滑块、进度条 | https://kenney.nl/assets/pixel-ui-pack |
| 1-Bit Pack | Kenney | CC0 | 备用图标、状态标记 | https://kenney.nl/assets/1-bit-pack |
| Press Start 2P | Google Fonts | OFL | 像素字体 | https://fonts.google.com/specimen/Press+Start+2P |

**LimeZu 署名要求**：在关于页面或启动画面标注 "Office tileset by LimeZu"。

### 7.2 Sprite Sheet 格式与尺寸规范

**角色 Sprite Sheet 规范：**

```
单帧尺寸:  16x32 pixels (宽x高，标准像素角色比例)
缩放倍率:  3x (渲染为 48x96 pixels)
Sheet 布局:

Row 0: idle (4 帧)          → 0-3
Row 1: walk_down (4 帧)     → 4-7
Row 2: walk_left (4 帧)     → 8-11
Row 3: walk_right (4 帧)    → 12-15
Row 4: walk_up (4 帧)       → 16-19
Row 5: think (4 帧)         → 20-23
Row 6: speak (4 帧)         → 24-27
Row 7: work (6 帧)          → 28-33
Row 8: complete (6 帧)      → 34-39
Row 9: error (4 帧)         → 40-43

Sheet 总尺寸:
- 每行最大 6 帧 -> 宽 = 6 * 16 = 96 pixels
- 共 10 行 -> 高 = 10 * 32 = 320 pixels
- 最终 Sheet: 96x320 pixels
```

**Tileset 规范：**

```
Tile 尺寸:  16x16 pixels
缩放倍率:   3x (渲染为 48x48 pixels)
颜色深度:   RGBA 32-bit PNG
抗锯齿:     关闭 (image-rendering: pixelated)
```

### 7.3 需要自制的最小素材清单

Modern Interiors 免费版涵盖了大部分办公室家具，但以下素材可能需要自制或额外寻找：

| 素材 | 原因 | 规格 | 自制难度 |
| --- | --- | --- | --- |
| 6 个 Agent 角色 sprite sheet | 需要差异化外观区分不同 Agent | 96x320px 每个 | 中等（可用 Aseprite 制作） |
| 大屏幕监控墙动画 | 免费版可能无动态显示器 | 48x32px，4 帧动画 | 低 |
| 公告栏/任务板 | 需要特殊功能标识 | 32x48px | 低 |
| 状态图标 | 完成/错误/思考等标记 | 8x8px 或 16x16px | 低 |
| 特效 sprite | 星星完成特效、错误叹号 | 16x16px，4-6 帧 | 低 |
| 对话气泡 9-slice | 可伸缩气泡框 | 24x24px 9-slice | 低 |

**角色差异化方案**：6 个 Agent 可以通过以下方式区分，不需要从零绘制 6 套完整角色：

1. **基础骨架共用** -- 使用同一个角色基础动画
2. **调色板替换 (Palette Swap)** -- 每个 Agent 使用不同配色（Phaser 支持 tint 着色）
3. **头饰/配件差异** -- 在基础角色上叠加不同帽子或配件 sprite
4. **名称标签颜色** -- 角色类型用不同颜色的名称标签区分

```typescript
// 调色板替换示例
const AGENT_TINTS: Record<string, number> = {
  orchestrator:      0xFFD700,  // 金色 -- 总指挥
  sales_coach:       0x4CAF50,  // 绿色 -- 生成型
  pitch_evaluator:   0x2196F3,  // 蓝色 -- 评估型
  price_intel:       0xFF9800,  // 橙色 -- 采集分析型
  risk_qa:           0xF44336,  // 红色 -- 审核型
  experiment_analyst: 0x9C27B0, // 紫色 -- 分析型
};

// 创建角色时应用 tint
sprite.setTint(AGENT_TINTS[agentSlug]);
```

### 7.4 推荐工具链

| 工具 | 用途 | 价格 |
| --- | --- | --- |
| **Aseprite** | 像素画编辑器，制作 sprite sheet | $19.99（或自行编译免费） |
| **Tiled Map Editor** | Tilemap 编辑 | 免费 |
| **TexturePacker** (Free tier) | Sprite sheet 打包优化 | 免费版够用 |
| **Piskel** (备选) | 在线像素画编辑器 | 免费 |

---

## 8. MVP 实现路线

### Step 1: 空办公室场景 + 静态角色（Week 1）

**目标**：浏览器打开能看到像素风格的办公室，6 个角色静态站在工位上。

**交付内容：**
- 前端项目初始化（Vite + React + Phaser + TypeScript）
- Phaser Game 配置 + Boot/Preload/Office 三个 Scene
- 使用 Tiled 绘制办公室地图（Ground + Walls + Furniture 图层）
- 加载 Modern Interiors tileset 渲染场景
- 6 个静态角色 sprite 放置在工位位置
- 角色播放 idle 动画
- 摄像机基础控制（拖拽平移、滚轮缩放）
- `pointer-events` 穿透设置和基本 HTML 结构

**验收标准：**
- `npm run dev` 启动后浏览器显示像素风办公室
- 6 个角色可见且有 idle 呼吸动画
- 可以拖拽和缩放查看场景

---

### Step 2: 点击交互 + React 面板通信（Week 2）

**目标**：点击角色弹出 React 配置面板，点击墙上显示器弹出成本面板。

**交付内容：**
- EventBus 通信机制实现
- Tiled Object Layer 交互热区加载
- 角色点击事件 -> `EventBus.emit('agent:clicked')`
- 物件点击事件 -> `EventBus.emit('object:clicked')`
- React PanelContainer 组件（拖拽、最小化、关闭）
- Agent 配置面板（连接后端 API 展示真实数据）
- 像素风 CSS 主题（面板边框、按钮、字体）
- 面板打开/关闭时 Phaser 交互的暂停/恢复
- 基本键盘快捷键（ESC 关闭面板）

**验收标准：**
- 点击角色弹出 Agent 配置面板，显示从 API 获取的真实数据
- 点击墙上显示器弹出成本监控面板
- 面板可拖拽移动、可最小化、可关闭
- 面板打开时鼠标点击不穿透到 Phaser 场景
- ESC 键可关闭最上层面板

---

### Step 3: WebSocket 连接 + 角色状态变化（Week 3）

**目标**：后端推送事件时，角色实时切换状态（think/work/speak）。

**交付内容：**
- WebSocketClient 实现（自动重连、心跳）
- WebSocket 事件 -> EventBus 分发
- AgentEventHandler 事件映射实现
- 角色状态切换：idle/think/speak/work/complete/error
- 头顶思考气泡和对话气泡
- 状态图标（完成 check / 错误 exclamation）
- React 事件日志面板（实时事件流滚动）
- React HUD 通知 toast（新事件提示）

**验收标准：**
- 通过后端 API 触发一个培训任务，WebSocket 推送事件到前端
- 对应 Agent 角色从 idle 切换到 think -> work -> complete
- 头顶出现思考气泡和完成特效
- 事件日志面板实时滚动更新
- WebSocket 断开后自动重连

---

### Step 4: 角色动画和交互（Week 4）

**目标**：角色可以移动，Agent 之间有协作交互动画。

**交付内容：**
- EasyStar.js 寻路集成
- 碰撞层从 Tiled 加载
- 角色四方向行走动画
- 动态 depth 排序（y 轴遮挡）
- InteractionSequencer 动画编排
- Orchestrator 分配任务 -> 走向目标 Agent -> 对话 -> 返回
- 角色完成任务后回到工位

**验收标准：**
- 发起比价任务后，Orchestrator 角色走到 PriceIntel 工位旁对话
- PriceIntel 开始工作动画
- 任务完成后 PriceIntel 播放完成特效
- 角色行走时正确避障
- 前后遮挡关系正确

---

### Step 5: 完整面板 + 数据可视化（Week 5）

**目标**：所有管理面板功能完整，图表展示。

**交付内容：**
- 成本监控面板：费用总览卡片、趋势折线图、Agent/模型排名条形图
- 任务中心面板：任务列表（筛选、分页）、任务详情时间线
- Agent 状态总览面板：6 个 Agent 状态卡片网格
- Agent 配置面板完善：模型参数修改、Skill 绑定/解绑、状态切换
- 像素风 Recharts 主题定制
- 所有面板连接后端 API 真实数据

**验收标准：**
- 成本监控展示近 7 天费用趋势图
- 任务中心可按状态/类型/Agent 筛选任务
- Agent 配置面板可以修改 temperature 参数并保存
- 数据图表使用像素风格配色

---

### Step 6: 打磨与优化（Week 6）

**目标**：视觉打磨、性能优化、用户体验完善。

**交付内容：**
- 像素风 UI 细节打磨（阴影、边框、渐变）
- 音效系统（点击、通知、完成音效）
- 迷你地图组件
- 角色头顶常驻状态标签（名称 + 类型颜色）
- 场景过渡动画（Boot -> Preload -> Office 淡入淡出）
- 性能优化：sprite 批处理、面板懒加载、WebSocket 消息节流
- 移动端适配基础：触摸拖拽、双指缩放
- 错误边界和加载状态处理

**验收标准：**
- 60fps 流畅运行（6 个角色 + 面板打开状态下）
- 触摸设备可以操作
- 加载过程有进度条反馈
- 无 JS 运行时错误

---

### 8.1 MVP 范围总结

**最小可用版本 (Step 1-3) 包含：**
1. 像素风办公室场景渲染
2. 6 个 Agent 角色（idle/think/speak/work/complete/error 状态切换）
3. 点击角色弹出配置面板
4. 点击物件弹出功能面板（成本、任务、事件日志）
5. WebSocket 实时事件驱动角色状态变化
6. 基本的面板 CRUD 操作

**完整版 (Step 4-6) 增加：**
7. A* 寻路和角色移动动画
8. Agent 之间的协作交互动画序列
9. 完整的数据可视化图表
10. 音效、迷你地图、过渡动画等体验优化

---

## 9. Phaser 场景代码结构

### 9.1 Game 配置

```typescript
// src/phaser/config.ts
import Phaser from 'phaser';
import { BootScene } from './scenes/BootScene';
import { PreloadScene } from './scenes/PreloadScene';
import { OfficeScene } from './scenes/OfficeScene';

export const gameConfig: Phaser.Types.Core.GameConfig = {
  type: Phaser.AUTO,  // 优先 WebGL，降级 Canvas
  width: window.innerWidth,
  height: window.innerHeight,
  pixelArt: true,     // 关键：禁用抗锯齿，保持像素清晰
  roundPixels: true,
  scale: {
    mode: Phaser.Scale.RESIZE,   // 响应窗口大小变化
    autoCenter: Phaser.Scale.CENTER_BOTH,
  },
  physics: {
    default: 'arcade',
    arcade: {
      gravity: { x: 0, y: 0 },  // 俯视视角无重力
      debug: false,
    },
  },
  scene: [BootScene, PreloadScene, OfficeScene],
  backgroundColor: '#1a1a2e',
};
```

### 9.2 主场景

```typescript
// src/phaser/scenes/OfficeScene.ts

import Phaser from 'phaser';
import { AgentManager } from '../systems/AgentManager';
import { PathfindingSystem } from '../systems/PathfindingSystem';
import { AgentEventHandler } from '../systems/EventHandler';
import { EventBus } from '../../shared/events/EventBus';

export class OfficeScene extends Phaser.Scene {
  private agentManager!: AgentManager;
  private pathfinding!: PathfindingSystem;
  private eventHandler!: AgentEventHandler;

  constructor() {
    super('OfficeScene');
  }

  create() {
    // 1. 加载 Tilemap
    const map = this.make.tilemap({ key: 'office-map' });
    const tileset = map.addTilesetImage('modern-interiors', 'tileset-interiors')!;

    // 2. 创建图层
    const groundLayer = map.createLayer('Ground', tileset)!;
    const wallsLayer = map.createLayer('Walls', tileset)!;
    const furnitureBelowLayer = map.createLayer('Furniture_Below', tileset)!;
    const furnitureAboveLayer = map.createLayer('Furniture_Above', tileset)!;

    // 设置图层深度
    groundLayer.setDepth(0);
    wallsLayer.setDepth(1);
    furnitureBelowLayer.setDepth(2);
    furnitureAboveLayer.setDepth(10);

    // 3. 碰撞层（不渲染，只用于寻路）
    const collisionLayer = map.createLayer('Collision', tileset);
    if (collisionLayer) {
      collisionLayer.setVisible(false);
      this.pathfinding = new PathfindingSystem(collisionLayer);
    }

    // 4. 初始化 Agent 管理器
    this.agentManager = new AgentManager(this, this.pathfinding);

    // 5. 从 Tiled Object Layer 读取出生点，创建 Agent 角色
    const spawnPoints = map.getObjectLayer('SpawnPoints');
    spawnPoints?.objects.forEach(obj => {
      const props = this.extractProperties(obj);
      if (props.type === 'agent_spawn') {
        this.agentManager.spawnAgent({
          agentId: props.agent_id,
          name: props.agent_name,
          slug: props.agent_slug,
          spriteKey: props.sprite_key || 'agent_default',
          homePosition: { x: obj.x!, y: obj.y! },
        });
      }
    });

    // 6. 加载交互热区
    this.loadInteractiveObjects(map);

    // 7. 初始化事件处理器（WebSocket 事件 -> 角色行为）
    this.eventHandler = new AgentEventHandler(this, this.agentManager);

    // 8. 摄像机设置
    const mapWidth = map.widthInPixels;
    const mapHeight = map.heightInPixels;
    this.cameras.main.setBounds(0, 0, mapWidth, mapHeight);
    this.cameras.main.setZoom(3); // 3x 缩放显示像素风格

    // 摄像机拖拽
    this.input.on('pointermove', (pointer: Phaser.Input.Pointer) => {
      if (pointer.isDown && pointer.button === 1) { // 中键拖拽
        this.cameras.main.scrollX -= (pointer.x - pointer.prevPosition.x) / this.cameras.main.zoom;
        this.cameras.main.scrollY -= (pointer.y - pointer.prevPosition.y) / this.cameras.main.zoom;
      }
    });

    // 滚轮缩放
    this.input.on('wheel', (
      _pointer: any, _gameObjects: any, _deltaX: number, deltaY: number
    ) => {
      const newZoom = Phaser.Math.Clamp(
        this.cameras.main.zoom - deltaY * 0.001,
        1, 5
      );
      this.cameras.main.setZoom(newZoom);
    });

    // 9. 通知 React 场景就绪
    EventBus.emit('scene:ready');
  }

  update(time: number, delta: number) {
    // 更新所有 Agent 角色
    this.agentManager.update(time, delta);
  }

  private loadInteractiveObjects(map: Phaser.Tilemaps.Tilemap) {
    const objectLayer = map.getObjectLayer('Objects');

    objectLayer?.objects.forEach(obj => {
      const props = this.extractProperties(obj);

      // 创建交互区域
      const zone = this.add.zone(
        obj.x! + obj.width! / 2,
        obj.y! + obj.height! / 2,
        obj.width!,
        obj.height!
      );
      zone.setInteractive({ useHandCursor: true });
      zone.setDepth(5); // 在家具上方以确保可点击

      // 悬停高亮效果
      const highlight = this.add.graphics();
      highlight.setDepth(4);
      highlight.setAlpha(0);

      zone.on('pointerover', () => {
        highlight.clear();
        highlight.fillStyle(0xffd700, 0.2);
        highlight.fillRect(obj.x!, obj.y!, obj.width!, obj.height!);
        highlight.setAlpha(1);
      });

      zone.on('pointerout', () => {
        highlight.setAlpha(0);
      });

      zone.on('pointerdown', () => {
        if (props.type === 'desk' && props.agent_id) {
          EventBus.emit('agent:clicked', { agentId: props.agent_id });
        } else if (props.panel) {
          EventBus.emit('object:clicked', { panel: props.panel });
        }
      });
    });
  }

  private extractProperties(obj: Phaser.Types.Tilemaps.TiledObject): Record<string, any> {
    const result: Record<string, any> = {};
    obj.properties?.forEach((p: any) => {
      result[p.name] = p.value;
    });
    return result;
  }
}
```

---

## 10. 性能优化策略

| 优化项 | 实现方式 | 预期效果 |
| --- | --- | --- |
| Phaser 渲染 | `pixelArt: true` + `roundPixels: true` 避免子像素渲染 | 更清晰 + 更少 GPU 计算 |
| Sprite 批处理 | 同一 texture atlas 的角色自动批处理 | 减少 draw call |
| React 面板懒加载 | 面板组件按需 `import()` | 减小初始 bundle |
| Phaser 分包 | Vite `manualChunks` 将 Phaser 独立分包 | 首屏加载不阻塞 |
| WebSocket 节流 | 对高频事件（如 move）做客户端节流（16ms/帧） | 避免过度更新 |
| Tilemap 裁剪 | Phaser 自动只渲染摄像机视口内的 tile | 大地图无性能问题 |
| 面板虚拟滚动 | 事件日志、任务列表使用虚拟列表 | 大数据量不卡顿 |
| 纹理图集 | 所有小图合并为 atlas，减少 HTTP 请求 | 加载更快 |
| 资源预加载 | PreloadScene 使用进度条加载所有资源 | 避免运行时卡顿 |

---

## 11. 补充说明

### 11.1 与后端 API 的对接约定

前端所有 API 请求走 `/api/v1/office/` 命名空间，WebSocket 连接 `/api/v1/office/ws/events`。

开发时 Vite dev server 通过 proxy 转发到 FastAPI（端口 8000），生产构建输出到 `app/static/office/`，由 FastAPI 直接 serve 静态文件。

### 11.2 Agent 元数据扩展

agents 表的 `metadata` JSONB 字段用于存储 RPG 可视化所需的配置：

```json
{
  "sprite_key": "orchestrator",
  "default_position": { "x": 160, "y": 200 },
  "tint_color": "0xFFD700",
  "desk_id": "desk_1",
  "personality_traits": ["leader", "analytical"]
}
```

### 11.3 后续扩展方向

- **多楼层/多房间**：通过 Phaser SceneManager 切换不同场景实现
- **自定义角色外观**：用户上传或选择 Agent 角色 sprite
- **实时语音气泡**：接入 TTS，Agent speak 事件播放语音
- **成就系统**：任务完成里程碑触发场景内特效
- **日夜循环**：根据真实时间切换办公室灯光
