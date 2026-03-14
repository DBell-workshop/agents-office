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

  emit(event: string, ...args: any[]) {
    this.emitter.emit(event, ...args);
  }

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
