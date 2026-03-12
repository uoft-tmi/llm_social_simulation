export type SimulationReplay = {
  meta: {
    runId: string;
    scenario: string;
    modelLabels: Record<string, string>;
  };
  ticks: TickState[];
};

export type TickState = {
  t: number;
  world: {
    resource: number;
    resourceCap: number;
    pool: number;
    collapsed: boolean;
  };
  agents: AgentState[];
  metrics: {
    totalHarvestRequested: number;
    totalHarvestActual: number;
    totalContribution: number;
    totalReward: number;
  };
};

export type AgentState = {
  id: number;
  type: string;
  modelLabel?: string;
  x: number;
  y: number;
  wealth: number;
  action: {
    harvestRequested: number;
    harvestActual: number;
    contribute: number;
    reward: number;
  };
  reason?: string | null;
  clamped?: {
    harvest?: boolean;
    contribute?: boolean;
  };
};

export type ReplaySourceMode = "mock" | "http" | "ws";

export type BackendRunRequest = {
  agent_type: "greedy" | "coop" | "adaptive" | "mixed" | "llm";
  n_agents: number;
  rounds: number;
  seed?: number | null;
  config_overrides?: Record<string, number | string | null>;
  llm_guardrails?: boolean;
  llm_model?: string;
  llm_temperature?: number;
  llm_max_tokens?: number;
};

export type BackendRunCreateResponse = {
  run_id: string;
  status: "queued" | "running" | "done" | "failed";
  created_at: number;
};

export type BackendRunStatusResponse = {
  run_id: string;
  status: "queued" | "running" | "done" | "failed";
  error: string | null;
  created_at: number;
  updated_at: number;
};
