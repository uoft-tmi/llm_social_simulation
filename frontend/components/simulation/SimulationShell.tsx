"use client";

import { useEffect, useMemo, useState } from "react";

import { WorldCanvas } from "@/components/pixi/WorldCanvas";
import {
  createBackendRun,
  getBackendRunStatus,
  loadBackendReplay,
  loadReplay
} from "@/lib/replay/replaySource";
import { BackendRunRequest, ReplayMode, SimulationReplay } from "@/lib/replay/replayTypes";
import { useReplayController } from "@/lib/replay/useReplayController";

import { AgentInspector } from "./AgentInspector";
import { CollapseBanner } from "./CollapseBanner";
import { MiniChartsPanel } from "./MiniChartsPanel";
import { OpenWorldResearchView } from "./OpenWorldResearchView";
import { SimulationMetricsPanel } from "./SimulationMetricsPanel";
import { SimulationToolbar } from "./SimulationToolbar";

const OPEN_RESOURCES_AGENT_OPTIONS = ["greedy", "coop", "adaptive", "mixed", "llm"] as const;
const OPEN_WORLD_AGENT_OPTIONS = ["rule", "llm"] as const;

function deriveReplayMode(replay: SimulationReplay): ReplayMode {
  if (replay.meta.mode === "open_world") return "open_world";
  if (replay.meta.scenario.toLowerCase().includes("open-world")) return "open_world";
  return "open_resources";
}

