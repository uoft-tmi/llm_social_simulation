import { Container, Graphics, Text } from "pixi.js";

import { AgentState } from "@/lib/replay/replayTypes";

type AgentSprite = {
  root: Container;
  body: Graphics;
  ring: Graphics;
  label: Text;
};

type LayerOptions = {
  tileSize: number;
  onSelectAgent: (id: number) => void;
  onHoverAgent: (id: number | null) => void;
};

const AGENT_COLORS = [0xf5b14d, 0x6ec5ff, 0xff8ea0, 0x8de48b, 0xcb9eff, 0xffda75, 0x89efe2, 0xd7a58a];

function colorForAgent(id: number): number {
  return AGENT_COLORS[id % AGENT_COLORS.length];
}

function findAgentById(list: AgentState[], id: number) {
  return list.find((item) => item.id === id);
}

export class AgentLayer {
  readonly container = new Container();
  private sprites = new Map<number, AgentSprite>();
  private tickClock = 0;

  constructor(private readonly options: LayerOptions) {}

  renderAgents(
    prevAgents: AgentState[],
    nextAgents: AgentState[],
    progress: number,
    selectedAgentId: number | null,
    hoveredAgentId: number | null
  ) {
    this.tickClock += 0.03;

    for (const next of nextAgents) {
      let sprite = this.sprites.get(next.id);
      if (!sprite) {
        sprite = this.createSprite(next.id);
        this.sprites.set(next.id, sprite);
        this.container.addChild(sprite.root);
      }

      const prev = findAgentById(prevAgents, next.id) ?? next;
      const x = prev.x + (next.x - prev.x) * progress;
      const y = prev.y + (next.y - prev.y) * progress;
      const bob = Math.sin(this.tickClock + next.id) * 1.4;
      sprite.root.position.set(x * this.options.tileSize, y * this.options.tileSize + bob);

      const selected = selectedAgentId === next.id;
      const hovered = hoveredAgentId === next.id;
      this.drawBody(sprite.body, next.id, selected, hovered);
      this.drawRing(sprite.ring, selected, hovered);
      sprite.label.text = String(next.id);
      sprite.label.style.fill = selected ? 0xfffbe6 : 0xf5f5f5;
      sprite.label.position.set(-4, -15);
    }

    for (const [id, sprite] of this.sprites.entries()) {
      if (!nextAgents.some((a) => a.id === id)) {
        this.container.removeChild(sprite.root);
        sprite.root.destroy({ children: true });
        this.sprites.delete(id);
      }
    }
  }

  private createSprite(id: number): AgentSprite {
    const root = new Container();
    const ring = new Graphics();
    const body = new Graphics();
    const label = new Text({
      text: String(id),
      style: {
        fontSize: 9,
        fill: 0xf5f5f5,
        fontFamily: "Courier New"
      }
    });

    body.eventMode = "static";
    body.cursor = "pointer";
    body.on("pointerdown", () => this.options.onSelectAgent(id));
    body.on("pointerover", () => this.options.onHoverAgent(id));
    body.on("pointerout", () => this.options.onHoverAgent(null));

    root.addChild(ring, body, label);
    return { root, ring, body, label };
  }

  private drawBody(g: Graphics, id: number, selected: boolean, hovered: boolean) {
    const color = colorForAgent(id);
    g.clear();
    g.rect(-5, -7, 10, 12).fill(color);
    g.rect(-3, -9, 6, 4).fill(0xfff0d2);
    g.rect(-5, -7, 10, 12).stroke({ color: 0x1e2125, width: selected ? 2 : 1 });

    if (hovered) {
      g.rect(-6, -10, 12, 16).stroke({ color: 0xd2fff0, width: 1, alpha: 0.9 });
    }
  }

  private drawRing(g: Graphics, selected: boolean, hovered: boolean) {
    g.clear();
    if (!selected && !hovered) return;
    g.circle(0, 2, selected ? 9 : 8).stroke({
      color: selected ? 0xffd166 : 0x9fe8ff,
      width: 2,
      alpha: 0.95
    });
  }
}
