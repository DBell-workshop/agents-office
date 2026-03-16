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
      { x: 260, y: 230 },
      { x: 360, y: 230 },
      { x: 460, y: 230 },
      { x: 260, y: 310 },
      { x: 360, y: 310 },
      { x: 460, y: 310 },
    ],
  },
  // 调度中心（右上）— 调度员常驻，分配任务
  manager: {
    label: '__room.manager__',
    labelPos: { x: 840, y: 100 },
    entry: { x: 688, y: 270 },
    spots: [
      { x: 700, y: 180 },
      { x: 790, y: 180 },
      { x: 700, y: 250 },
      { x: 790, y: 250 },
      { x: 740, y: 215 },
      { x: 830, y: 215 },
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
    entry: { x: 850, y: 380 },
    spots: [
      { x: 760, y: 380 },
      { x: 850, y: 380 },
      { x: 940, y: 380 },
      { x: 760, y: 450 },
      { x: 850, y: 450 },
      { x: 940, y: 450 },
    ],
  },
  // 数据仓库（右侧下部）— 理货员常驻，管理商品数据
  datacenter: {
    label: '__room.datacenter__',
    labelPos: { x: 840, y: 600 },
    entry: { x: 848, y: 610 },
    spots: [
      { x: 760, y: 640 },
      { x: 850, y: 640 },
      { x: 940, y: 640 },
      { x: 760, y: 720 },
      { x: 850, y: 720 },
      { x: 940, y: 720 },
    ],
  },
};

// ============================================================
// 公共休闲点（POI）— Agent 空闲时可能去的地方
// ============================================================
interface POI {
  id: string;
  x: number;
  y: number;
  nearestCorridor: string;  // 最近的走廊节点
  action: 'drink' | 'sit' | 'look';  // 到达后的行为
  facingDir: Direction;  // 到达后朝向
}

const POIS: POI[] = [
  // 自动贩卖机（展示厅内）— 去买饮料
  { id: 'vending_showroom', x: 395, y: 230, nearestCorridor: 'SHOW_DOOR', action: 'drink', facingDir: 'up' },
  // 自动贩卖机（数据中心旁）— 去买饮料
  { id: 'vending_data', x: 1100, y: 700, nearestCorridor: 'DATA_AREA', action: 'drink', facingDir: 'up' },
  // 会议室中央大桌 — 去坐坐
  { id: 'meeting_table', x: 330, y: 650, nearestCorridor: 'MEET_DOOR', action: 'sit', facingDir: 'down' },
  // 展示厅展板前 — 看看东西
  { id: 'showroom_display', x: 250, y: 320, nearestCorridor: 'SHOW_DOOR', action: 'look', facingDir: 'left' },
  // 走廊中央 — 路过闲逛
  { id: 'corridor_center', x: 620, y: 430, nearestCorridor: 'COR_CENTER', action: 'look', facingDir: 'down' },
];

// ============================================================
// 状态目的地 — Agent 根据状态去不同位置
// ============================================================

/** 电脑工位 — working 状态目标（Agent 面朝上坐到电脑前） */
const DESK_SPOTS: { x: number; y: number; room: string }[] = [
  // workspace 工位区电脑（3台电脑，坐在椅子位置面朝上）
  { x: 992, y: 570, room: 'workspace' },
  { x: 1088, y: 570, room: 'workspace' },
  { x: 1184, y: 570, room: 'workspace' },
  { x: 1088, y: 480, room: 'workspace' },
  { x: 1184, y: 480, room: 'workspace' },
  // datacenter 数据中心电脑
  { x: 992, y: 830, room: 'datacenter' },
  { x: 1088, y: 830, room: 'datacenter' },
  { x: 1184, y: 830, room: 'datacenter' },
  // manager 调度中心
  { x: 960, y: 190, room: 'manager' },
];

/** 面壁角落 — error 状态目标（Agent 面朝墙壁） */
const SHAME_CORNERS: { x: number; y: number; room: string; facingDir: Direction }[] = [
  { x: 195, y: 175, room: 'showroom', facingDir: 'left' },     // 展示厅左上角
  { x: 750, y: 160, room: 'manager', facingDir: 'up' },        // 调度中心左上角
  { x: 195, y: 610, room: 'meeting', facingDir: 'left' },      // 会议室左上角
  { x: 810, y: 490, room: 'workspace', facingDir: 'up' },      // 工位区左上角
  { x: 810, y: 720, room: 'datacenter', facingDir: 'up' },     // 数据中心左上角
];

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