export function SimulationShell() {
  const [replay, setReplay] = useState<SimulationReplay | null>(null);
  const [selectedAgentId, setSelectedAgentId] = useState<number | null>(null);
  const [hoveredAgentId, setHoveredAgentId] = useState<number | null>(null);
  const [runStatus, setRunStatus] = useState<string>("idle");
  const [runError, setRunError] = useState<string | null>(null);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [pendingAutoPlay, setPendingAutoPlay] = useState(false);
  const [runForm, setRunForm] = useState({
    mode: "open_resources" as ReplayMode,
    agentType: "greedy" as BackendRunRequest["agent_type"],
    nAgents: 6,
    rounds: 80,
    seed: 0,
    initialResource: 60,
    resourceCap: 60,
    regenRate: 0.1,
    maxHarvestPerStep: 10,
    collapseThreshold: 0.5
  });

  useEffect(() => {
    loadReplay({ mode: "mock" })
      .then(setReplay)
      .catch((err: unknown) => setRunError(String(err)));
  }, []);

  const fallbackReplay = useMemo<SimulationReplay>(
    () => ({
      meta: { runId: "loading", scenario: "loading", modelLabels: {} },
      ticks: []
    }),
    []
  );
  const resolvedReplay = replay ?? fallbackReplay;
  const replayMode = deriveReplayMode(resolvedReplay);

  const replayController = useReplayController(resolvedReplay, 1);
  const { reset, play } = replayController;
  const currentTick = replayController.currentTick;

  useEffect(() => {
    if (!replay?.meta.runId) return;
    reset();
    setSelectedAgentId(null);
    if (pendingAutoPlay) {
      play();
      setPendingAutoPlay(false);
    }
  }, [pendingAutoPlay, replay?.meta.runId, play, reset]);

  useEffect(() => {
    if (!activeRunId) return;
    if (!["queued", "running"].includes(runStatus)) return;

    const timer = window.setInterval(async () => {
      try {
        const status = await getBackendRunStatus(activeRunId);
        setRunStatus(status.status);
        setRunError(status.error ?? null);

        if (status.status === "done") {
          const fetched = await loadBackendReplay(activeRunId);
          setReplay(fetched);
          setPendingAutoPlay(true);
        }
      } catch (err) {
        setRunStatus("failed");
        setRunError(String(err));
      }
    }, 900);

    return () => window.clearInterval(timer);
  }, [activeRunId, runStatus]);

  async function startBackendRun() {
    setRunError(null);
    setRunStatus("submitting");
    try {
      const request: BackendRunRequest =
        runForm.mode === "open_world"
          ? {
              mode: "open_world",
              agent_type: runForm.agentType === "llm" ? "llm" : "rule",
              n_agents: runForm.nAgents,
              rounds: runForm.rounds,
              seed: runForm.seed
            }
          : {
              mode: "open_resources",
              agent_type: runForm.agentType === "rule" ? "greedy" : runForm.agentType,
              n_agents: runForm.nAgents,
              rounds: runForm.rounds,
              seed: runForm.seed,
              config_overrides: {
                initial_resource: runForm.initialResource,
                resource_cap: runForm.resourceCap,
                regen_rate: runForm.regenRate,
                max_harvest_per_step: runForm.maxHarvestPerStep,
                collapse_threshold: runForm.collapseThreshold
              }
            };
      const created = await createBackendRun(request);
      setActiveRunId(created.run_id);
      setRunStatus(created.status);
    } catch (err) {
      setRunStatus("failed");
      setRunError(String(err));
    }
  }

  function patchRunForm<K extends keyof typeof runForm>(key: K, value: (typeof runForm)[K]) {
    setRunForm((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-[1600px] flex-col gap-3 p-4">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="pixel-font text-sm uppercase tracking-widest text-moss-100">
            {replayMode === "open_world" ? "TMI Town Research Viewer" : "Open Resources Simulation Viewer"}
          </h1>
          <p className="text-xs text-moss-100/70">
            Run {resolvedReplay.meta.runId} · {resolvedReplay.meta.scenario}
          </p>
        </div>
      </header>

      <SimulationToolbar
        roundLabel={`Tick ${replayController.currentTickIndex + 1}/${replayController.tickCount}`}
        isPlaying={replayController.isPlaying}
        speed={replayController.speed}
        speedOptions={replayController.speedOptions}
        onTogglePlay={replayController.togglePlay}
        onStepForward={replayController.stepForward}
        onStepBack={replayController.stepBack}
        onReset={() => {
          replayController.reset();
          setSelectedAgentId(null);
        }}
        onSpeedChange={replayController.setSpeed}
      />

      <div className="grid flex-1 grid-cols-1 gap-3 lg:grid-cols-[280px_minmax(600px,1fr)_340px]">
        <aside className="panel hidden p-3 lg:block">
          <h2 className="pixel-font mb-3 text-xs uppercase text-moss-200">Run Config</h2>
          <div className="space-y-2 text-xs">
            <label className="block">
              <span className="mb-1 block text-moss-100/80">Mode</span>
              <select
                value={runForm.mode}
                onChange={(e) => {
                  const mode = e.target.value as ReplayMode;
                  patchRunForm("mode", mode);
                  patchRunForm(
                    "agentType",
                    mode === "open_world"
                      ? runForm.agentType === "llm"
                        ? "llm"
                        : "rule"
                      : runForm.agentType === "rule"
                        ? "greedy"
                        : runForm.agentType
                  );
                }}
                className="w-full rounded border border-moss-700/60 bg-slate-900/70 px-2 py-1 text-moss-50"
              >
                <option value="open_resources">open_resources</option>
                <option value="open_world">open_world</option>
              </select>
            </label>

            <label className="block">
              <span className="mb-1 block text-moss-100/80">Agent Type</span>
              <select
                value={runForm.agentType}
                onChange={(e) =>
                  patchRunForm("agentType", e.target.value as BackendRunRequest["agent_type"])
                }
                className="w-full rounded border border-moss-700/60 bg-slate-900/70 px-2 py-1 text-moss-50"
              >
                {(runForm.mode === "open_world"
                  ? OPEN_WORLD_AGENT_OPTIONS
                  : OPEN_RESOURCES_AGENT_OPTIONS
                ).map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="mb-1 block text-moss-100/80">N Agents</span>
              <input
                type="number"
                value={runForm.nAgents}
                onChange={(e) => patchRunForm("nAgents", Number(e.target.value))}
                className="w-full rounded border border-moss-700/60 bg-slate-900/70 px-2 py-1 text-moss-50"
              />
            </label>

            <label className="block">
              <span className="mb-1 block text-moss-100/80">Rounds</span>
              <input
                type="number"
                value={runForm.rounds}
                onChange={(e) => patchRunForm("rounds", Number(e.target.value))}
                className="w-full rounded border border-moss-700/60 bg-slate-900/70 px-2 py-1 text-moss-50"
              />
            </label>

            <label className="block">
              <span className="mb-1 block text-moss-100/80">Seed</span>
              <input
                type="number"
                value={runForm.seed}
                onChange={(e) => patchRunForm("seed", Number(e.target.value))}
                className="w-full rounded border border-moss-700/60 bg-slate-900/70 px-2 py-1 text-moss-50"
              />
            </label>

            {runForm.mode === "open_resources" ? (
              <>
                <label className="block">
                  <span className="mb-1 block text-moss-100/80">Initial Resource</span>
                  <input
                    type="number"
                    value={runForm.initialResource}
                    onChange={(e) => patchRunForm("initialResource", Number(e.target.value))}
                    className="w-full rounded border border-moss-700/60 bg-slate-900/70 px-2 py-1 text-moss-50"
                  />
                </label>

                <label className="block">
                  <span className="mb-1 block text-moss-100/80">Resource Cap</span>
                  <input
                    type="number"
                    value={runForm.resourceCap}
                    onChange={(e) => patchRunForm("resourceCap", Number(e.target.value))}
                    className="w-full rounded border border-moss-700/60 bg-slate-900/70 px-2 py-1 text-moss-50"
                  />
                </label>

                <label className="block">
                  <span className="mb-1 block text-moss-100/80">Regen Rate</span>
                  <input
                    type="number"
                    step="0.01"
                    value={runForm.regenRate}
                    onChange={(e) => patchRunForm("regenRate", Number(e.target.value))}
                    className="w-full rounded border border-moss-700/60 bg-slate-900/70 px-2 py-1 text-moss-50"
                  />
                </label>

                <label className="block">
                  <span className="mb-1 block text-moss-100/80">Max Harvest / Step</span>
                  <input
                    type="number"
                    step="0.1"
                    value={runForm.maxHarvestPerStep}
                    onChange={(e) => patchRunForm("maxHarvestPerStep", Number(e.target.value))}
                    className="w-full rounded border border-moss-700/60 bg-slate-900/70 px-2 py-1 text-moss-50"
                  />
                </label>

                <label className="block">
                  <span className="mb-1 block text-moss-100/80">Collapse Threshold</span>
                  <input
                    type="number"
                    step="0.1"
                    value={runForm.collapseThreshold}
                    onChange={(e) => patchRunForm("collapseThreshold", Number(e.target.value))}
                    className="w-full rounded border border-moss-700/60 bg-slate-900/70 px-2 py-1 text-moss-50"
                  />
                </label>
              </>
            ) : null}

            <button
              type="button"
              onClick={startBackendRun}
              className="mt-2 w-full rounded border border-moss-300/60 bg-moss-500 px-2 py-2 pixel-font text-xs uppercase text-slate-950 hover:bg-moss-400"
            >
              Run Backend Simulation
            </button>

            <div className="rounded border border-moss-700/50 bg-slate-900/50 p-2 text-[11px] text-moss-100/85">
              <div>Status: {runStatus}</div>
              <div>Run ID: {activeRunId ?? "-"}</div>
              {runError ? <div className="text-rose-300">Error: {runError}</div> : null}
              <div className="mt-1 text-moss-200/70">
                API base: <code>{process.env.NEXT_PUBLIC_SIM_API_BASE ?? "http://127.0.0.1:8000"}</code>
              </div>
            </div>
          </div>
        </aside>

        <section className="flex min-h-[620px] flex-col gap-3">
          <CollapseBanner tick={currentTick} />
          <div className="h-[620px]">
            {replayMode === "open_world" ? (
              <OpenWorldResearchView
                tick={currentTick}
                selectedAgentId={selectedAgentId}
                onSelectAgent={setSelectedAgentId}
                onHoverAgent={setHoveredAgentId}
              />
            ) : (
              <WorldCanvas
                replay={resolvedReplay}
                tickIndex={replayController.currentTickIndex}
                selectedAgentId={selectedAgentId}
                onSelectAgent={setSelectedAgentId}
                onHoverAgent={setHoveredAgentId}
                speed={replayController.speed}
              />
            )}
          </div>
        </section>

        <aside className="subtle-scrollbar flex max-h-[calc(100vh-180px)] flex-col gap-3 overflow-y-auto pr-1">
          <SimulationMetricsPanel tick={currentTick} mode={replayMode} />
          <AgentInspector
            tick={currentTick}
            selectedAgentId={selectedAgentId}
            hoveredAgentId={hoveredAgentId}
            mode={replayMode}
          />
          <MiniChartsPanel replay={resolvedReplay} />
        </aside>
      </div>
    </main>
  );
}
