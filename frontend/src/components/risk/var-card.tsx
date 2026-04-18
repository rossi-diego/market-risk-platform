"use client";

import { Activity, AlertTriangle } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { CVarResponse, VarResponse } from "@/lib/api/hooks/use-risk";
import { formatBRL } from "@/lib/formatters";

export function VarCard({
  title,
  description,
  data,
  isLoading,
  isError,
  tone = "default",
}: {
  title: string;
  description: string;
  data: VarResponse | CVarResponse | undefined;
  isLoading?: boolean;
  isError?: boolean;
  tone?: "default" | "warning";
}) {
  const Icon = tone === "warning" ? AlertTriangle : Activity;
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <div>
          <CardTitle>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </div>
        <Icon
          className={tone === "warning" ? "size-5 text-amber-500" : "text-muted-foreground size-5"}
          aria-hidden="true"
        />
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {isLoading ? (
          <Skeleton className="h-10 w-48" />
        ) : isError || !data ? (
          <p className="text-muted-foreground text-sm">
            Dados indisponíveis — verifique o histórico de preços no backend.
          </p>
        ) : (
          <>
            <div>
              <p className="text-3xl font-semibold">{formatBRL(data.value_brl)}</p>
              <p className="text-muted-foreground text-xs">
                método {data.method} · confiança {Number(data.confidence) * 100}% ·{" "}
                {data.horizon_days}d · N={data.n_observations}
              </p>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <LegStat label="CBOT" value={data.per_leg.cbot} />
              <LegStat label="Basis" value={data.per_leg.basis} />
              <LegStat label="FX" value={data.per_leg.fx} />
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function LegStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-md border p-2">
      <span className="text-muted-foreground text-[10px] uppercase">{label}</span>
      <span className="text-sm font-medium">{formatBRL(value)}</span>
    </div>
  );
}
