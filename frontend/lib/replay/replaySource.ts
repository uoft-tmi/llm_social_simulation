import mockReplay from "@/lib/mock/sampleReplay.json";
import { ensureReplay } from "@/lib/replay/replayAdapter";
import {
  BackendRunCreateResponse,
  BackendRunRequest,
  BackendRunStatusResponse,
  ReplaySourceMode,
  SimulationReplay
} from "@/lib/replay/replayTypes";

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

export function defaultBackendApiBase(): string {
  return process.env.NEXT_PUBLIC_SIM_API_BASE ?? "http://127.0.0.1:8000";
}

export async function createBackendRun(
  request: BackendRunRequest,
  apiBase = defaultBackendApiBase()
): Promise<BackendRunCreateResponse> {
  const response = await fetch(`${apiBase}/api/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request)
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to create run: ${response.status} ${text}`);
  }
  return (await response.json()) as BackendRunCreateResponse;
}

export async function getBackendRunStatus(
  runId: string,
  apiBase = defaultBackendApiBase()
): Promise<BackendRunStatusResponse> {
  const response = await fetch(`${apiBase}/api/runs/${runId}`);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to get run status: ${response.status} ${text}`);
  }
  return (await response.json()) as BackendRunStatusResponse;
}

export async function loadBackendReplay(
  runId: string,
  apiBase = defaultBackendApiBase()
): Promise<SimulationReplay> {
  return loadReplay({ mode: "http", url: `${apiBase}/api/runs/${runId}/replay` });
}
