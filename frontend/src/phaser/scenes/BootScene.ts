import Phaser from 'phaser';

export class BootScene extends Phaser.Scene {
  constructor() {
    super('BootScene');
  }

  preload() {
    // Boot 阶段只加载最基础的 loading UI 资源
    // 后续可在此加载 loading bar 素材
  }

  create() {
    this.scene.start('PreloadScene');
  }
}
