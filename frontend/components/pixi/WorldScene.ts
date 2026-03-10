import { Application, Container } from "pixi.js";

import { TickState } from "@/lib/replay/replayTypes";

import { AgentLayer } from "./AgentLayer";
import { EffectsLayer } from "./EffectsLayer";
import { ResourceLayer } from "./ResourceLayer";
import { TileLayer } from "./TileLayer";

export const WORLD_CONFIG = {
  tileSize: 24,
  widthTiles: 20,
  heightTiles: 14,
  resourceRect: { x: 4, y: 1, w: 12, h: 5 },
  townRect: { x: 7, y: 10, w: 6, h: 3 },
  resourceAnchor: { x: 10, y: 4 },
  townAnchor: { x: 10, y: 11.5 }
} as const;

type SceneHandlers = {
  onSelectAgent: (id: number) => void;
  onHoverAgent: (id: number | null) => void;
};

export class WorldScene {
  readonly root = new Container();

  private readonly tileLayer: TileLayer;
  private readonly resourceLayer: ResourceLayer;
  private readonly agentLayer: AgentLayer;
  private readonly effectsLayer: EffectsLayer;
  private lastEffectTick = -1;

  constructor(private readonly app: Application, handlers: SceneHandlers) {
    const cfg = WORLD_CONFIG;

    this.tileLayer = new TileLayer({
      tileSize: cfg.tileSize,
      widthTiles: cfg.widthTiles,
      heightTiles: cfg.heightTiles,
      resourceRect: cfg.resourceRect,
      townRect: cfg.townRect
    });

    this.resourceLayer = new ResourceLayer({
      tileSize: cfg.tileSize,
      rect: cfg.resourceRect
    });

    this.agentLayer = new AgentLayer({
      tileSize: cfg.tileSize,
      onSelectAgent: handlers.onSelectAgent,
      onHoverAgent: handlers.onHoverAgent
    });

    this.effectsLayer = new EffectsLayer(
      {
        tileSize: cfg.tileSize,
        townAnchor: cfg.townAnchor,
        resourceAnchor: cfg.resourceAnchor
      },
      this.app.ticker
    );

    this.root.addChild(this.tileLayer.container);
    this.root.addChild(this.resourceLayer.container);
    this.root.addChild(this.effectsLayer.container);
    this.root.addChild(this.agentLayer.container);
  }

  renderTransition(
    previousTick: TickState,
    nextTick: TickState,
    progress: number,
    selectedAgentId: number | null,
    hoveredAgentId: number | null
  ) {
    if (nextTick.t !== this.lastEffectTick && progress < 0.2) {
      this.effectsLayer.emitForTransition(previousTick, nextTick);
      this.lastEffectTick = nextTick.t;
    }

    const interpolatedResource =
      previousTick.world.resource + (nextTick.world.resource - previousTick.world.resource) * progress;

    this.resourceLayer.update(interpolatedResource, nextTick.world.resourceCap);
    this.tileLayer.setCollapsed(nextTick.world.collapsed);

    this.agentLayer.renderAgents(
      previousTick.agents,
      nextTick.agents,
      progress,
      selectedAgentId,
      hoveredAgentId
    );
  }

  resize(width: number, height: number) {
    const worldW = WORLD_CONFIG.widthTiles * WORLD_CONFIG.tileSize;
    const worldH = WORLD_CONFIG.heightTiles * WORLD_CONFIG.tileSize;

    const scale = Math.min(width / worldW, height / worldH);
    this.root.scale.set(scale);

    this.root.position.set((width - worldW * scale) * 0.5, (height - worldH * scale) * 0.5);
  }

  destroy() {
    this.root.destroy({ children: true });
  }
}
