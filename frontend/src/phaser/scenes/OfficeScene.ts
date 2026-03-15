import Phaser from 'phaser';
import { EventBus } from '../../shared/events/EventBus';
import { getAgentsCached, getSpriteKey } from '../../shared/agentRegistry';
import { t } from '../../shared/i18n';

// LimeZu 32x64 frames: 56 cols x 20 rows
// Row 1: idle loop (24 frames: down 0-5, right 6-11, up 12-17, left 18-23)
// Row 2: walk (same layout)
const SPRITE_COLS = 56;

// ============================================================
// 房间定义 — 基于实际地图墙体分析
// ============================================================
// 地图尺寸: 40x30 tiles (1280x960 px)
// 水平墙线:
//   Y=288: X=640-1056 (门口 X=672-704)  → 经理室南墙
//   Y=352: X=192-608  (门口 X=384-416)  → 展示厅南墙
//   Y=512: X=192-640  (门口 X=384-416)  → 会议室北墙
// 右侧 X>640 区域为开放空间（工位区+数据中心）

const ROOMS: Record<
  string,
  {
    label: string;
    labelPos: { x: number; y: number };
    entry: { x: number; y: number };
    spots: { x: number; y: number }[];
  }
> = {
  // 商品展厅（左上）— 导购员常驻，向客户推荐商品
  showroom: {
    label: '__room.showroom__',
    labelPos: { x: 330, y: 120 },
    entry: { x: 400, y: 365 },
    spots: [
      { x: 265, y: 200 },
      { x: 365, y: 200 },
      { x: 465, y: 200 },
      { x: 265, y: 280 },
      { x: 365, y: 280 },
      { x: 465, y: 280 },
    ],
  },
  // 调度中心（右上）— 调度员常驻，分配任务
  manager: {
    label: '__room.manager__',
    labelPos: { x: 840, y: 100 },
    entry: { x: 688, y: 270 },
    spots: [
      { x: 765, y: 160 },
      { x: 865, y: 160 },
      { x: 965, y: 160 },
      { x: 765, y: 240 },
      { x: 865, y: 240 },
      { x: 965, y: 240 },
    ],
  },
  // 协作室（左下）— 多 Agent 协同讨论
  meeting: {
    label: '__room.meeting__',
    labelPos: { x: 330, y: 540 },
    entry: { x: 400, y: 525 },
    spots: [
      { x: 265, y: 620 },
      { x: 365, y: 620 },
      { x: 465, y: 620 },
      { x: 265, y: 720 },
      { x: 365, y: 720 },
      { x: 465, y: 720 },
    ],
  },
  // 待命区（右侧中部）— 待命 Agent 就绪等待
  workspace: {
    label: '__room.workspace__',
    labelPos: { x: 840, y: 340 },
    entry: { x: 850, y: 430 },
    spots: [
      { x: 825, y: 500 },
      { x: 920, y: 500 },
      { x: 1005, y: 500 },
      { x: 825, y: 580 },
      { x: 920, y: 580 },
      { x: 1005, y: 580 },
    ],
  },
  // 数据仓库（右侧下部）— 理货员常驻，管理商品数据
  datacenter: {
    label: '__room.datacenter__',
    labelPos: { x: 840, y: 650 },
    entry: { x: 848, y: 660 },
    spots: [
      { x: 810, y: 730 },
      { x: 900, y: 730 },
      { x: 985, y: 730 },
      { x: 810, y: 830 },
      { x: 900, y: 830 },
      { x: 985, y: 830 },
    ],
  },
};

