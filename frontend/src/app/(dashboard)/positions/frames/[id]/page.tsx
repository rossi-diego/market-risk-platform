"use client";

import { ArrowLeft, Calendar, Plus } from "lucide-react";
import Link from "next/link";
import { use, useMemo, useState } from "react";

import { FixationDialog } from "@/components/positions/dialogs/fixation-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { usePhysicalFrame, usePhysicalFrames } from "@/lib/api/hooks/use-positions";
import { formatDate, formatPrice, formatTons } from "@/lib/formatters";

const MODE_LEGS = {
  flat: { cbot: true, basis: true, fx: true },
  cbot: { cbot: true, basis: false, fx: false },
  cbot_basis: { cbot: true, basis: true, fx: false },
  basis: { cbot: false, basis: true, fx: false },
  fx: { cbot: false, basis: false, fx: true },
} as const;

function computeRemaining(
  total: number,
  fixations: { fixation_mode: string; quantity_tons: string }[],
): { cbot: number; basis: number; fx: number } {
  let cbotLocked = 0;
  let basisLocked = 0;
  let fxLocked = 0;
  for (const f of fixations) {
    const mode = f.fixation_mode as keyof typeof MODE_LEGS;
    const qty = Number(f.quantity_tons);
    if (!Number.isFinite(qty)) continue;
    const legs = MODE_LEGS[mode];
    if (legs?.cbot) cbotLocked += qty;
    if (legs?.basis) basisLocked += qty;
    if (legs?.fx) fxLocked += qty;
  }
  return {
    cbot: Math.max(0, total - cbotLocked),
    basis: Math.max(0, total - basisLocked),
    fx: Math.max(0, total - fxLocked),
  };
}

export default function FrameDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const detail = usePhysicalFrame(id);
  const framesList = usePhysicalFrames();
  const [dialogOpen, setDialogOpen] = useState(false);

  const summary = framesList.data?.find((f) => f.id === id);
  const total = Number(detail.data?.quantity_tons ?? 0);
  const remaining = useMemo(
    () => computeRemaining(total, detail.data?.fixations ?? []),
    [total, detail.data?.fixations],
  );

  if (detail.isLoading || !detail.data) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  const frame = detail.data;
  const fixations = [...frame.fixations].sort((a, b) =>
    a.fixation_date < b.fixation_date ? 1 : -1,
  );

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-2">
        <Link
          href="/positions?tab=physical"
          className="text-muted-foreground hover:text-foreground flex items-center gap-1 text-sm"
        >
          <ArrowLeft className="size-4" /> Voltar
        </Link>
      </div>
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">{frame.counterparty ?? "(sem contraparte)"}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
            <Badge variant="outline">{frame.commodity}</Badge>
            <Badge variant={frame.side === "buy" ? "default" : "secondary"}>{frame.side}</Badge>
            <Badge variant="outline">{frame.status}</Badge>
            <span className="text-muted-foreground inline-flex items-center gap-1">
              <Calendar className="size-4" />
              {formatDate(frame.delivery_start)} → {formatDate(frame.delivery_end)}
            </span>
          </div>
        </div>
        <Button onClick={() => setDialogOpen(true)}>
          <Plus className="size-4" /> Nova fixação
        </Button>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Exposição por leg</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <LegBar
            label="CBOT"
            locked={summary?.locked_cbot_tons ?? "0"}
            total={frame.quantity_tons}
          />
          <LegBar
            label="Basis"
            locked={summary?.locked_basis_tons ?? "0"}
            total={frame.quantity_tons}
          />
          <LegBar label="FX" locked={summary?.locked_fx_tons ?? "0"} total={frame.quantity_tons} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Timeline de fixações</CardTitle>
        </CardHeader>
        <CardContent>
          {fixations.length === 0 ? (
            <p className="text-muted-foreground text-sm">
              Nenhuma fixação registrada. Clique em &quot;Nova fixação&quot; para começar.
            </p>
          ) : (
            <ol className="flex flex-col gap-3 border-l pl-6">
              {fixations.map((f) => (
                <li key={f.id} className="relative">
                  <span className="bg-primary absolute top-2 -left-[1.625rem] size-3 rounded-full" />
                  <div className="rounded-md border p-3">
                    <div className="mb-2 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline">{f.fixation_mode}</Badge>
                        <span className="font-medium">{formatTons(f.quantity_tons)}</span>
                      </div>
                      <span className="text-muted-foreground text-xs">
                        {formatDate(f.fixation_date)}
                      </span>
                    </div>
                    <dl className="text-muted-foreground grid grid-cols-3 gap-2 text-xs">
                      <div>
                        <dt>CBOT</dt>
                        <dd className="text-foreground">{formatPrice(f.cbot_fixed)}</dd>
                      </div>
                      <div>
                        <dt>Basis</dt>
                        <dd className="text-foreground">{formatPrice(f.basis_fixed)}</dd>
                      </div>
                      <div>
                        <dt>FX</dt>
                        <dd className="text-foreground">{formatPrice(f.fx_fixed)}</dd>
                      </div>
                    </dl>
                    {f.reference_cbot_contract && (
                      <p className="text-muted-foreground mt-2 text-xs">
                        ref: {f.reference_cbot_contract}
                      </p>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </CardContent>
      </Card>

      <FixationDialog
        frameId={frame.id}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        remainingTons={remaining}
      />
    </div>
  );
}

function LegBar({ label, locked, total }: { label: string; locked: string; total: string }) {
  const lockedN = Number(locked);
  const totalN = Number(total);
  const pct = totalN > 0 ? Math.min(100, (lockedN / totalN) * 100) : 0;
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-medium">{label}</span>
        <span className="text-muted-foreground text-xs">
          {formatTons(lockedN)} / {formatTons(totalN)} ({pct.toFixed(1)}%)
        </span>
      </div>
      <Progress value={pct} className="h-2" />
    </div>
  );
}
