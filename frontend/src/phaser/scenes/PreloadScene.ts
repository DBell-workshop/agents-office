import Phaser from 'phaser';

export class PreloadScene extends Phaser.Scene {
  private progressBar!: Phaser.GameObjects.Graphics;
  private progressBox!: Phaser.GameObjects.Graphics;
  private loadingText!: Phaser.GameObjects.Text;

  constructor() {
    super('PreloadScene');
  }

  preload() {
    const { width, height } = this.cameras.main;
    const centerX = width / 2;
    const centerY = height / 2;

    this.progressBox = this.add.graphics();
    this.progressBox.fillStyle(0x222222, 0.8);
    this.progressBox.fillRect(centerX - 160, centerY - 15, 320, 30);

    this.progressBar = this.add.graphics();

    this.loadingText = this.add.text(centerX, centerY - 40, 'Loading AgentsOffice...', {
      fontFamily: 'monospace',
      fontSize: '14px',
      color: '#e0e0e0',
    });
    this.loadingText.setOrigin(0.5);

    this.load.on('progress', (value: number) => {
      this.progressBar.clear();
      this.progressBar.fillStyle(0x4ade80, 1);
      this.progressBar.fillRect(centerX - 155, centerY - 10, 310 * value, 20);
    });

    this.load.on('complete', () => {
      this.progressBar.destroy();
      this.progressBox.destroy();
      this.loadingText.destroy();
    });

    // 地图 JSON
    this.load.tilemapTiledJSON('office-map', 'assets/tilemaps/office.json');

    // tileset 用 spritesheet 加载（object layer 需要 frame index）
    this.load.spritesheet('tiles_wall', 'assets/tilemaps/FloorAndGround.png', {
      frameWidth: 32,
      frameHeight: 32,
    });
    this.load.spritesheet('chairs', 'assets/tilemaps/chair.png', {
      frameWidth: 32,
      frameHeight: 64,
    });
    this.load.spritesheet('computers', 'assets/tilemaps/computer.png', {
      frameWidth: 96,
      frameHeight: 64,
    });
    this.load.spritesheet('whiteboards', 'assets/tilemaps/whiteboard.png', {
      frameWidth: 64,
      frameHeight: 64,
    });
    this.load.spritesheet('vendingmachines', 'assets/tilemaps/vendingmachine.png', {
      frameWidth: 48,
      frameHeight: 72,
    });
    this.load.spritesheet('office', 'assets/tilemaps/Modern_Office_Black_Shadow.png', {
      frameWidth: 32,
      frameHeight: 32,
    });
    this.load.spritesheet('basement', 'assets/tilemaps/Basement.png', {
      frameWidth: 32,
      frameHeight: 32,
    });
    this.load.spritesheet('generic', 'assets/tilemaps/Generic.png', {
      frameWidth: 32,
      frameHeight: 32,
    });

    // 6 个角色 spritesheet（32x64 帧 — 每个角色 2 格高）
    for (let i = 1; i <= 6; i++) {
      const key = `char_0${i}`;
      this.load.spritesheet(key, `assets/sprites/characters/${key}.png`, {
        frameWidth: 32,
        frameHeight: 64,
      });
    }
  }

  create() {
    this.scene.start('OfficeScene');
  }
}