// ============================================================
// 走廊节点网络 — 基于实际墙体门口位置
// ============================================================
const CORRIDOR_NODES: { x: number; y: number; id: string }[] = [
  // 展示厅门口（Y=352 墙体间隙 X=384-416 正下方）
  { x: 400, y: 365, id: 'SHOW_DOOR' },
  // 左侧走廊中心（Y=352 与 Y=512 两道墙之间）
  { x: 400, y: 430, id: 'COR_LEFT' },
  // 会议室门口（Y=512 墙体间隙 X=384-416 正上方）
  { x: 400, y: 500, id: 'MEET_DOOR' },
  // 中心节点（左侧走廊与右侧开放区交汇处）
  { x: 620, y: 430, id: 'COR_CENTER' },
  // 上方转角（通往经理室门口）
  { x: 670, y: 300, id: 'COR_UPPER' },
  // 经理室门口（Y=288 墙体间隙 X=672-704）
  { x: 688, y: 270, id: 'MGR_DOOR' },
  // 右侧走廊（进入工位区/数据中心）
  { x: 850, y: 430, id: 'COR_RIGHT' },
  // 工位区内部
  { x: 900, y: 550, id: 'WORK_AREA' },
  // 数据仓库门口（Y=608-640 墙体间隙 X=832-864）
  { x: 848, y: 624, id: 'DATA_DOOR' },
  // 数据仓库内部
  { x: 900, y: 750, id: 'DATA_AREA' },
];

const CORRIDOR_EDGES: [string, string][] = [
  ['SHOW_DOOR', 'COR_LEFT'],
  ['COR_LEFT', 'MEET_DOOR'],
  ['COR_LEFT', 'COR_CENTER'],
  ['COR_CENTER', 'COR_UPPER'],
  ['COR_UPPER', 'MGR_DOOR'],
  ['COR_CENTER', 'COR_RIGHT'],
  ['COR_RIGHT', 'WORK_AREA'],
  ['WORK_AREA', 'DATA_DOOR'],
  ['DATA_DOOR', 'DATA_AREA'],
];

// 房间出口对应的走廊节点
const ROOM_CORRIDOR: Record<string, string> = {
  showroom: 'SHOW_DOOR',
  manager: 'MGR_DOOR',
  meeting: 'MEET_DOOR',
  workspace: 'COR_RIGHT',
  datacenter: 'DATA_DOOR',
};

type Direction = 'down' | 'right' | 'up' | 'left';

// ============================================================
// Agent 配置 — 从 agentRegistry 动态构建
// ============================================================
function cssColorToHex(css: string): number {
  return parseInt(css.replace('#', ''), 16);
}

function buildAgentSpawns() {
  return getAgentsCached().map((a) => ({
    agentId: a.phaserAgentId || `agt_${a.slug}`,
    name: a.displayName,
    slug: a.slug,
    spriteKey: getSpriteKey(a.slug),
    homeRoom: a.roomId || 'workspace',
    color: cssColorToHex(a.color),
  }));
}

interface AgentCharacter {
  container: Phaser.GameObjects.Container;
  sprite: Phaser.GameObjects.Sprite;
  nameTag: Phaser.GameObjects.Text;
  agentId: string;
  slug: string;
  spriteKey: string;
  color: number;
  isMoving: boolean;
  homeRoom: string;
  currentRoom: string;
  bubbleContainer?: Phaser.GameObjects.Container;
  bubbleTimer?: Phaser.Time.TimerEvent;
}

export class OfficeScene extends Phaser.Scene {
  private agents: AgentCharacter[] = [];
  private agentSpawns: ReturnType<typeof buildAgentSpawns> = [];
  private map!: Phaser.Tilemaps.Tilemap;
  private corridorGraph: Map<string, string[]> = new Map();

  constructor() {
    super('OfficeScene');
  }

