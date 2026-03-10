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
