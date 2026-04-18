"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { FanResponse } from "@/lib/api/hooks/use-risk";
import { formatBRL } from "@/lib/formatters";

export function FanChart({
  data,
  isLoading,
}: {
  data: FanResponse | undefined;
  isLoading?: boolean;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>MC fan chart</CardTitle>
        <CardDescription>
          Percentis 5 / 25 / 50 / 75 / 95 do P&L simulado por dia. Cholesky-correlated GBM.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-64 w-full" />
        ) : !data ? (
          <p className="text-muted-foreground text-sm">Sem dados.</p>
        ) : (
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={transform(data)}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="day" tick={{ fontSize: 10 }} stroke="var(--muted-foreground)" />
                <YAxis
                  tick={{ fontSize: 10 }}
                  stroke="var(--muted-foreground)"
                  tickFormatter={(v) => formatBRL(v)}
                  width={90}
                />
                <Tooltip
                  formatter={(value) => formatBRL(Number(value ?? 0))}
                  labelFormatter={(label) => `Dia ${label}`}
                  contentStyle={{
                    background: "var(--card)",
                    border: "1px solid var(--border)",
                    fontSize: "12px",
                  }}
                />
                {/* outer band p5-p95 */}
                <Area
                  type="monotone"
                  dataKey="p95"
                  stroke="transparent"
                  fill="var(--chart-2, #3b82f6)"
                  fillOpacity={0.15}
                  name="p95"
                />
                <Area
                  type="monotone"
                  dataKey="p5"
                  stroke="transparent"
                  fill="var(--background)"
                  fillOpacity={1}
                  name="p5"
                />
                {/* inner band p25-p75 */}
                <Area
                  type="monotone"
                  dataKey="p75"
                  stroke="transparent"
                  fill="var(--chart-2, #3b82f6)"
                  fillOpacity={0.3}
                  name="p75"
                />
                <Area
                  type="monotone"
                  dataKey="p25"
                  stroke="transparent"
                  fill="var(--background)"
                  fillOpacity={1}
                  name="p25"
                />
                <Line
                  type="monotone"
                  dataKey="p50"
                  stroke="var(--primary)"
                  strokeWidth={2}
                  dot={false}
                  name="p50 (mediana)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function transform(fan: FanResponse) {
  const horizon = fan.horizon_days;
  const rows: Array<{
    day: number;
    p5: number;
    p25: number;
    p50: number;
    p75: number;
    p95: number;
  }> = [];
  for (let i = 0; i < horizon; i += 1) {
    rows.push({
      day: i + 1,
      p5: Number(fan.percentiles["5"]?.[i] ?? 0),
      p25: Number(fan.percentiles["25"]?.[i] ?? 0),
      p50: Number(fan.percentiles["50"]?.[i] ?? 0),
      p75: Number(fan.percentiles["75"]?.[i] ?? 0),
      p95: Number(fan.percentiles["95"]?.[i] ?? 0),
    });
  }
  return rows;
}