  create() {
    this.agentSpawns = buildAgentSpawns();
    this.buildCorridorGraph();

    // 1. 地图
    this.map = this.make.tilemap({ key: 'office-map' });
    const floorTS = this.map.addTilesetImage('FloorAndGround', 'tiles_wall')!;
    const groundLayer = this.map.createLayer('Ground', floorTS);
    if (groundLayer) groundLayer.setDepth(0);

    // 2. Object layers
    this.addGroupFromTiled('Wall', 'tiles_wall', 'FloorAndGround');
    this.addGroupFromTiled('Objects', 'office', 'Modern_Office_Black_Shadow');
    this.addGroupFromTiled('ObjectsOnCollide', 'office', 'Modern_Office_Black_Shadow');
    this.addGroupFromTiled('GenericObjects', 'generic', 'Generic');
    this.addGroupFromTiled('GenericObjectsOnCollide', 'generic', 'Generic');
    this.addGroupFromTiled('Basement', 'basement', 'Basement');
    this.addGroupFromTiled('Chair', 'chairs', 'chair');
    this.addGroupFromTiled('Computer', 'computers', 'computer');
    this.addGroupFromTiled('Whiteboard', 'whiteboards', 'whiteboard');
    this.addGroupFromTiled('VendingMachine', 'vendingmachines', 'vendingmachine');

    // 3. 房间名称标签
    this.createRoomLabels();

    // 4. 角色
    this.createAnimations();
    this.createAgents();

    // 5. 摄像机 — 自适应缩放 + 拖拽/滚轮平移
    const mapWidth = this.map.widthInPixels;
    const mapHeight = this.map.heightInPixels;
    const chatBoxWidth = 520; // ChatBox 占据右侧宽度（含 Agent 列表侧栏）
    const cam = this.cameras.main;

    // 将相机视口限定在 ChatBox 左侧区域，地图自然居中
    const vpWidth = this.scale.width - chatBoxWidth;
    const vpHeight = this.scale.height;
    cam.setViewport(0, 0, vpWidth, vpHeight);

    // 计算刚好能显示全部地图的缩放比例（留5%边距）
    const fitZoom = Math.min(vpWidth / mapWidth, vpHeight / mapHeight) * 0.95;
    const initialZoom = Math.max(fitZoom, 0.5);

    cam.setBounds(-200, -200, mapWidth + 400, mapHeight + 400);
    // 底部 Agent 信息卡遮挡地图，相机中心下移 80px 补偿
    cam.centerOn(mapWidth / 2 + 20, mapHeight / 2 + 80);
    cam.setZoom(initialZoom);

    // 鼠标拖拽平移
    this.input.on('pointermove', (pointer: Phaser.Input.Pointer) => {
      if (pointer.isDown) {
        this.cameras.main.scrollX -= (pointer.x - pointer.prevPosition.x) / this.cameras.main.zoom;
        this.cameras.main.scrollY -= (pointer.y - pointer.prevPosition.y) / this.cameras.main.zoom;
      }
    });

    // 滚轮/触控板手势
    // macOS 触控板: 双指滑动 = wheel(deltaX, deltaY)，捏合缩放 = wheel(ctrlKey=true)
    this.scale.canvas.addEventListener('wheel', (e: WheelEvent) => {
      e.preventDefault();
      if (e.ctrlKey || e.metaKey) {
        // 捏合缩放（ctrlKey 是 macOS 触控板 pinch 的标志）
        const newZoom = Phaser.Math.Clamp(
          this.cameras.main.zoom - e.deltaY * 0.005, 0.4, 4,
        );
        this.cameras.main.setZoom(newZoom);
      } else {
        // 双指滑动 → 平移地图
        this.cameras.main.scrollX += e.deltaX / this.cameras.main.zoom;
        this.cameras.main.scrollY += e.deltaY / this.cameras.main.zoom;
      }
    }, { passive: false });

    this.input.mouse?.disableContextMenu();

    // 6. 监听聊天事件驱动 Agent 移动 & 对话气泡 & 状态
    EventBus.on('chat:agent-move', this.onChatAgentMove, this);
    EventBus.on('chat:agent-bubble', this.onAgentBubble, this);
    EventBus.on('agent:status', this.onAgentStatusChange, this);

    // 7. 空闲 Agent 随机走动
    this.time.addEvent({
      delay: 5000,
      loop: true,
      callback: this.idleWander,
      callbackScope: this,
    });

    EventBus.emit('scene:ready');
  }

  // ============================================================
  // 聊天事件 → Agent 地图移动 & 对话气泡
  // ============================================================
  private onChatAgentMove(data: { agentId: string; roomId: string }) {
    this.moveAgentToRoom(data.agentId, data.roomId);
  }

  private onAgentBubble(data: { agentSlug: string; text: string; duration?: number }) {
    this.showAgentBubble(data.agentSlug, data.text, data.duration);
  }

  // ============================================================
  // 房间名称标签
  // ============================================================
  private createRoomLabels() {
    for (const [_key, room] of Object.entries(ROOMS)) {
      // 解析 i18n key: "__room.xxx__" → t('room.xxx')
      const labelText = room.label.startsWith('__') && room.label.endsWith('__')
        ? t(room.label.slice(2, -2))
        : room.label;
      const label = this.add.text(room.labelPos.x, room.labelPos.y, labelText, {
        fontFamily: 'monospace',
        fontSize: '14px',
        color: '#ffd700',
        stroke: '#000000',
        strokeThickness: 4,
        align: 'center',
      });
      label.setOrigin(0.5);
      label.setAlpha(0.85);
      label.setDepth(10000);
    }
  }