// 预定义的不重叠初始站位 — 全部在走廊正中央和房间中心开阔地带
const FIXED_SPAWN_POINTS: { x: number; y: number; room: string }[] = [
  { x: 720, y: 190, room: 'manager' },      // 1. 调度中心正中央
  { x: 350, y: 250, room: 'showroom' },      // 2. 展示厅正中央
  { x: 620, y: 370, room: 'workspace' },     // 3. 主走廊中段
  { x: 830, y: 400, room: 'workspace' },     // 4. 待命区中央
  { x: 810, y: 680, room: 'datacenter' },    // 5. 数据中心正中央
  { x: 620, y: 300, room: 'workspace' },     // 6. 主走廊上段
  { x: 620, y: 460, room: 'workspace' },     // 7. 主走廊下段
  { x: 350, y: 660, room: 'meeting' },       // 8. 协作室正中央
  { x: 920, y: 400, room: 'workspace' },     // 9. 待命区右侧开阔
  { x: 800, y: 190, room: 'manager' },       // 10. 调度中心右侧
  { x: 250, y: 250, room: 'showroom' },      // 11. 展示厅左侧
  { x: 720, y: 400, room: 'workspace' },     // 12. 走廊中间
  { x: 900, y: 680, room: 'datacenter' },    // 13. 数据中心右侧
  { x: 450, y: 660, room: 'meeting' },       // 14. 协作室右侧
  { x: 620, y: 250, room: 'workspace' },     // 15. 走廊最上段
  { x: 520, y: 370, room: 'workspace' },     // 16. 走廊左侧
  { x: 450, y: 250, room: 'showroom' },      // 17. 展示厅右侧
  { x: 720, y: 680, room: 'datacenter' },    // 18. 数据中心左侧
  { x: 520, y: 460, room: 'workspace' },     // 19. 走廊左下
  { x: 250, y: 660, room: 'meeting' },       // 20. 协作室左侧
];

const ROOM_KEYS = Object.keys(ROOMS);

