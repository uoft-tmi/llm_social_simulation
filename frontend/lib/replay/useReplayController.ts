"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { SimulationReplay, TickState } from "@/lib/replay/replayTypes";

const SPEED_OPTIONS = [1, 2, 4] as const;

export type ReplaySpeed = (typeof SPEED_OPTIONS)[number];

export function useReplayController(replay: SimulationReplay, defaultSpeed: ReplaySpeed = 1) {
  const [currentTickIndex, setCurrentTickIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState<ReplaySpeed>(defaultSpeed);

  const tickCount = replay.ticks.length;

  const currentTick = useMemo<TickState | null>(() => {
    if (tickCount === 0) return null;
    return replay.ticks[Math.min(currentTickIndex, tickCount - 1)] ?? null;
  }, [currentTickIndex, replay.ticks, tickCount]);

  const setTick = useCallback(
    (index: number) => {
      if (tickCount === 0) return;
      const bounded = Math.max(0, Math.min(index, tickCount - 1));
      setCurrentTickIndex(bounded);
    },
    [tickCount]
  );

  const play = useCallback(() => setIsPlaying(true), []);
  const pause = useCallback(() => setIsPlaying(false), []);
  const togglePlay = useCallback(() => setIsPlaying((v) => !v), []);

  const stepForward = useCallback(() => {
    setCurrentTickIndex((prev) => {
      if (tickCount === 0) return 0;
      return Math.min(prev + 1, tickCount - 1);
    });
  }, [tickCount]);

  const stepBack = useCallback(() => {
    setCurrentTickIndex((prev) => Math.max(prev - 1, 0));
  }, []);

  const reset = useCallback(() => {
    setCurrentTickIndex(0);
    setIsPlaying(false);
  }, []);

  useEffect(() => {
    if (!isPlaying || tickCount < 2) return;

    const atEnd = currentTickIndex >= tickCount - 1;
    if (atEnd) {
      setIsPlaying(false);
      return;
    }

    const baseMs = 850;
    const delay = Math.max(100, Math.floor(baseMs / speed));

    const timer = window.setTimeout(() => {
      setCurrentTickIndex((prev) => {
        const next = prev + 1;
        if (next >= tickCount - 1) {
          setIsPlaying(false);
          return tickCount - 1;
        }
        return next;
      });
    }, delay);

    return () => window.clearTimeout(timer);
  }, [currentTickIndex, isPlaying, speed, tickCount]);

  return {
    tickCount,
    currentTickIndex,
    currentTick,
    isPlaying,
    speed,
    speedOptions: SPEED_OPTIONS,
    setSpeed,
    setTick,
    play,
    pause,
    togglePlay,
    stepForward,
    stepBack,
    reset
  };
}
