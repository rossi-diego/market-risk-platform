"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useRiskPortfolio } from "@/components/risk/portfolio-store";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch } from "@/lib/api/fetcher";
import type { StressRow } from "@/lib/api/hooks/use-risk";
import { formatBRL, formatSignedBRL } from "@/lib/formatters";

type Factor = "cbot" | "fx" | "basis";

const POINTS = Array.from({ length: 13 }, (_, i) => -0.3 + i * 0.05); // -30% … +30%

function scenarioFor(factor: Factor, shock: number) {
  return {
    name: `sensitivity-${factor}-${shock.toFixed(2)}`,
    cbot_soja: factor === "cbot" ? shock.toString() : "0",
    cbot_milho: factor === "cbot" ? shock.toString() : "0",
    basis_soja: factor === "basis" ? shock.toString() : "0",
    basis_milho: factor === "basis" ? shock.toString() : "0",
    fx: factor === "fx" ? shock.toString() : "0",
    source_period: "sensitivity",
  };
}

export function SensitivitySliders() {
  const state = useRiskPortfolio();
  const [rows, setRows] = useState<
    { shock: number; cbot: number; fx: number; basis: number }[] | null
  >(null);

  const exposurePrices = useMemo(
    () => ({
      exposure_tons_by_commodity: state.exposureTons,
      prices_current: state.pricesCurrent,
    }),
    [state.exposureTons, state.pricesCurrent],
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const next: { shock: number; cbot: number; fx: number; basis: number }[] = [];
      for (const shock of POINTS) {
        const [cbotRow, fxRow, basisRow] = await Promise.all(
          (["cbot", "fx", "basis"] as Factor[]).map((factor) =>
            apiFetch<StressRow>("/risk/stress/custom", {
              method: "POST",
              body: { scenario: scenarioFor(factor, shock), ...exposurePrices },
            }),
          ),
        );
        next.push({
          shock: Number(shock.toFixed(2)),
          cbot: Number(cbotRow.total_pnl_brl),
          fx: Number(fxRow.total_pnl_brl),
          basis: Number(basisRow.total_pnl_brl),
        });
      }
      if (!cancelled) setRows(next);
    })();
    return () => {
      cancelled = true;
    };
  }, [exposurePrices]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Sensibilidade por fator</CardTitle>
        <CardDescription>
          P&L total em função de shocks independentes por fator ({(-30).toFixed(0)}% … +30%).
        </CardDescription>
      </CardHeader>
      <CardContent>
        {!rows ? (
          <Skeleton className="h-64 w-full" />
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap gap-4 text-xs">
              <Legend color="var(--chart-1, #3b82f6)" label="CBOT" />
              <Legend color="var(--chart-2, #10b981)" label="FX" />
              <Legend color="var(--chart-3, #f59e0b)" label="Basis" />
            </div>
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={rows}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis
                    dataKey="shock"
                    tick={{ fontSize: 10 }}
                    stroke="var(--muted-foreground)"
                    tickFormatter={(v) => `${(Number(v) * 100).toFixed(0)}%`}
                  />
                  <YAxis
                    tick={{ fontSize: 10 }}
                    stroke="var(--muted-foreground)"
                    tickFormatter={(v) => formatBRL(v)}
                    width={100}
                  />
                  <Tooltip
                    formatter={(v) => formatSignedBRL(Number(v ?? 0))}
                    labelFormatter={(label) => `Shock ${(Number(label) * 100).toFixed(0)}%`}
                    contentStyle={{
                      background: "var(--card)",
                      border: "1px solid var(--border)",
                      fontSize: "12px",
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="cbot"
                    stroke="var(--chart-1, #3b82f6)"
                    dot={false}
                  />
                  <Line type="monotone" dataKey="fx" stroke="var(--chart-2, #10b981)" dot={false} />
                  <Line
                    type="monotone"
                    dataKey="basis"
                    stroke="var(--chart-3, #f59e0b)"
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <Label className="flex items-center gap-2 text-xs">
      <span className="inline-block size-3 rounded" style={{ background: color }} aria-hidden />
      {label}
    </Label>
  );
}