  // ============================================================
  // 走廊图 + BFS 寻路
  // ============================================================
  private buildCorridorGraph() {
    for (const node of CORRIDOR_NODES) {
      this.corridorGraph.set(node.id, []);
    }
    for (const [a, b] of CORRIDOR_EDGES) {
      this.corridorGraph.get(a)!.push(b);
      this.corridorGraph.get(b)!.push(a);
    }
  }

  private findCorridorPath(fromId: string, toId: string): string[] {
    if (fromId === toId) return [fromId];

    const visited = new Set<string>();
    const queue: string[][] = [[fromId]];
    visited.add(fromId);

    while (queue.length > 0) {
      const path = queue.shift()!;
      const current = path[path.length - 1];

      for (const neighbor of this.corridorGraph.get(current) || []) {
        if (neighbor === toId) return [...path, neighbor];
        if (!visited.has(neighbor)) {
          visited.add(neighbor);
          queue.push([...path, neighbor]);
        }
      }
    }
    return [fromId, toId]; // fallback
  }

  private getNodePos(nodeId: string): { x: number; y: number } {
    const node = CORRIDOR_NODES.find((n) => n.id === nodeId)!;
    return { x: node.x, y: node.y };
  }

  // ============================================================
  // 公开 API：移动 Agent 到指定房间
  // ============================================================
  public moveAgentToRoom(agentId: string, roomId: string) {
    const agent = this.agents.find((a) => a.agentId === agentId);
    if (!agent || agent.isMoving) return;

    const targetRoom = ROOMS[roomId];
    if (!targetRoom) return;

    const fromRoom = agent.currentRoom;
    const fullPath: { x: number; y: number }[] = [];

    if (fromRoom === roomId) {
      // 同房间 — 直接走到新站位
      const usedSpots = this.agents
        .filter((a) => a.currentRoom === roomId && a.agentId !== agentId)
        .length;
      const spotIndex = usedSpots % targetRoom.spots.length;
      fullPath.push(targetRoom.spots[spotIndex]);
    } else {
      const fromCorridorId = ROOM_CORRIDOR[fromRoom];
      const toCorridorId = ROOM_CORRIDOR[roomId];
      if (!fromCorridorId || !toCorridorId) return;

      // 1) 先走到当前房间的门口（不会穿墙）
      const fromRoomData = ROOMS[fromRoom];
      if (fromRoomData) {
        fullPath.push(fromRoomData.entry);
      }

      // 2) 走廊 BFS 寻路（节点都在走廊/门口，不穿墙）
      const corridorPath = this.findCorridorPath(fromCorridorId, toCorridorId);
      for (const nodeId of corridorPath) {
        fullPath.push(this.getNodePos(nodeId));
      }

      // 3) 进入目标房间
      fullPath.push(targetRoom.entry);

      // 4) 走到站位
      const usedSpots = this.agents
        .filter((a) => a.currentRoom === roomId && a.agentId !== agentId)
        .length;
      const spotIndex = usedSpots % targetRoom.spots.length;
      fullPath.push(targetRoom.spots[spotIndex]);
    }

    // 去除连续重复/极近的路径点（entry ≈ corridor node 时）
    const cleanPath: { x: number; y: number }[] = [fullPath[0]];
    for (let i = 1; i < fullPath.length; i++) {
      const prev = cleanPath[cleanPath.length - 1];
      const curr = fullPath[i];
      if (Math.abs(curr.x - prev.x) > 4 || Math.abs(curr.y - prev.y) > 4) {
        cleanPath.push(curr);
      }
    }

    agent.currentRoom = roomId;
    this.moveAlongPath(agent, cleanPath, 0);
  }

