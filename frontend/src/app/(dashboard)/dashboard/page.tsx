import { Activity, AlertTriangle, BarChart3, TrendingUp } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface Kpi {
  label: string;
  value: string;
  hint: string;
  icon: typeof TrendingUp;
}

const KPIS: Kpi[] = [
  {
    label: "Total Exposure",
    value: "BRL 0",
    hint: "Net open CBOT + basis + FX (aggregate)",
    icon: TrendingUp,
  },
  {
    label: "Parametric VaR (95% · 1d)",
    value: "BRL 0",
    hint: "Flat, delta-normal",
    icon: BarChart3,
  },
  {
    label: "CVaR (97.5% · 1d)",
    value: "BRL 0",
    hint: "Expected shortfall — FRTB-aligned",
    icon: Activity,
  },
  {
    label: "Active Scenarios",
    value: "0",
    hint: "Custom + historical templates",
    icon: AlertTriangle,
  },
];

export default function DashboardPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-muted-foreground text-sm">
          Visão agregada das posições + métricas de risco. Dados preenchidos conforme Phases 10–11
          concluam.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {KPIS.map((kpi) => (
          <Card key={kpi.label}>
            <CardHeader className="flex flex-row items-center justify-between gap-2 pb-2">
              <CardTitle className="text-muted-foreground text-sm font-medium">
                {kpi.label}
              </CardTitle>
              <kpi.icon className="text-muted-foreground size-4" aria-hidden="true" />
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-semibold">{kpi.value}</p>
              <p className="text-muted-foreground mt-1 text-xs">{kpi.hint}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
