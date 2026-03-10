import { AgentState, SimulationReplay, TickState } from "@/lib/replay/replayTypes";

type PythonOpenResourcesTick = {
  t: number;
  R_after: number;
  P_after: number;
  harvest_requested: Record<string, number>;
  harvest_actual: Record<string, number>;
  contribute: Record<string, number>;
  reward: Record<string, number>;
  wealth: Record<string, number>;
  clamped: Record<string, { harvest: boolean; contribute: boolean }>;
  info?: { collapsed?: boolean };
};

type PythonReplayEnvelope = {
  run_id?: string;
  scenario?: string;
  resource_cap?: number;
  model_labels?: Record<string, string>;
  ticks: PythonOpenResourcesTick[];
};

function toNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function stableAgentPosition(id: number): { x: number; y: number } {
  const radius = 3.8;
  const cx = 10;
  const cy = 10.6;
  const angle = (Math.PI * 2 * id) / 8;
  return {
    x: cx + Math.cos(angle) * radius,
    y: cy + Math.sin(angle) * radius
  };
}

function mapAgentFromPython(
  idRaw: string,
  tick: PythonOpenResourcesTick,
  modelLabels: Record<string, string>
): AgentState {
  const id = Number.parseInt(idRaw, 10);
  const fallbackPos = stableAgentPosition(id);
  return {
    id,
    type: modelLabels[String(id)] ? "llm" : "rule",
    modelLabel: modelLabels[String(id)],
    x: fallbackPos.x,
    y: fallbackPos.y,
    wealth: toNumber(tick.wealth[idRaw]),
    action: {
      harvestRequested: toNumber(tick.harvest_requested[idRaw]),
      harvestActual: toNumber(tick.harvest_actual[idRaw]),
      contribute: toNumber(tick.contribute[idRaw]),
      reward: toNumber(tick.reward[idRaw])
    },
    reason: null,
    clamped: tick.clamped[idRaw]
  };
}

export function adaptPythonReplay(payload: PythonReplayEnvelope): SimulationReplay {
  const modelLabels = payload.model_labels ?? {};
  const resourceCap = payload.resource_cap ?? 100;

  const ticks: TickState[] = payload.ticks.map((tick) => {
    const ids = Object.keys(tick.wealth);
    const agents = ids.map((idRaw) => mapAgentFromPython(idRaw, tick, modelLabels));

    const totalHarvestRequested = agents.reduce((sum, a) => sum + a.action.harvestRequested, 0);
    const totalHarvestActual = agents.reduce((sum, a) => sum + a.action.harvestActual, 0);
    const totalContribution = agents.reduce((sum, a) => sum + a.action.contribute, 0);
    const totalReward = agents.reduce((sum, a) => sum + a.action.reward, 0);

    return {
      t: tick.t,
      world: {
        resource: toNumber(tick.R_after),
        resourceCap,
        pool: toNumber(tick.P_after),
        collapsed: Boolean(tick.info?.collapsed)
      },
      agents,
      metrics: {
        totalHarvestRequested,
        totalHarvestActual,
        totalContribution,
        totalReward
      }
    };
  });

  return {
    meta: {
      runId: payload.run_id ?? "python-replay",
      scenario: payload.scenario ?? "open-resources",
      modelLabels
    },
    ticks
  };
}

export function ensureReplay(payload: SimulationReplay): SimulationReplay {
  return payload;
}
