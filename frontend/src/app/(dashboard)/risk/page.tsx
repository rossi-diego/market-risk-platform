"use client";

import { useMemo } from "react";

import { AttributionTable } from "@/components/risk/attribution-table";
import { CorrelationHeatmap } from "@/components/risk/correlation-heatmap";
import { ExportReportButton } from "@/components/risk/export-report-button";
import { FanChart } from "@/components/risk/fan-chart";
import { useRiskPortfolio } from "@/components/risk/portfolio-store";
import { RiskControls } from "@/components/risk/risk-controls";
import { StressPanel } from "@/components/risk/stress-panel";
import { VarCard } from "@/components/risk/var-card";
import { useCVar, useFan, useStressHistorical, useVar } from "@/lib/api/hooks/use-risk";

export default function RiskPage() {
  const state = useRiskPortfolio();
  const varRequest = useMemo(
    () => ({
      method: state.method,
      confidence: String(state.confidence),
      horizon_days: state.horizonDays,
      window: state.window,
      weights: state.weights,
    }),
    [state.method, state.confidence, state.horizonDays, state.window, state.weights],
  );
  const fanRequest = useMemo(
    () => ({
      weights: state.weights,
      horizon_days: Math.max(5, state.horizonDays),
      n_paths: 5000,
      window: state.window,
      seed: 42,
    }),
    [state.weights, state.horizonDays, state.window],
  );
  const stressRequest = useMemo(
    () => ({
      exposure_tons_by_commodity: state.exposureTons,
      prices_current: state.pricesCurrent,
    }),
    [state.exposureTons, state.pricesCurrent],
  );

  const varQuery = useVar(varRequest);
  const cvarQuery = useCVar(varRequest);
  const fanQuery = useFan(fanRequest);
  const stressQuery = useStressHistorical(stressRequest);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Risk</h1>
          <p className="text-muted-foreground text-sm">
            Deep-dive: VaR/CVaR com três métodos, MC fan chart, cenários históricos, matriz de
            correlação e atribuição paramétrica.
          </p>
        </div>
        <ExportReportButton
          varData={varQuery.data}
          cvarData={cvarQuery.data}
          stressData={stressQuery.data}
        />
      </div>

      <RiskControls />

      <div className="grid gap-4 lg:grid-cols-2">
        <VarCard
          title="VaR"
          description="Value at Risk — maior perda esperada ao nível de confiança escolhido."
          data={varQuery.data}
          isLoading={varQuery.isLoading}
          isError={varQuery.isError}
        />
        <VarCard
          title="CVaR / ES"
          description="Expected Shortfall — média das perdas além do VaR."
          data={cvarQuery.data}
          isLoading={cvarQuery.isLoading}
          isError={cvarQuery.isError}
          tone="warning"
        />
      </div>

      <FanChart data={fanQuery.data} isLoading={fanQuery.isLoading} />

      <StressPanel />

      <div className="grid gap-4 lg:grid-cols-2">
        <AttributionTable />
        <CorrelationHeatmap />
      </div>
    </div>
  );
}
