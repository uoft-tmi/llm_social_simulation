import { ReplaySpeed } from "@/lib/replay/useReplayController";

import { Badge } from "@/components/ui/Badge";

type ToolbarProps = {
  roundLabel: string;
  isPlaying: boolean;
  speed: ReplaySpeed;
  speedOptions: readonly ReplaySpeed[];
  onTogglePlay: () => void;
  onStepForward: () => void;
  onStepBack: () => void;
  onReset: () => void;
  onSpeedChange: (speed: ReplaySpeed) => void;
};

export function SimulationToolbar({
  roundLabel,
  isPlaying,
  speed,
  speedOptions,
  onTogglePlay,
  onStepForward,
  onStepBack,
  onReset,
  onSpeedChange
}: ToolbarProps) {
  return (
    <div className="panel flex flex-wrap items-center justify-between gap-3 p-3">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onTogglePlay}
          className="rounded-sm border border-moss-300/60 bg-moss-500 px-3 py-1.5 pixel-font text-xs uppercase text-slate-950 transition hover:bg-moss-400"
        >
          {isPlaying ? "Pause" : "Play"}
        </button>
        <button
          type="button"
          onClick={onStepBack}
          className="rounded-sm border border-moss-300/40 bg-slate-900/70 px-2 py-1 text-xs text-moss-100 hover:bg-slate-800"
        >
          -1
        </button>
        <button
          type="button"
          onClick={onStepForward}
          className="rounded-sm border border-moss-300/40 bg-slate-900/70 px-2 py-1 text-xs text-moss-100 hover:bg-slate-800"
        >
          +1
        </button>
        <button
          type="button"
          onClick={onReset}
          className="rounded-sm border border-clay-300/40 bg-clay-700/70 px-3 py-1 text-xs text-clay-100 hover:bg-clay-600"
        >
          Reset
        </button>
      </div>

      <div className="flex items-center gap-2">
        <Badge tone="accent">{roundLabel}</Badge>
        <div className="inline-flex rounded-sm border border-moss-300/40 bg-slate-900/70 p-1">
          {speedOptions.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => onSpeedChange(option)}
              className={`rounded-sm px-2 py-1 pixel-font text-[10px] ${
                option === speed
                  ? "bg-amber-400 text-slate-950"
                  : "text-moss-100 hover:bg-moss-800/70"
              }`}
            >
              {option}x
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
