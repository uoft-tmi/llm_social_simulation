import {
  AgentState,
  ReplayEvent,
  TickCommunication,
  TickState
} from "@/lib/replay/replayTypes";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";

function findAgent(tick: TickState | null, id: number | null): AgentState | null {
  if (!tick || id == null) return null;
  return tick.agents.find((agent) => agent.id === id) ?? null;
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-0.5 text-xs">
      <span className="text-moss-100/75">{label}</span>
      <span className="pixel-font text-moss-50">{value}</span>
    </div>
  );
}

function latestAgentEvent(tick: TickState | null, agentId: number): ReplayEvent | null {
  if (!tick?.events) return null;
  for (let idx = tick.events.length - 1; idx >= 0; idx -= 1) {
    const event = tick.events[idx];
    if (event.agent_id === agentId) return event;
  }
  return null;
}

function agentMessages(tick: TickState | null, agentId: number): TickCommunication[] {
  if (!tick?.communications) return [];
  return tick.communications.filter((entry) => entry.agentId === agentId).slice(-5);
}

export function AgentInspector({
  tick,
  selectedAgentId,
  hoveredAgentId
}: {
  tick: TickState | null;
  selectedAgentId: number | null;
  hoveredAgentId: number | null;
}) {
  const chosenId = selectedAgentId ?? hoveredAgentId;
  const agent = findAgent(tick, chosenId);
  const event = agent ? latestAgentEvent(tick, agent.id) : null;
  const payload = event?.payload ?? {};
  const debugRaw = payload["decision_debug"];
  const decisionDebug = typeof debugRaw === "object" && debugRaw !== null
    ? (debugRaw as Record<string, unknown>)
    : null;
  const messages = agent ? agentMessages(tick, agent.id) : [];

  return (
    <Card
      title="Agent Inspector"
      rightSlot={agent ? <Badge tone="accent">ID {agent.id}</Badge> : <Badge tone="neutral">No selection</Badge>}
    >
      {!agent ? (
        <p className="text-xs text-moss-100/70">Click an agent sprite in the world to inspect actions and reasoning.</p>
      ) : (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Badge tone="neutral">{agent.type}</Badge>
            {agent.modelLabel ? <Badge tone="ok">{agent.modelLabel}</Badge> : null}
            {agent.clamped?.harvest || agent.clamped?.contribute ? <Badge tone="warn">Clamp</Badge> : null}
          </div>

          <div className="space-y-1 border-b border-moss-700/30 pb-2">
            <Row label="Wealth" value={agent.wealth.toFixed(2)} />
            <Row label="Harvest req" value={agent.action.harvestRequested.toFixed(2)} />
            <Row label="Harvest act" value={agent.action.harvestActual.toFixed(2)} />
            <Row label="Contribution" value={agent.action.contribute.toFixed(2)} />
            <Row label="Reward" value={agent.action.reward.toFixed(2)} />
            <Row label="Clamp harvest" value={String(Boolean(agent.clamped?.harvest))} />
            <Row label="Clamp contribute" value={String(Boolean(agent.clamped?.contribute))} />
          </div>

          <div>
            <div className="mb-1 text-[11px] uppercase tracking-wide text-moss-200">Last reason</div>
            <p className="rounded border border-moss-700/50 bg-slate-900/55 p-2 text-xs leading-relaxed text-moss-50/90">
              {agent.reason ?? "No reason text available."}
            </p>
          </div>

          <div>
            <div className="mb-1 text-[11px] uppercase tracking-wide text-moss-200">Recent messages</div>
            <div className="space-y-1 rounded border border-moss-700/50 bg-slate-900/55 p-2 text-xs">
              {messages.length === 0 ? (
                <div className="text-moss-100/70">No recent messages this tick.</div>
              ) : (
                messages.map((entry, idx) => (
                  <div key={`${entry.t}-${entry.agentId}-${idx}`} className="text-moss-50/90">
                    [{entry.scope}] {entry.topic}: {entry.message}
                  </div>
                ))
              )}
            </div>
          </div>

          <div>
            <div className="mb-1 text-[11px] uppercase tracking-wide text-moss-200">Decision influence</div>
            <div className="rounded border border-moss-700/50 bg-slate-900/55 p-2 text-xs">
              {decisionDebug ? (
                <div className="space-y-1">
                  <div className="text-moss-100/80">
                    reason: {String(decisionDebug.influence_reason ?? "-")}
                  </div>
                  <div className="text-moss-100/80">
                    zone: {String(decisionDebug.influencing_zone ?? "-")}
                  </div>
                  <div className="text-moss-100/80">
                    speaker label: {String(decisionDebug.influencing_speaker_label ?? "unknown")}
                  </div>
                  <div className="text-moss-100/80">
                    score: {String(decisionDebug.influence_score ?? "0")}
                  </div>
                </div>
              ) : (
                <div className="text-moss-100/70">
                  No decision debug on latest action.
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
