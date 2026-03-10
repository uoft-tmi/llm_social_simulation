import { TickState } from "@/lib/replay/replayTypes";

export function CollapseBanner({ tick }: { tick: TickState | null }) {
  if (!tick?.world.collapsed) return null;

  return (
    <div className="panel border-rose-300/60 bg-rose-900/65 p-2">
      <p className="pixel-font text-xs uppercase text-rose-100">Resource Collapse Active</p>
      <p className="text-xs text-rose-100/85">
        The commons crossed collapse threshold. Resource tiles are depleted and environment is desaturated.
      </p>
    </div>
  );
}
