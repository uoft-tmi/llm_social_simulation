export type ReplayMode = "open_resources" | "open_world";

export type SimulationReplay = {
  meta: {
    runId: string;
    scenario: string;
    modelLabels: Record<string, string>;
    mode?: ReplayMode;
  };
  ticks: TickState[];
};

export type TickMetrics = {
  totalHarvestRequested: number;
  totalHarvestActual: number;
  totalContribution: number;
  totalReward: number;
  moveTotal?: number;
  gatherTotal?: number;
  restTotal?: number;
  talkLocalTotal?: number;
  broadcastTotal?: number;
  communicationTotal?: number;
  invalidActionTotal?: number;
  avgEnergy?: number;
  totalCredits?: number;
  averageHonestyBelief?: number;
  averageBeliefConfidence?: number;
  suspiciousLabelsCount?: number;
  validatedTruthfulReports?: number;
  validatedFalseReports?: number;
  communicationInfluencedActionTotal?: number;
  trustedInfluenceActionTotal?: number;
  suspiciousDiscountActionTotal?: number;
};

export type ZoneState = {
  id: string;
  x: number;
  y: number;
  resource: number;
  resourceCap: number;
  regenRate: number;
  resourceType: string;
  neighbors: string[];
  blocked: boolean;
};

export type ReplayEvent = {
  t: number;
  agent_id: number;
  kind: string;
  location_id: string;
  action?: {
    kind: string;
    move_target?: string | null;
    gather_resource?: string | null;
    amount?: number | null;
    message?: string | null;
    speech_act?: string | null;
    topic?: string | null;
    meta?: Record<string, unknown>;
  } | null;
  valid: boolean;
  reason?: string | null;
  payload?: Record<string, unknown>;
};

export type TickCommunication = {
  t: number;
  agentId: number;
  scope: string;
  locationId: string;
  message: string;
  speechAct: string;
  topic: string;
};

export type ReputationBeliefSummary = {
  subject_id: number;
  honesty: number;
  reliability: number;
  confidence: number;
  label: string;
};

export type TickReputationSummary = {
  average_honesty_belief?: number;
  average_belief_confidence?: number;
  suspicious_labels_count?: number;
  validated_truthful_reports?: number;
  validated_false_reports?: number;
  by_observer?: Record<string, ReputationBeliefSummary[]>;
};

export type TickDecisionInfluenceSummary = {
  communication_influenced_action_total?: number;
  trusted_influence_action_total?: number;
  suspicious_discount_action_total?: number;
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
  metrics: TickMetrics;
  zones?: ZoneState[];
  events?: ReplayEvent[];
  communications?: TickCommunication[];
  reputation?: TickReputationSummary;
  decisionInfluence?: TickDecisionInfluenceSummary;
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
  state?: {
    locationId: string;
    energy: number;
    inventory: Record<string, number>;
  };
};

export type ReplaySourceMode = "mock" | "http" | "ws";

export type BackendRunRequest = {
  mode?: ReplayMode;
  agent_type: "greedy" | "coop" | "adaptive" | "mixed" | "llm" | "rule";
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
