"use client";

import { Download } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import type { CVarResponse, StressRow, VarResponse } from "@/lib/api/hooks/use-risk";
import { useRiskPdf } from "@/lib/api/hooks/use-risk";

import { useRiskPortfolio } from "./portfolio-store";

export function ExportReportButton({
  varData,
  cvarData,
  stressData,
}: {
  varData: VarResponse | undefined;
  cvarData: CVarResponse | undefined;
  stressData: StressRow[] | undefined;
}) {
  const state = useRiskPortfolio();
  const pdf = useRiskPdf();
  const [loading, setLoading] = useState(false);

  const onExport = async () => {
    setLoading(true);
    try {
      const payload = {
        portfolio_value_brl: Object.values(state.weights).reduce(
          (acc, v) => acc + Number(v || 0),
          0,
        ),
        var_flat_brl: varData?.value_brl ?? null,
        var_per_leg: varData?.per_leg ?? {},
        cvar_flat_brl: cvarData?.value_brl ?? null,
        stress_results: (stressData ?? []).map((s) => ({
          scenario_name: s.scenario_name,
          total_pnl_brl: s.total_pnl_brl,
        })),
        attribution_top: [],
        confidence: String(state.confidence),
        horizon_days: state.horizonDays,
      };
      const blob = await pdf.mutateAsync(payload);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `risk-report-${new Date().toISOString().slice(0, 10)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success("PDF gerado.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Falha ao gerar PDF");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Button onClick={onExport} disabled={loading} variant="outline">
      <Download className="size-4" />
      {loading ? "Gerando…" : "Export PDF"}
    </Button>
  );
}