  private moveAlongPath(agent: AgentCharacter, path: { x: number; y: number }[], index: number) {
    if (index >= path.length) {
      agent.isMoving = false;
      agent.sprite.play(`${agent.spriteKey}-idle-down`);
      return;
    }

    const target = path[index];
    const dx = target.x - agent.container.x;
    const dy = target.y - agent.container.y;
    const distance = Math.sqrt(dx * dx + dy * dy);

    if (distance < 4) {
      this.moveAlongPath(agent, path, index + 1);
      return;
    }

    const dir = this.getDirection(dx, dy);
    agent.sprite.play(`${agent.spriteKey}-walk-${dir}`);
    agent.isMoving = true;

    const duration = (distance / 80) * 1000; // 80px/s

    this.tweens.add({
      targets: agent.container,
      x: target.x,
      y: target.y,
      duration,
      ease: 'Linear',
      onUpdate: () => {
        agent.container.setDepth(agent.container.y);
      },
      onComplete: () => {
        this.moveAlongPath(agent, path, index + 1);
      },
    });
  }

  // ============================================================
  // 渲染
  // ============================================================
  private addGroupFromTiled(objectLayerName: string, key: string, tilesetName: string) {
    const objectLayer = this.map.getObjectLayer(objectLayerName);
    if (!objectLayer) return;

    const tileset = this.map.getTileset(tilesetName);
    if (!tileset) return;

    objectLayer.objects.forEach((object) => {
      if (object.gid === undefined) return;

      const FLIPPED_H = 0x80000000;
      const FLIPPED_V = 0x40000000;
      const FLIPPED_D = 0x20000000;
      const cleanGid = object.gid & ~(FLIPPED_H | FLIPPED_V | FLIPPED_D);
      const flipH = (object.gid & FLIPPED_H) !== 0;

      const frameIndex = cleanGid - tileset.firstgid;
      const actualX = (object.x || 0) + (object.width || 0) * 0.5;
      const actualY = (object.y || 0) - (object.height || 0) * 0.5;

      const sprite = this.add.sprite(actualX, actualY, key, frameIndex);
      sprite.setDepth(actualY);
      if (flipH) sprite.setFlipX(true);
    });
  }

  private createAnimations() {
    this.agentSpawns.forEach((spawn) => {
      const key = spawn.spriteKey;
      const dirs: { dir: Direction; colStart: number }[] = [
        { dir: 'down', colStart: 0 },
        { dir: 'right', colStart: 6 },
        { dir: 'up', colStart: 12 },
        { dir: 'left', colStart: 18 },
      ];

      dirs.forEach(({ dir, colStart }) => {
        const idleKey = `${key}-idle-${dir}`;
        if (!this.anims.exists(idleKey)) {
          const frames: Phaser.Types.Animations.AnimationFrame[] = [];
          for (let i = 0; i < 6; i++) {
            frames.push({ key, frame: 1 * SPRITE_COLS + colStart + i });
          }
          this.anims.create({ key: idleKey, frames, frameRate: 6, repeat: -1 });
        }

        const walkKey = `${key}-walk-${dir}`;
        if (!this.anims.exists(walkKey)) {
          const frames: Phaser.Types.Animations.AnimationFrame[] = [];
          for (let i = 0; i < 6; i++) {
            frames.push({ key, frame: 2 * SPRITE_COLS + colStart + i });
          }
          this.anims.create({ key: walkKey, frames, frameRate: 10, repeat: -1 });
        }
      });
    });
  }

  private createAgents() {
    // 按房间追踪已分配的站位数量
    const roomSpotCounter: Record<string, number> = {};

    this.agentSpawns.forEach((spawn) => {
      const room = ROOMS[spawn.homeRoom];
      const usedCount = roomSpotCounter[spawn.homeRoom] || 0;
      const spotIndex = usedCount % room.spots.length;
      roomSpotCounter[spawn.homeRoom] = usedCount + 1;
      const pos = room.spots[spotIndex];

      const sprite = this.add.sprite(0, 0, spawn.spriteKey);
      sprite.play(`${spawn.spriteKey}-idle-down`);

      const nameTag = this.add.text(0, -42, spawn.name, {
        fontFamily: 'monospace',
        fontSize: '13px',
        color: '#ffffff',
        stroke: '#000000',
        strokeThickness: 3,
        shadow: { offsetX: 1, offsetY: 1, color: '#000', blur: 2, fill: true },
      });
      nameTag.setOrigin(0.5);

      const container = this.add.container(pos.x, pos.y, [sprite, nameTag]);
      container.setDepth(pos.y);
      container.setSize(32, 64);
      container.setInteractive({ useHandCursor: true });

      container.on('pointerdown', () => {
        EventBus.emit('agent:clicked', { agentId: spawn.agentId, name: spawn.name });
      });
      container.on('pointerover', () => sprite.setTint(0xffd700));
      container.on('pointerout', () => sprite.clearTint());

      this.agents.push({
        container,
        sprite,
        nameTag,
        agentId: spawn.agentId,
        slug: spawn.slug,
        spriteKey: spawn.spriteKey,
        color: spawn.color,
        isMoving: false,
        homeRoom: spawn.homeRoom,
        currentRoom: spawn.homeRoom,
      });
    });
  }

