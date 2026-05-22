"use client";

import { useMemo } from "react";

import { AgentState, ReplayEvent, TickState, ZoneState } from "@/lib/replay/replayTypes";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";

type OpenWorldResearchViewProps = {
  tick: TickState | null;
  selectedAgentId: number | null;
  onSelectAgent: (id: number) => void;
  onHoverAgent: (id: number | null) => void;
};

type ZoneLayout = {
  leftPct: number;
  topPct: number;
};

const ZONE_LAYOUT: Record<string, ZoneLayout> = {
  forest: { leftPct: 18, topPct: 16 },
  sea: { leftPct: 80, topPct: 16 },
  farm: { leftPct: 18, topPct: 39 },
  market: { leftPct: 49, topPct: 39 },
  workshop: { leftPct: 80, topPct: 39 },
  housing: { leftPct: 18, topPct: 72 },
  town_hall: { leftPct: 49, topPct: 72 },
  clinic: { leftPct: 80, topPct: 72 }
};

const DEFAULT_NEIGHBORS: Record<string, string[]> = {
  forest: ["farm", "workshop", "housing"],
  sea: ["market", "clinic"],
  farm: ["forest", "market", "housing"],
  market: ["sea", "farm", "workshop", "town_hall"],
  workshop: ["forest", "market", "town_hall", "housing"],
  town_hall: ["market", "workshop", "clinic", "housing"],
  clinic: ["sea", "town_hall", "housing"],
  housing: ["forest", "farm", "workshop", "town_hall", "clinic"]
};

type DisplayZone = {
  id: string;
  resource: number;
  resourceCap: number;
  resourceType: string;
  neighbors: string[];
  blocked: boolean;
};

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function actionKindFromEvent(event: ReplayEvent | undefined, agent: AgentState): string {
  if (event?.kind) return event.kind;
  if (agent.action.harvestActual > 0) return "gather";
  return "rest";
}

function actionLabel(kind: string): string {
  const table: Record<string, string> = {
    move: "MV",
    gather: "GH",
    rest: "RS",
    talk_local: "TL",
    broadcast: "BC",
    invalid_action: "IV"
  };
  return table[kind] ?? kind.slice(0, 2).toUpperCase();
}

function normalizeZones(tick: TickState | null): DisplayZone[] {
  const zoneMap = new Map<string, ZoneState>();
  for (const zone of tick?.zones ?? []) {
    zoneMap.set(zone.id, zone);
  }

  return Object.keys(ZONE_LAYOUT).map((zoneId) => {
    const zone = zoneMap.get(zoneId);
    return {
      id: zoneId,
      resource: zone?.resource ?? 0,
      resourceCap: zone?.resourceCap ?? 1,
      resourceType: zone?.resourceType ?? "resource",
      neighbors: zone?.neighbors ?? DEFAULT_NEIGHBORS[zoneId] ?? [],
      blocked: Boolean(zone?.blocked)
    };
  });
}

function inferZoneFromCoordinates(agent: AgentState, zones: DisplayZone[]): string | null {
  if (!Number.isFinite(agent.x) || !Number.isFinite(agent.y)) return null;
  const withDistance = zones.map((zone) => {
    const fallback = ZONE_LAYOUT[zone.id];
    const dx = agent.x - fallback.leftPct;
    const dy = agent.y - fallback.topPct;
    return { id: zone.id, d2: dx * dx + dy * dy };
  });
  withDistance.sort((a, b) => a.d2 - b.d2);
  return withDistance[0]?.id ?? null;
}

