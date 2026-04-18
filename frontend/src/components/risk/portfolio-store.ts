"use client";

import { create } from "zustand";

import type { Method } from "@/lib/api/hooks/use-risk";

export interface RiskPortfolioState {
  method: Method;
  confidence: number;
  horizonDays: number;
  window: number;
  weights: {
    "ZS=F": string;
    "ZC=F": string;
    "USDBRL=X": string;
  };
  exposureTons: {
    soja: { cbot: string; basis: string; fx: string };
    milho: { cbot: string; basis: string; fx: string };
  };
  pricesCurrent: {
    cbot_soja: string;
    cbot_milho: string;
    fx: string;
    basis_soja: string;
    basis_milho: string;
  };

  setMethod: (method: Method) => void;
  setConfidence: (value: number) => void;
  setHorizonDays: (value: number) => void;
  setWindow: (value: number) => void;
  setWeight: (instrument: keyof RiskPortfolioState["weights"], value: string) => void;
  setExposure: (commodity: "soja" | "milho", leg: "cbot" | "basis" | "fx", value: string) => void;
  setPrice: (key: keyof RiskPortfolioState["pricesCurrent"], value: string) => void;
}

export const useRiskPortfolio = create<RiskPortfolioState>((set) => ({
  method: "parametric",
  confidence: 0.95,
  horizonDays: 1,
  window: 252,
  weights: {
    "ZS=F": "1000",
    "ZC=F": "1000",
    "USDBRL=X": "1000",
  },
  exposureTons: {
    soja: { cbot: "1000", basis: "1000", fx: "1000" },
    milho: { cbot: "0", basis: "0", fx: "0" },
  },
  pricesCurrent: {
    cbot_soja: "1000",
    cbot_milho: "400",
    fx: "5",
    basis_soja: "0.5",
    basis_milho: "0.3",
  },
  setMethod: (method) => set({ method }),
  setConfidence: (confidence) => set({ confidence }),
  setHorizonDays: (horizonDays) => set({ horizonDays }),
  setWindow: (window) => set({ window }),
  setWeight: (instrument, value) =>
    set((state) => ({ weights: { ...state.weights, [instrument]: value } })),
  setExposure: (commodity, leg, value) =>
    set((state) => ({
      exposureTons: {
        ...state.exposureTons,
        [commodity]: { ...state.exposureTons[commodity], [leg]: value },
      },
    })),
  setPrice: (key, value) =>
    set((state) => ({ pricesCurrent: { ...state.pricesCurrent, [key]: value } })),
}));