  private getDirection(dx: number, dy: number): Direction {
    if (Math.abs(dx) > Math.abs(dy)) {
      return dx > 0 ? 'right' : 'left';
    }
    return dy > 0 ? 'down' : 'up';
  }

  // ============================================================
  // Agent 对话气泡
  // ============================================================
  public showAgentBubble(agentSlug: string, text: string, duration = 4000) {
    const agent = this.agents.find((a) => a.slug === agentSlug);
    if (!agent) return;

    // 移除已有气泡
    this.hideAgentBubble(agent);

    // 截断文本
    const displayText = text.length > 40 ? text.slice(0, 37) + '...' : text;

    // 创建文字（先测量尺寸）
    const bubbleText = this.add.text(0, 0, displayText, {
      fontFamily: 'monospace',
      fontSize: '14px',
      color: '#ffe',
      fontStyle: 'bold',
      wordWrap: { width: 180 },
      lineSpacing: 4,
      stroke: '#000',
      strokeThickness: 1,
    });
    bubbleText.setOrigin(0.5);

    const padX = 12;
    const padY = 8;
    const tailH = 7;
    const bgW = bubbleText.width + padX * 2;
    const bgH = bubbleText.height + padY * 2;

    // 绘制气泡背景
    const gfx = this.add.graphics();

    // 填充 — 更不透明
    gfx.fillStyle(0x0a0a1e, 0.95);
    gfx.fillRoundedRect(-bgW / 2, -bgH, bgW, bgH, 4);

    // 边框（Agent 专属颜色）— 更粗更亮
    gfx.lineStyle(2, agent.color, 0.9);
    gfx.strokeRoundedRect(-bgW / 2, -bgH, bgW, bgH, 4);

    // 小三角尾巴
    gfx.fillStyle(0x0a0a1e, 0.95);
    gfx.fillTriangle(-5, 0, 5, 0, 0, tailH);

    // 文字居中在背景内
    bubbleText.setPosition(0, -bgH / 2);

    // 气泡容器 — 放在名字标签上方
    const bubbleContainer = this.add.container(0, -62, [gfx, bubbleText]);
    bubbleContainer.setAlpha(0);

    // 加入 Agent 容器
    agent.container.add(bubbleContainer);
    agent.bubbleContainer = bubbleContainer;

    // 淡入
    this.tweens.add({
      targets: bubbleContainer,
      alpha: 1,
      duration: 200,
    });

    // 定时淡出消失
    agent.bubbleTimer = this.time.delayedCall(duration, () => {
      this.fadeOutBubble(agent);
    });
  }

  private fadeOutBubble(agent: AgentCharacter) {
    if (!agent.bubbleContainer) return;
    const bc = agent.bubbleContainer;
    this.tweens.add({
      targets: bc,
      alpha: 0,
      duration: 300,
      onComplete: () => {
        bc.destroy();
        agent.bubbleContainer = undefined;
      },
    });
  }

  private hideAgentBubble(agent: AgentCharacter) {
    if (agent.bubbleTimer) {
      agent.bubbleTimer.destroy();
      agent.bubbleTimer = undefined;
    }
    if (agent.bubbleContainer) {
      agent.bubbleContainer.destroy();
      agent.bubbleContainer = undefined;
    }
  }