export function OpenWorldResearchView({
  tick,
  selectedAgentId,
  onSelectAgent,
  onHoverAgent
}: OpenWorldResearchViewProps) {
  const zones = useMemo(() => normalizeZones(tick), [tick]);
  const events = useMemo(() => tick?.events ?? [], [tick?.events]);
  const communications = useMemo(() => tick?.communications ?? [], [tick?.communications]);

  const latestEventByAgent = useMemo(() => {
    const mapping = new Map<number, ReplayEvent>();
    for (const event of events) {
      mapping.set(event.agent_id, event);
    }
    return mapping;
  }, [events]);

  const zoneAgents = useMemo(() => {
    const mapping = new Map<string, AgentState[]>();
    for (const zone of zones) {
      mapping.set(zone.id, []);
    }
    for (const agent of tick?.agents ?? []) {
      const zoneId = agent.state?.locationId ?? inferZoneFromCoordinates(agent, zones);
      if (!zoneId) continue;
      const bucket = mapping.get(zoneId);
      if (!bucket) continue;
      bucket.push(agent);
    }
    for (const bucket of mapping.values()) {
      bucket.sort((a, b) => a.id - b.id);
    }
    return mapping;
  }, [tick?.agents, zones]);

  const edges = useMemo(() => {
    const dedupe = new Set<string>();
    const out: Array<{ from: string; to: string }> = [];
    for (const zone of zones) {
      for (const neighbor of zone.neighbors) {
        if (!ZONE_LAYOUT[neighbor]) continue;
        const pair = [zone.id, neighbor].sort();
        const key = `${pair[0]}::${pair[1]}`;
        if (dedupe.has(key)) continue;
        dedupe.add(key);
        out.push({ from: pair[0], to: pair[1] });
      }
    }
    return out;
  }, [zones]);

  if (!tick) {
    return <Card title="TMI Town Map">No open_world tick loaded.</Card>;
  }

  return (
    <div className="grid h-full grid-rows-[minmax(360px,1fr)_260px] gap-3">
      <Card
        title="TMI Town Map"
        rightSlot={<Badge tone={tick.world.collapsed ? "warn" : "ok"}>{tick.world.collapsed ? "Collapsed" : "Stable"}</Badge>}
      >
        <div className="relative h-[420px] rounded border border-moss-700/40 bg-slate-900/50">
          <svg className="pointer-events-none absolute inset-0 h-full w-full">
            {edges.map((edge) => {
              const from = ZONE_LAYOUT[edge.from];
              const to = ZONE_LAYOUT[edge.to];
              return (
                <line
                  key={`${edge.from}-${edge.to}`}
                  x1={`${from.leftPct}%`}
                  y1={`${from.topPct}%`}
                  x2={`${to.leftPct}%`}
                  y2={`${to.topPct}%`}
                  stroke="rgba(142,168,130,0.45)"
                  strokeWidth={2}
                />
              );
            })}
          </svg>

          {zones.map((zone) => {
            const layout = ZONE_LAYOUT[zone.id];
            const ratio = clamp01(zone.resource / Math.max(zone.resourceCap, 1));
            const agents = zoneAgents.get(zone.id) ?? [];
            return (
              <div
                key={zone.id}
                className="absolute w-36 -translate-x-1/2 -translate-y-1/2 rounded border border-moss-600/60 bg-slate-950/80 p-2"
                style={{ left: `${layout.leftPct}%`, top: `${layout.topPct}%` }}
              >
                <div className="flex items-center justify-between text-[11px]">
                  <span className="pixel-font uppercase text-moss-100">{zone.id}</span>
                  <Badge tone={zone.blocked ? "warn" : "neutral"}>{zone.resourceType}</Badge>
                </div>
                <div className="mt-1 text-[11px] text-moss-100/75">
                  R {zone.resource.toFixed(1)} / {zone.resourceCap.toFixed(1)}
                </div>
                <div className="mt-1 h-1.5 rounded bg-slate-800">
                  <div
                    className="h-1.5 rounded bg-gradient-to-r from-emerald-500 to-lime-300"
                    style={{ width: `${(ratio * 100).toFixed(1)}%` }}
                  />
                </div>
                <div className="mt-2 flex flex-wrap gap-1">
                  {agents.length === 0 ? (
                    <span className="text-[10px] text-moss-200/55">No agents</span>
                  ) : (
                    agents.map((agent) => {
                      const event = latestEventByAgent.get(agent.id);
                      const kind = actionKindFromEvent(event, agent);
                      const selected = selectedAgentId === agent.id;
                      return (
                        <button
                          key={agent.id}
                          type="button"
                          onClick={() => onSelectAgent(agent.id)}
                          onMouseEnter={() => onHoverAgent(agent.id)}
                          onMouseLeave={() => onHoverAgent(null)}
                          className={[
                            "rounded border px-1.5 py-0.5 text-[10px]",
                            selected
                              ? "border-amber-300 bg-amber-500/30 text-amber-100"
                              : "border-cyan-400/50 bg-cyan-600/25 text-cyan-100"
                          ].join(" ")}
                          title={`Agent ${agent.id} · ${kind}`}
                        >
                          A{agent.id} {actionLabel(kind)}
                        </button>
                      );
                    })
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      <Card
        title="Tick Feed"
        rightSlot={
          <span className="text-[11px] text-moss-100/70">
            {events.length} events · {communications.length} comms
          </span>
        }
      >
        <div className="grid h-[190px] grid-cols-1 gap-3 overflow-y-auto lg:grid-cols-2">
          <div className="space-y-1">
            <div className="text-[11px] uppercase tracking-wide text-moss-200">Actions</div>
            {events.length === 0 ? (
              <div className="text-xs text-moss-100/65">No action events.</div>
            ) : (
              events.map((event, idx) => (
                <div key={`${event.agent_id}-${event.kind}-${idx}`} className="rounded border border-moss-700/40 bg-slate-900/60 p-1.5 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="pixel-font text-moss-100">
                      A{event.agent_id} · {event.kind}
                    </span>
                    <Badge tone={event.valid ? "ok" : "warn"}>{event.valid ? "valid" : "invalid"}</Badge>
                  </div>
                  <div className="text-moss-100/70">
                    {event.location_id}
                    {event.reason ? ` · ${event.reason}` : ""}
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="space-y-1">
            <div className="text-[11px] uppercase tracking-wide text-moss-200">Communications</div>
            {communications.length === 0 ? (
              <div className="text-xs text-moss-100/65">No communication entries.</div>
            ) : (
              communications.map((comm, idx) => (
                <div key={`${comm.agentId}-${comm.t}-${idx}`} className="rounded border border-moss-700/40 bg-slate-900/60 p-1.5 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="pixel-font text-moss-100">
                      A{comm.agentId} · {comm.scope}
                    </span>
                    <Badge tone="neutral">{comm.topic}</Badge>
                  </div>
                  <div className="text-moss-100/70">{comm.locationId}</div>
                  <div className="mt-0.5 text-moss-50/90">{comm.message}</div>
                </div>
              ))
            )}
          </div>
        </div>
      </Card>
    </div>
  );
}
