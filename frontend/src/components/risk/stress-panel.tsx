"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { StressRow } from "@/lib/api/hooks/use-risk";
import { useStressHistorical } from "@/lib/api/hooks/use-risk";
import { formatSignedBRL } from "@/lib/formatters";

import { useRiskPortfolio } from "./portfolio-store";

export function StressPanel() {
  const state = useRiskPortfolio();
  const query = useStressHistorical({
    exposure_tons_by_commodity: state.exposureTons,
    prices_current: state.pricesCurrent,
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>Stress — cenários históricos</CardTitle>
        <CardDescription>
          Full revaluation via pricing.mtm_value_brl (linear em exposição, não linear em preço).
        </CardDescription>
      </CardHeader>
      <CardContent>
        {query.isLoading ? (
          <div className="grid gap-3 md:grid-cols-2">
            {Array.from({ length: 4 }).map((_, idx) => (
              <Skeleton key={idx} className="h-32 w-full" />
            ))}
          </div>
        ) : query.isError || !query.data ? (
          <p className="text-muted-foreground text-sm">Falha ao carregar cenários.</p>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {query.data.map((row) => (
              <ScenarioCard key={row.scenario_name} row={row} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ScenarioCard({ row }: { row: StressRow }) {
  const pnl = Number(row.total_pnl_brl);
  const tone =
    pnl > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400";
  return (
    <div className="rounded-md border p-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold">{row.scenario_name}</h3>
        <span className={`text-lg font-semibold ${tone}`}>{formatSignedBRL(pnl)}</span>
      </div>
      <dl className="grid grid-cols-3 gap-2 text-xs">
        <Stat label="CBOT" value={row.per_leg_pnl.cbot} />
        <Stat label="Basis" value={row.per_leg_pnl.basis} />
        <Stat label="FX" value={row.per_leg_pnl.fx} />
      </dl>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-muted-foreground text-[10px] uppercase">{label}</dt>
      <dd>{formatSignedBRL(value)}</dd>
    </div>
  );
}