  // ============================================================
  // Agent 状态动画
  // ============================================================
  private onAgentStatusChange(data: { agentSlug: string; status: string }) {
    const agent = this.agents.find((a) => a.slug === data.agentSlug);
    if (!agent) return;

    if (data.status === 'working' || data.status === 'running') {
      this.startWorkingAnimation(agent);
    } else {
      this.stopWorkingAnimation(agent);
    }
  }

  private startWorkingAnimation(agent: AgentCharacter) {
    // 面朝上（朝电脑方向）播放 idle 动画
    agent.sprite.play(`${agent.spriteKey}-idle-up`);

    // 添加打字粒子效果（小方块从头顶飘出）
    if ((agent as any)._typingTimer) return; // 已经在工作了

    const typingEmitter = () => {
      if (agent.isMoving) return;
      const colors = [0xffd700, 0x4ade80, 0x60a5fa, 0xf97316];
      const color = colors[Math.floor(Math.random() * colors.length)];
      const offsetX = (Math.random() - 0.5) * 20;

      const dot = this.add.rectangle(
        agent.container.x + offsetX,
        agent.container.y - 50,
        4, 4, color, 0.9,
      );
      dot.setDepth(agent.container.y + 1000);

      this.tweens.add({
        targets: dot,
        y: dot.y - 20 - Math.random() * 15,
        alpha: 0,
        duration: 600 + Math.random() * 400,
        ease: 'Quad.easeOut',
        onComplete: () => dot.destroy(),
      });
    };

    // 立即发射一次，然后每400ms发射
    typingEmitter();
    (agent as any)._typingTimer = this.time.addEvent({
      delay: 400,
      loop: true,
      callback: typingEmitter,
    });

    // Agent 轻微上下晃动（模拟敲键盘）
    if (!(agent as any)._bounceTween) {
      (agent as any)._bounceTween = this.tweens.add({
        targets: agent.sprite,
        y: -2,
        duration: 300,
        yoyo: true,
        repeat: -1,
        ease: 'Sine.easeInOut',
      });
    }
  }

  private stopWorkingAnimation(agent: AgentCharacter) {
    // 停止打字粒子
    if ((agent as any)._typingTimer) {
      (agent as any)._typingTimer.destroy();
      (agent as any)._typingTimer = undefined;
    }

    // 停止晃动
    if ((agent as any)._bounceTween) {
      (agent as any)._bounceTween.stop();
      (agent as any)._bounceTween = undefined;
      agent.sprite.y = 0;
    }

    // 恢复正面 idle 动画
    if (!agent.isMoving) {
      agent.sprite.play(`${agent.spriteKey}-idle-down`);
    }
  }

  // ============================================================
  // 空闲 Agent 随机走动
  // ============================================================
  private idleWander() {
    this.agents.forEach((agent) => {
      // 正在移动或工作中的 Agent 不走动
      if (agent.isMoving) return;
      if ((agent as any)._typingTimer) return;

      // 30% 概率触发走动
      if (Math.random() > 0.3) return;

      const room = ROOMS[agent.currentRoom];
      if (!room) return;

      // 在当前房间内随机选一个站位
      const randomSpot = room.spots[Math.floor(Math.random() * room.spots.length)];
      const dx = randomSpot.x - agent.container.x;
      const dy = randomSpot.y - agent.container.y;
      const distance = Math.sqrt(dx * dx + dy * dy);

      // 太近就不走了
      if (distance < 30) return;

      const dir = this.getDirection(dx, dy);
      agent.sprite.play(`${agent.spriteKey}-walk-${dir}`);
      agent.isMoving = true;

      this.tweens.add({
        targets: agent.container,
        x: randomSpot.x,
        y: randomSpot.y,
        duration: (distance / 60) * 1000, // 60px/s 慢速闲逛
        ease: 'Linear',
        onUpdate: () => {
          agent.container.setDepth(agent.container.y);
        },
        onComplete: () => {
          agent.isMoving = false;
          agent.sprite.play(`${agent.spriteKey}-idle-down`);
        },
      });
    });
  }

  shutdown() {
    EventBus.off('chat:agent-move', this.onChatAgentMove, this);
    EventBus.off('chat:agent-bubble', this.onAgentBubble, this);
    EventBus.off('agent:status', this.onAgentStatusChange, this);
  }

  update(_time: number, _delta: number) {
    // WebSocket 事件驱动（未来）
  }
}
