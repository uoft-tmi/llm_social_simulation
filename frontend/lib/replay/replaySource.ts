import mockReplay from "@/lib/mock/sampleReplay.json";
import { ensureReplay } from "@/lib/replay/replayAdapter";
import { ReplaySourceMode, SimulationReplay } from "@/lib/replay/replayTypes";

export type ReplaySourceConfig =
  | { mode: "mock" }
  | { mode: "http"; url: string }
  | { mode: "ws"; url: string };

export async function loadReplay(config: ReplaySourceConfig): Promise<SimulationReplay> {
  if (config.mode === "mock") {
    return ensureReplay(mockReplay);
  }

  if (config.mode === "http") {
    const response = await fetch(config.url);
    if (!response.ok) {
      throw new Error(`Failed to load replay from ${config.url}: ${response.status}`);
    }
    const payload = (await response.json()) as SimulationReplay;
    return ensureReplay(payload);
  }

  throw new Error(
    `Replay mode '${config.mode}' is reserved for live streaming. Add a WS adapter to map stream frames into TickState[].`
  );
}

export function defaultReplayMode(): ReplaySourceMode {
  return "mock";
}
