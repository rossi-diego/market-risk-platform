"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { CorrelationResponse } from "@/lib/api/hooks/use-risk";
import { useCorrelation } from "@/lib/api/hooks/use-risk";

import { useRiskPortfolio } from "./portfolio-store";

const WINDOWS = [30, 90, 252];

function cellColor(value: number): string {
  // -1 → red, 0 → neutral, 1 → green
  const clamped = Math.max(-1, Math.min(1, value));
  if (clamped >= 0) {
    return `color-mix(in oklab, var(--background), green ${Math.round(clamped * 60)}%)`;
  }
  return `color-mix(in oklab, var(--background), red ${Math.round(-clamped * 60)}%)`;
}

export function CorrelationHeatmap() {
  const { window: win, setWindow } = useRiskPortfolio();
  const query = useCorrelation(win);
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle>Correlation heatmap</CardTitle>
          <CardDescription>
            Correlação empírica dos fatores nas últimas {win} observações.
          </CardDescription>
        </div>
        <Select value={String(win)} onValueChange={(v) => v && setWindow(Number(v))}>
          <SelectTrigger className="w-28">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {WINDOWS.map((w) => (
              <SelectItem key={w} value={String(w)}>
                {w}d
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </CardHeader>
      <CardContent>
        {query.isLoading ? (
          <Skeleton className="h-48 w-full" />
        ) : query.isError || !query.data ? (
          <p className="text-muted-foreground text-sm">Sem histórico suficiente.</p>
        ) : (
          <HeatmapGrid data={query.data} />
        )}
      </CardContent>
    </Card>
  );
}

function HeatmapGrid({ data }: { data: CorrelationResponse }) {
  const { names, matrix } = data;
  return (
    <div className="overflow-x-auto">
      <table className="border-collapse text-xs">
        <thead>
          <tr>
            <th className="border p-2" />
            {names.map((n) => (
              <th key={n} className="text-muted-foreground border p-2 font-medium">
                {n}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={names[i]}>
              <th className="text-muted-foreground border p-2 text-left font-medium">{names[i]}</th>
              {row.map((value, j) => {
                const n = Number(value);
                return (
                  <td
                    key={`${names[i]}-${names[j]}`}
                    className="border p-2 text-center"
                    style={{ background: cellColor(n) }}
                  >
                    {Number.isFinite(n) ? n.toFixed(2) : "—"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
