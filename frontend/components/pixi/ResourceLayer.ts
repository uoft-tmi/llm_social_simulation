import { Container, Graphics } from "pixi.js";

type ResourcePatch = {
  tileX: number;
  tileY: number;
  sprite: Graphics;
};

type ResourceLayerConfig = {
  tileSize: number;
  rect: { x: number; y: number; w: number; h: number };
};

export class ResourceLayer {
  readonly container = new Container();
  private readonly patches: ResourcePatch[] = [];
  private density = 1;

  constructor(private readonly cfg: ResourceLayerConfig) {
    const { rect } = cfg;
    for (let y = 0; y < rect.h; y += 1) {
      for (let x = 0; x < rect.w; x += 1) {
        const sprite = new Graphics();
        this.patches.push({
          tileX: rect.x + x,
          tileY: rect.y + y,
          sprite
        });
        this.container.addChild(sprite);
      }
    }
  }

  update(resource: number, resourceCap: number) {
    this.density = resourceCap > 0 ? Math.max(0, Math.min(1, resource / resourceCap)) : 0;
    for (const patch of this.patches) {
      this.drawPatch(patch);
    }
  }

  private drawPatch(patch: ResourcePatch) {
    const { tileSize } = this.cfg;
    const x = patch.tileX * tileSize;
    const y = patch.tileY * tileSize;
    const g = patch.sprite;
    const normalizedNoise = ((patch.tileX * 17 + patch.tileY * 31) % 10) / 10;

    g.clear();

    if (this.density <= 0.08 + normalizedNoise * 0.05) {
      g.rect(x + 4, y + 12, tileSize - 8, 3).fill(0x5b4c3f);
      return;
    }

    if (this.density < 0.35 + normalizedNoise * 0.1) {
      g.rect(x + 6, y + 10, 4, 4).fill(0x9a7f4b);
      g.rect(x + 10, y + 9, 4, 5).fill(0x7c9d46);
      g.rect(x + 7, y + 13, 7, 2).fill(0x2f4f2f);
      return;
    }

    if (this.density < 0.68 + normalizedNoise * 0.12) {
      g.rect(x + 7, y + 8, 2, 6).fill(0x624321);
      g.rect(x + 5, y + 4, 8, 6).fill(0x4d7f3f);
      g.rect(x + 4, y + 8, 10, 5).fill(0x5f904f);
      return;
    }

    g.rect(x + 7, y + 7, 2, 7).fill(0x5d3c1f);
    g.rect(x + 5, y + 2, 10, 8).fill(0x4f8f45);
    g.rect(x + 3, y + 6, 14, 7).fill(0x61a753);
    g.rect(x + 7, y + 1, 4, 3).fill(0x8cd27a);
  }
}
