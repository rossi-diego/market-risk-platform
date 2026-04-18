"use client";

import { useMemo } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { AttributionRequest } from "@/lib/api/hooks/use-risk";
import { useAttribution } from "@/lib/api/hooks/use-risk";
import { formatBRL, formatPercent } from "@/lib/formatters";

import { useRiskPortfolio } from "./portfolio-store";

export function AttributionTable() {
  const state = useRiskPortfolio();
  const request = useMemo<AttributionRequest>(() => {
    // Each weight entry becomes one "position" for the attribution call.
    const positions: AttributionRequest["positions"] = [];
    const pairs: [keyof typeof state.weights, string][] = [
      ["ZS=F", "Soja CBOT"],
      ["ZC=F", "Milho CBOT"],
      ["USDBRL=X", "FX USD/BRL"],
    ];
    for (const [instr, label] of pairs) {
      const w = state.weights[instr];
      if (!w || Number(w) === 0) continue;
      positions.push({
        position_id: crypto.randomUUID(),
        label,
        weight_brl: w,
        factor_exposures: { [instr]: w },
      });
    }
    return {
      positions,
      confidence: String(state.confidence),
      horizon_days: state.horizonDays,
      window: state.window,
    };
  }, [state.weights, state.confidence, state.horizonDays, state.window]);

  const query = useAttribution(request);

  const sumContribution = useMemo(() => {
    if (!query.data) return 0;
    return query.data.reduce((acc, row) => acc + Number(row.contribution_brl), 0);
  }, [query.data]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Attribution</CardTitle>
        <CardDescription>
          Decomposição paramétrica do VaR flat em contribuições por posição.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {query.isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : query.isError || !query.data || query.data.length === 0 ? (
          <p className="text-muted-foreground text-sm">
            Configure pesos (controles) para gerar a atribuição.
          </p>
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Posição</TableHead>
                  <TableHead>Contribuição (BRL)</TableHead>
                  <TableHead>Share</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {query.data.map((row) => {
                  const share = Number(row.share_pct);
                  return (
                    <TableRow key={row.position_id}>
                      <TableCell className="font-medium">{row.label}</TableCell>
                      <TableCell>{formatBRL(row.contribution_brl)}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Progress value={Math.abs(share)} className="h-1.5 w-24" />
                          <span className="text-muted-foreground text-xs">
                            {formatPercent(share)}
                          </span>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
            <p className="text-muted-foreground mt-3 text-xs">
              Σ contribuições = {formatBRL(sumContribution)} (deve bater com o flat VaR paramétrico
              — diferença = ruído de arredondamento)
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