function buildAgentSpawns() {
  return getAgentsCached().map((a, idx) => {
    const spawn = FIXED_SPAWN_POINTS[idx % FIXED_SPAWN_POINTS.length];
    return {
      agentId: a.phaserAgentId || `agt_${a.slug}`,
      name: a.displayName,
      slug: a.slug,
      spriteKey: getSpriteKey(a.slug),
      homeRoom: a.roomId || spawn.room,
      color: cssColorToHex(a.color),
      fixedSpawn: { x: spawn.x, y: spawn.y },
    };
  });
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

    // 1. 地图 — 用 sprites 渲染 Ground 层（而非 TileLayer），确保 depth 排序完全可控
    this.map = this.make.tilemap({ key: 'office-map' });
    const floorTS = this.map.addTilesetImage('FloorAndGround', 'tiles_wall')!;
    // 逐瓦片渲染 Ground，每个 tile 作为独立 sprite，depth 固定 -1000
    const groundData = this.map.getLayer('Ground');
    if (groundData) {
      const tw = this.map.tileWidth;
      const th = this.map.tileHeight;
      for (let row = 0; row < groundData.height; row++) {
        for (let col = 0; col < groundData.width; col++) {
          const tile = groundData.data[row][col];
          if (tile.index < 0) continue; // 空瓦片
          const frame = tile.index - floorTS.firstgid;
          if (frame < 0) continue;
          const s = this.add.sprite(col * tw + tw / 2, row * th + th / 2, 'tiles_wall', frame);
          s.setDepth(-1000);
        }
      }
    }

    // 2. Object layers — 全部使用固定低 depth，确保 Agent 永远在最上层
    this.addGroupFromTiled('Wall', 'tiles_wall', 'FloorAndGround', -500);
    this.addGroupFromTiled('Objects', 'office', 'Modern_Office_Black_Shadow', 1);
    this.addGroupFromTiled('ObjectsOnCollide', 'office', 'Modern_Office_Black_Shadow', 1);
    this.addGroupFromTiled('GenericObjects', 'generic', 'Generic', 1);
    this.addGroupFromTiled('GenericObjectsOnCollide', 'generic', 'Generic', 1);
    this.addGroupFromTiled('Basement', 'basement', 'Basement', -800);
    this.addGroupFromTiled('Chair', 'chairs', 'chair', 2);
    this.addGroupFromTiled('Computer', 'computers', 'computer', 2);
    this.addGroupFromTiled('Whiteboard', 'whiteboards', 'whiteboard', 2);
    this.addGroupFromTiled('VendingMachine', 'vendingmachines', 'vendingmachine', 2);

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
        agent.container.setDepth(agent.container.y + 10000);
      },
      onComplete: () => {
        this.moveAlongPath(agent, path, index + 1);
      },
    });
  }

  // ============================================================
  // 渲染
  // ============================================================
  private addGroupFromTiled(objectLayerName: string, key: string, tilesetName: string, fixedDepth?: number) {
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
      sprite.setDepth(fixedDepth ?? 1);
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
    this.agentSpawns.forEach((spawn) => {
      // 使用预定义的固定站位，不再从房间 spots 取
      const pos = (spawn as any).fixedSpawn || ROOMS[spawn.homeRoom]?.spots?.[0] || { x: 600, y: 400 };

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
      container.setDepth(pos.y + 10000);
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
      // 先走到电脑前，再开始工作动画
      this.moveAgentToDesk(agent, () => {
        this.startWorkingAnimation(agent);
      });
    } else if (data.status === 'error') {
      // 走到角落面壁
      this.moveAgentToShameCorner(agent);
    } else {
      // idle — 停止工作动画，回到房间
      this.stopWorkingAnimation(agent);
      if ((agent as any)._atShameCorner) {
        (agent as any)._atShameCorner = false;
        this.returnAgentHome(agent);
      }
    }
  }

  /** 走到最近的空闲电脑工位 */
  private moveAgentToDesk(agent: AgentCharacter, onArrived: () => void) {
    // 找同房间的工位，如果没有就找最近的
    const sameRoomDesks = DESK_SPOTS.filter(d => d.room === agent.currentRoom);
    const otherDesks = DESK_SPOTS.filter(d => d.room !== agent.currentRoom);
    const candidates = sameRoomDesks.length > 0 ? sameRoomDesks : otherDesks;

    if (candidates.length === 0) { onArrived(); return; }

    // 选一个最近的
    let closest = candidates[0];
    let minDist = Infinity;
    for (const desk of candidates) {
      const d = Math.sqrt((desk.x - agent.container.x) ** 2 + (desk.y - agent.container.y) ** 2);
      if (d < minDist) { minDist = d; closest = desk; }
    }

    // 如果已经在工位附近，直接开始工作
    if (minDist < 40) { onArrived(); return; }

    // 同房间直接走过去
    if (closest.room === agent.currentRoom) {
      agent.isMoving = true;
      this.moveAlongPathWithCallback(agent, [{ x: closest.x, y: closest.y }], 0, () => {
        agent.isMoving = false;
        onArrived();
      });
    } else {
      // 跨房间走过去
      const exitNode = ROOM_CORRIDOR[agent.currentRoom];
      const targetNode = ROOM_CORRIDOR[closest.room];
      if (!exitNode || !targetNode) { onArrived(); return; }

      const corridorPath = this.findCorridorPath(exitNode, targetNode);
      if (!corridorPath) { onArrived(); return; }

      const room = ROOMS[agent.currentRoom];
      const targetRoom = ROOMS[closest.room];
      const fullPath = [
        room.entry,
        ...corridorPath.map(id => {
          const node = CORRIDOR_NODES.find(n => n.id === id);
          return node ? { x: node.x, y: node.y } : room.entry;
        }),
        targetRoom.entry,
        { x: closest.x, y: closest.y },
      ];

      agent.isMoving = true;
      this.moveAlongPathWithCallback(agent, fullPath, 0, () => {
        agent.isMoving = false;
        agent.currentRoom = closest.room;
        onArrived();
      });
    }
  }

  /** 走到最近的面壁角落 */
  private moveAgentToShameCorner(agent: AgentCharacter) {
    this.stopWorkingAnimation(agent);

    // 找同房间的角落
    const sameRoom = SHAME_CORNERS.filter(c => c.room === agent.currentRoom);
    const corner = sameRoom.length > 0
      ? sameRoom[Math.floor(Math.random() * sameRoom.length)]
      : SHAME_CORNERS[Math.floor(Math.random() * SHAME_CORNERS.length)];

    const walkToCorner = () => {
      agent.isMoving = true;
      this.moveAlongPathWithCallback(agent, [{ x: corner.x, y: corner.y }], 0, () => {
        agent.isMoving = false;
        (agent as any)._atShameCorner = true;

        // 面朝墙壁
        agent.sprite.play(`${agent.spriteKey}-idle-${corner.facingDir}`);

        // 头顶显示错误气泡
        this.showAgentBubble(agent.slug, '🐛 ...', 5000);

        // 轻微抖动效果（表示沮丧）
        this.tweens.add({
          targets: agent.container,
          x: corner.x - 2,
          duration: 100,
          yoyo: true,
          repeat: 5,
          onComplete: () => {
            agent.container.x = corner.x;
          },
        });
      });
    };

    // 如果角落在不同房间，需要先走过去
    if (corner.room !== agent.currentRoom) {
      const exitNode = ROOM_CORRIDOR[agent.currentRoom];
      const targetNode = ROOM_CORRIDOR[corner.room];
      if (exitNode && targetNode) {
        const corridorPath = this.findCorridorPath(exitNode, targetNode);
        if (corridorPath) {
          const room = ROOMS[agent.currentRoom];
          const targetRoom = ROOMS[corner.room];
          const pathToRoom = [
            room.entry,
            ...corridorPath.map(id => {
              const node = CORRIDOR_NODES.find(n => n.id === id);
              return node ? { x: node.x, y: node.y } : room.entry;
            }),
            targetRoom.entry,
          ];
          agent.isMoving = true;
          this.moveAlongPathWithCallback(agent, pathToRoom, 0, () => {
            agent.isMoving = false;
            agent.currentRoom = corner.room;
            walkToCorner();
          });
          return;
        }
      }
    }
    walkToCorner();
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
      dot.setDepth(agent.container.y + 20000);

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
  // 空闲 Agent 随机走动 & 公共区域串门
  // ============================================================
  private idleWander() {
    this.agents.forEach((agent) => {
      if (agent.isMoving) return;
      if ((agent as any)._typingTimer) return; // 工作中不走动
      if ((agent as any)._wandering) return;   // 已在串门中

      // 25% 概率触发
      if (Math.random() > 0.25) return;

      // 15% 概率去公共区域串门，85% 在房间内闲逛
      if (Math.random() < 0.15) {
        this.wanderToPOI(agent);
      } else {
        this.wanderInRoom(agent);
      }
    });
  }

  /** 在当前房间内随机走动 */
  private wanderInRoom(agent: AgentCharacter) {
    const room = ROOMS[agent.currentRoom];
    if (!room) return;

    const randomSpot = room.spots[Math.floor(Math.random() * room.spots.length)];
    const dx = randomSpot.x - agent.container.x;
    const dy = randomSpot.y - agent.container.y;
    const distance = Math.sqrt(dx * dx + dy * dy);
    if (distance < 30) return;

    const dir = this.getDirection(dx, dy);
    agent.sprite.play(`${agent.spriteKey}-walk-${dir}`);
    agent.isMoving = true;

    this.tweens.add({
      targets: agent.container,
      x: randomSpot.x,
      y: randomSpot.y,
      duration: (distance / 60) * 1000,
      ease: 'Linear',
      onUpdate: () => { agent.container.setDepth(agent.container.y + 10000); },
      onComplete: () => {
        agent.isMoving = false;
        agent.sprite.play(`${agent.spriteKey}-idle-down`);
      },
    });
  }

  /** 去公共休闲点串门 — 走到 POI → 执行行为动画 → 回到自己房间 */
  private wanderToPOI(agent: AgentCharacter) {
    const poi = POIS[Math.floor(Math.random() * POIS.length)];
    (agent as any)._wandering = true;

    // 用走廊网络走到 POI
    const exitNode = ROOM_CORRIDOR[agent.currentRoom];
    if (!exitNode) { (agent as any)._wandering = false; return; }

    // 构建路径：当前位置 → 房间出口 → 走廊 → POI走廊 → POI
    const corridorPath = this.findCorridorPath(exitNode, poi.nearestCorridor);
    if (!corridorPath) { (agent as any)._wandering = false; return; }

    const room = ROOMS[agent.currentRoom];
    const fullPath = [
      room.entry,  // 走到房间门口
      ...corridorPath.map(id => {
        const node = CORRIDOR_NODES.find(n => n.id === id);
        return node ? { x: node.x, y: node.y } : room.entry;
      }),
      { x: poi.x, y: poi.y },  // 最终目的地
    ];

    // 走到 POI
    agent.isMoving = true;
    this.moveAlongPathWithCallback(agent, fullPath, 0, () => {
      // 到达 POI — 执行行为动画
      agent.isMoving = false;
      agent.sprite.play(`${agent.spriteKey}-idle-${poi.facingDir}`);

      // 行为效果
      if (poi.action === 'drink') {
        this.showAgentBubble(agent.slug, '☕', 2000);
      } else if (poi.action === 'sit') {
        this.showAgentBubble(agent.slug, '💤', 2500);
      }

      // 停留 3~6 秒后回家
      const stayTime = 3000 + Math.random() * 3000;
      this.time.delayedCall(stayTime, () => {
        this.returnAgentHome(agent);
      });
    });
  }

  /** 让 Agent 沿路径走动，走完执行回调 */
  private moveAlongPathWithCallback(
    agent: AgentCharacter,
    path: { x: number; y: number }[],
    index: number,
    onDone: () => void,
  ) {
    if (index >= path.length) {
      onDone();
      return;
    }
    const target = path[index];
    const dx = target.x - agent.container.x;
    const dy = target.y - agent.container.y;
    const distance = Math.sqrt(dx * dx + dy * dy);

    if (distance < 4) {
      this.moveAlongPathWithCallback(agent, path, index + 1, onDone);
      return;
    }

    const dir = this.getDirection(dx, dy);
    agent.sprite.play(`${agent.spriteKey}-walk-${dir}`);
    agent.isMoving = true;

    this.tweens.add({
      targets: agent.container,
      x: target.x,
      y: target.y,
      duration: (distance / 70) * 1000, // 70px/s 闲逛速度
      ease: 'Linear',
      onUpdate: () => { agent.container.setDepth(agent.container.y + 10000); },
      onComplete: () => {
        this.moveAlongPathWithCallback(agent, path, index + 1, onDone);
      },
    });
  }

  /** 从 spots 中选择一个没有其他 Agent 占用的位置 */
  private pickUnoccupiedSpot(
    spots: { x: number; y: number }[],
    excludeAgent: AgentCharacter,
  ): { x: number; y: number } {
    const occupied = new Set<number>();
    for (const other of this.agents) {
      if (other === excludeAgent || other.isMoving) continue;
      for (let i = 0; i < spots.length; i++) {
        const dist = Math.abs(other.container.x - spots[i].x) + Math.abs(other.container.y - spots[i].y);
        if (dist < 30) occupied.add(i);
      }
    }
    const free = spots.map((s, i) => i).filter(i => !occupied.has(i));
    const idx = free.length > 0
      ? free[Math.floor(Math.random() * free.length)]
      : Math.floor(Math.random() * spots.length);
    return spots[idx];
  }

  /** Agent 回到自己的房间 */
  private returnAgentHome(agent: AgentCharacter) {
    const homeRoom = ROOMS[agent.homeRoom];
    if (!homeRoom) { (agent as any)._wandering = false; return; }

    // 找回家路径
    const currentNearestCorridor = this.findNearestCorridorNode(agent.container.x, agent.container.y);
    const homeExit = ROOM_CORRIDOR[agent.homeRoom];
    const corridorPath = this.findCorridorPath(currentNearestCorridor, homeExit);

    const homeSpot = this.pickUnoccupiedSpot(homeRoom.spots, agent);
    const returnPath = [
      ...(corridorPath || []).map(id => {
        const node = CORRIDOR_NODES.find(n => n.id === id);
        return node ? { x: node.x, y: node.y } : homeRoom.entry;
      }),
      homeRoom.entry,
      homeSpot,
    ];

    agent.isMoving = true;
    this.moveAlongPathWithCallback(agent, returnPath, 0, () => {
      agent.isMoving = false;
      agent.currentRoom = agent.homeRoom;
      agent.sprite.play(`${agent.spriteKey}-idle-down`);
      (agent as any)._wandering = false;
    });
  }

  /** 找到离坐标最近的走廊节点 */
  private findNearestCorridorNode(x: number, y: number): string {
    let nearest = CORRIDOR_NODES[0].id;
    let minDist = Infinity;
    for (const node of CORRIDOR_NODES) {
      const d = Math.sqrt((node.x - x) ** 2 + (node.y - y) ** 2);
      if (d < minDist) { minDist = d; nearest = node.id; }
    }
    return nearest;
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
