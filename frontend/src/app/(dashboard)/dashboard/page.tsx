"use client";

import { Activity, AlertTriangle, BarChart3, TrendingUp } from "lucide-react";
import { useMemo } from "react";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { useRiskPortfolio } from "@/components/risk/portfolio-store";
import { RiskControls } from "@/components/risk/risk-controls";
import { VarCard } from "@/components/risk/var-card";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useBasisForwards,
  useCbotDerivatives,
  useFxDerivatives,
  usePhysicalFrames,
} from "@/lib/api/hooks/use-positions";
import { useVar } from "@/lib/api/hooks/use-risk";
import { formatBRL, formatSignedBRL } from "@/lib/formatters";

export default function DashboardPage() {
  const state = useRiskPortfolio();
  const frames = usePhysicalFrames();
  const cbot = useCbotDerivatives();
  const basis = useBasisForwards();
  const fx = useFxDerivatives();

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
  const varQuery = useVar(varRequest);

  const openCount =
    (frames.data?.length ?? 0) +
    (cbot.data?.length ?? 0) +
    (basis.data?.length ?? 0) +
    (fx.data?.length ?? 0);

  const exposureData = useMemo(() => {
    // Signed BRL exposure per factor. A simple linear read of the user-supplied
    // weights; positions still load independently and feed the row count.
    const w = state.weights;
    return [
      { label: "CBOT soja", value: Number(w["ZS=F"] ?? 0) },
      { label: "CBOT milho", value: Number(w["ZC=F"] ?? 0) },
      { label: "FX", value: Number(w["USDBRL=X"] ?? 0) },
    ];
  }, [state.weights]);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-muted-foreground text-sm">
          Visão agregada das posições + métricas de risco. Ajuste os pesos em &quot;Controles&quot;
          para ver VaR/CVaR atualizados.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Kpi
          label="Posições em aberto"
          value={openCount.toString()}
          hint="Físicas + CBOT + basis + FX"
          Icon={TrendingUp}
        />
        <Kpi
          label="VaR (método atual)"
          value={varQuery.data ? formatBRL(varQuery.data.value_brl) : "—"}
          hint={`${state.method} · ${(state.confidence * 100).toFixed(0)}% · ${state.horizonDays}d`}
          Icon={BarChart3}
          loading={varQuery.isLoading}
        />
        <Kpi
          label="VaR CBOT leg"
          value={varQuery.data ? formatBRL(varQuery.data.per_leg.cbot) : "—"}
          hint="Isolado ao fator CBOT"
          Icon={Activity}
          loading={varQuery.isLoading}
        />
        <Kpi
          label="VaR FX leg"
          value={varQuery.data ? formatBRL(varQuery.data.per_leg.fx) : "—"}
          hint="Isolado ao fator USDBRL"
          Icon={AlertTriangle}
          loading={varQuery.isLoading}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-[3fr_2fr]">
        <Card>
          <CardHeader>
            <CardTitle>Exposição por fator</CardTitle>
            <CardDescription>
              BRL alocado por fator (sinal: long positivo / short negativo).
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-56 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={exposureData}>
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} stroke="var(--muted-foreground)" />
                  <YAxis
                    tick={{ fontSize: 11 }}
                    stroke="var(--muted-foreground)"
                    tickFormatter={(v) => formatBRL(v)}
                    width={100}
                  />
                  <Tooltip
                    formatter={(v) => formatSignedBRL(Number(v ?? 0))}
                    contentStyle={{
                      background: "var(--card)",
                      border: "1px solid var(--border)",
                      fontSize: "12px",
                    }}
                  />
                  <Bar dataKey="value">
                    {exposureData.map((d) => (
                      <Cell
                        key={d.label}
                        fill={
                          d.value >= 0 ? "var(--chart-2, #10b981)" : "var(--destructive, #ef4444)"
                        }
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
        <VarCard
          title="VaR summary"
          description="Flat + per-leg conforme método/confiança/horizonte nos controles."
          data={varQuery.data}
          isLoading={varQuery.isLoading}
          isError={varQuery.isError}
        />
      </div>

      <RiskControls compact />
    </div>
  );
}

function Kpi({
  label,
  value,
  hint,
  Icon,
  loading,
}: {
  label: string;
  value: string;
  hint: string;
  Icon: typeof TrendingUp;
  loading?: boolean;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2 pb-2">
        <CardTitle className="text-muted-foreground text-sm font-medium">{label}</CardTitle>
        <Icon className="text-muted-foreground size-4" aria-hidden="true" />
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-8 w-32" />
        ) : (
          <p className="text-2xl font-semibold">{value}</p>
        )}
        <p className="text-muted-foreground mt-1 text-xs">{hint}</p>
      </CardContent>
    </Card>
  );
}
