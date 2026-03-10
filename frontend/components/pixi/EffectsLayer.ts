import { Container, Graphics, Ticker } from "pixi.js";

import { TickState } from "@/lib/replay/replayTypes";

type Particle = {
  g: Graphics;
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  maxLife: number;
};

type EffectsLayerConfig = {
  tileSize: number;
  townAnchor: { x: number; y: number };
  resourceAnchor: { x: number; y: number };
};

export class EffectsLayer {
  readonly container = new Container();
  private readonly particles: Particle[] = [];

  constructor(private readonly cfg: EffectsLayerConfig, ticker: Ticker) {
    ticker.add((delta) => this.onTick(delta.deltaTime));
  }

  emitForTransition(previousTick: TickState, nextTick: TickState) {
    for (const agent of nextTick.agents) {
      if (agent.action.harvestActual > 0.2) {
        this.spawnBurst(this.cfg.resourceAnchor, 0x8ddf76, Math.min(8, Math.ceil(agent.action.harvestActual * 1.5)));
      }
      if (agent.action.contribute > 0.2) {
        this.spawnTrail({ x: agent.x, y: agent.y }, this.cfg.townAnchor, 0x8ecbff, 6);
      }
      if (agent.action.reward > 0.05) {
        this.spawnTrail(this.cfg.townAnchor, { x: agent.x, y: agent.y }, 0xf7d669, 5);
      }
    }

    if (!previousTick.world.collapsed && nextTick.world.collapsed) {
      this.spawnBurst(
        { x: this.cfg.resourceAnchor.x, y: this.cfg.resourceAnchor.y },
        0xf16c6c,
        28,
        1.6
      );
    }
  }

  private toPx(point: { x: number; y: number }) {
    return { x: point.x * this.cfg.tileSize, y: point.y * this.cfg.tileSize };
  }

  private spawnBurst(originTile: { x: number; y: number }, color: number, count: number, speed = 1) {
    const origin = this.toPx(originTile);
    for (let i = 0; i < count; i += 1) {
      const angle = (Math.PI * 2 * i) / count + Math.random() * 0.4;
      const mag = (0.3 + Math.random() * 1.2) * speed;
      const g = new Graphics();
      g.rect(-1, -1, 2, 2).fill(color);
      g.position.set(origin.x, origin.y);
      this.container.addChild(g);
      this.particles.push({
        g,
        x: origin.x,
        y: origin.y,
        vx: Math.cos(angle) * mag,
        vy: Math.sin(angle) * mag,
        life: 1,
        maxLife: 1
      });
    }
  }

  private spawnTrail(fromTile: { x: number; y: number }, toTile: { x: number; y: number }, color: number, count: number) {
    const from = this.toPx(fromTile);
    const to = this.toPx(toTile);
    for (let i = 0; i < count; i += 1) {
      const k = i / Math.max(1, count - 1);
      const x = from.x + (to.x - from.x) * k;
      const y = from.y + (to.y - from.y) * k;
      const g = new Graphics();
      g.rect(-1, -1, 2, 2).fill(color);
      g.position.set(x, y);
      this.container.addChild(g);
      this.particles.push({
        g,
        x,
        y,
        vx: (Math.random() - 0.5) * 0.8,
        vy: (Math.random() - 0.5) * 0.8,
        life: 0.8,
        maxLife: 0.8
      });
    }
  }

  private onTick(deltaTime: number) {
    for (let i = this.particles.length - 1; i >= 0; i -= 1) {
      const p = this.particles[i];
      p.life -= 0.02 * deltaTime;
      p.x += p.vx * deltaTime;
      p.y += p.vy * deltaTime;
      p.vy += 0.002 * deltaTime;
      p.g.position.set(p.x, p.y);
      p.g.alpha = Math.max(0, p.life / p.maxLife);

      if (p.life <= 0) {
        p.g.destroy();
        this.particles.splice(i, 1);
      }
    }
  }
}
