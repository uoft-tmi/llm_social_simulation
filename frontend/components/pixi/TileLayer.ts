import { Container, Graphics } from "pixi.js";

type TileLayerConfig = {
  tileSize: number;
  widthTiles: number;
  heightTiles: number;
  resourceRect: { x: number; y: number; w: number; h: number };
  townRect: { x: number; y: number; w: number; h: number };
};

export class TileLayer {
  readonly container = new Container();
  private readonly overlay = new Graphics();

  constructor(private readonly cfg: TileLayerConfig) {
    this.drawGround();
    this.drawTown();
    this.overlay.alpha = 0;
    this.container.addChild(this.overlay);
    this.drawOverlay();
  }

  private drawGround() {
    const { tileSize, widthTiles, heightTiles, resourceRect } = this.cfg;
    for (let y = 0; y < heightTiles; y += 1) {
      for (let x = 0; x < widthTiles; x += 1) {
        const g = new Graphics();
        const inResource =
          x >= resourceRect.x &&
          x < resourceRect.x + resourceRect.w &&
          y >= resourceRect.y &&
          y < resourceRect.y + resourceRect.h;

        const color = inResource
          ? (x + y) % 2 === 0
            ? 0x4a7645
            : 0x3f6b3b
          : (x + y) % 2 === 0
            ? 0x406043
            : 0x37553a;

        g.rect(x * tileSize, y * tileSize, tileSize, tileSize).fill(color);
        g.rect(x * tileSize, y * tileSize, tileSize, tileSize).stroke({ color: 0x243726, width: 1, alpha: 0.5 });
        this.container.addChild(g);
      }
    }
  }

  private drawTown() {
    const { tileSize, townRect } = this.cfg;
    const town = new Graphics();
    town
      .rect(townRect.x * tileSize, townRect.y * tileSize, townRect.w * tileSize, townRect.h * tileSize)
      .fill(0x7f5a3d)
      .stroke({ color: 0x2f1d10, width: 2 });

    const roof = new Graphics();
    roof
      .rect((townRect.x + 1) * tileSize, (townRect.y - 1) * tileSize, (townRect.w - 2) * tileSize, tileSize)
      .fill(0xc88a56)
      .stroke({ color: 0x51331d, width: 2 });

    const sign = new Graphics();
    sign.rect((townRect.x + townRect.w / 2 - 0.5) * tileSize, townRect.y * tileSize, tileSize, tileSize * 0.7).fill(0xe7d28a);

    this.container.addChild(town, roof, sign);
  }

  private drawOverlay() {
    const { tileSize, widthTiles, heightTiles } = this.cfg;
    this.overlay.clear();
    this.overlay.rect(0, 0, widthTiles * tileSize, heightTiles * tileSize).fill(0x5c6264);
  }

  setCollapsed(collapsed: boolean) {
    this.overlay.alpha = collapsed ? 0.45 : 0;
  }
}
