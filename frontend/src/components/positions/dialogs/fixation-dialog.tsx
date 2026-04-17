"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Textarea } from "@/components/ui/textarea";
import { ProblemDetailsError } from "@/lib/api/fetcher";
import { useCreateFixation } from "@/lib/api/hooks/use-positions";

type Mode = "flat" | "cbot" | "cbot_basis" | "basis" | "fx";

const schema = z.object({
  fixation_mode: z.enum(["flat", "cbot", "cbot_basis", "basis", "fx"]),
  quantity_tons: z.string().min(1),
  fixation_date: z.string().min(1),
  cbot_fixed: z.string().optional(),
  basis_fixed: z.string().optional(),
  fx_fixed: z.string().optional(),
  reference_cbot_contract: z.string().optional(),
  notes: z.string().optional(),
});
type FormValues = z.infer<typeof schema>;

const MODE_LEGS: Record<Mode, { cbot: boolean; basis: boolean; fx: boolean }> = {
  flat: { cbot: true, basis: true, fx: true },
  cbot: { cbot: true, basis: false, fx: false },
  cbot_basis: { cbot: true, basis: true, fx: false },
  basis: { cbot: false, basis: true, fx: false },
  fx: { cbot: false, basis: false, fx: true },
};

export function FixationDialog({
  frameId,
  open,
  onOpenChange,
  remainingTons,
}: {
  frameId: string;
  open: boolean;
  onOpenChange: (next: boolean) => void;
  remainingTons: { cbot: number; basis: number; fx: number };
}) {
  const create = useCreateFixation(frameId);
  const { register, handleSubmit, watch, setValue, reset, formState } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { fixation_mode: "flat" },
  });
  const [serverError, setServerError] = useState<string | null>(null);

  const mode = watch("fixation_mode") ?? "flat";
  const legs = MODE_LEGS[mode];
  const qty = Number(watch("quantity_tons") ?? "");

  useEffect(() => {
    if (!open) {
      reset({ fixation_mode: "flat" });
      setServerError(null);
    }
  }, [open, reset]);

  // Client-side over-lock guard: the smallest remaining bucket among locked legs.
  const activeRemaining: number[] = [];
  if (legs.cbot) activeRemaining.push(remainingTons.cbot);
  if (legs.basis) activeRemaining.push(remainingTons.basis);
  if (legs.fx) activeRemaining.push(remainingTons.fx);
  const minRemaining = activeRemaining.length ? Math.min(...activeRemaining) : Infinity;
  const overLockedClientSide = Number.isFinite(qty) && qty > 0 && qty > minRemaining;

  const onSubmit = handleSubmit(async (values) => {
    setServerError(null);
    try {
      await create.mutateAsync({
        fixation_mode: values.fixation_mode,
        quantity_tons: values.quantity_tons,
        fixation_date: values.fixation_date,
        cbot_fixed: legs.cbot ? values.cbot_fixed || null : null,
        basis_fixed: legs.basis ? values.basis_fixed || null : null,
        fx_fixed: legs.fx ? values.fx_fixed || null : null,
        reference_cbot_contract: values.reference_cbot_contract || null,
        notes: values.notes || null,
      });
      toast.success("Fixação registrada.");
      onOpenChange(false);
    } catch (err) {
      if (err instanceof ProblemDetailsError && err.status === 409) {
        const detail = err.problem.detail;
        const remainingFromServer =
          detail && typeof detail === "object" && "remaining_tons" in detail
            ? String((detail as Record<string, unknown>).remaining_tons)
            : "?";
        const leg =
          detail && typeof detail === "object" && "leg" in detail
            ? String((detail as Record<string, unknown>).leg)
            : "?";
        setServerError(`Over-lock no leg ${leg}: restam ${remainingFromServer} t`);
        return;
      }
      setServerError(err instanceof Error ? err.message : "Erro desconhecido");
    }
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Nova fixação</DialogTitle>
          <DialogDescription>
            Escolha o modo — os campos obrigatórios variam conforme o leg fixado.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="flex flex-col gap-3">
          <div className="flex flex-col gap-2">
            <Label>Modo</Label>
            <RadioGroup
              value={mode}
              onValueChange={(v) => setValue("fixation_mode", v as Mode)}
              className="grid grid-cols-5 gap-2"
            >
              {(["flat", "cbot", "cbot_basis", "basis", "fx"] as const).map((m) => (
                <label
                  key={m}
                  className="hover:bg-accent flex cursor-pointer items-center justify-center gap-1 rounded-md border px-2 py-1 text-xs"
                >
                  <RadioGroupItem value={m} />
                  <span>{m}</span>
                </label>
              ))}
            </RadioGroup>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Tonelagem" error={formState.errors.quantity_tons?.message}>
              <Input type="number" step="0.0001" {...register("quantity_tons")} />
            </Field>
            <Field label="Data" error={formState.errors.fixation_date?.message}>
              <Input type="date" {...register("fixation_date")} />
            </Field>
          </div>
          <p className="text-muted-foreground text-xs">
            Restante (open): cbot {remainingTons.cbot.toFixed(4)} t · basis{" "}
            {remainingTons.basis.toFixed(4)} t · fx {remainingTons.fx.toFixed(4)} t
          </p>
          {overLockedClientSide && (
            <p className="text-destructive text-xs" role="alert">
              Quantidade excede o restante em pelo menos um leg ativo ({minRemaining.toFixed(4)} t).
            </p>
          )}
          <div className="grid grid-cols-3 gap-3">
            {legs.cbot && (
              <Field label="CBOT (USc/bu)">
                <Input type="number" step="0.0001" {...register("cbot_fixed")} />
              </Field>
            )}
            {legs.basis && (
              <Field label="Basis (USD/bu)">
                <Input type="number" step="0.0001" {...register("basis_fixed")} />
              </Field>
            )}
            {legs.fx && (
              <Field label="FX (BRL/USD)">
                <Input type="number" step="0.0001" {...register("fx_fixed")} />
              </Field>
            )}
          </div>
          <Field label="Contrato CBOT ref.">
            <Input {...register("reference_cbot_contract")} placeholder="ZSK26" />
          </Field>
          <Field label="Notas">
            <Textarea rows={2} {...register("notes")} />
          </Field>
          {serverError && (
            <p className="text-destructive text-sm" role="alert">
              {serverError}
            </p>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={create.isPending || overLockedClientSide}>
              {create.isPending ? "Salvando…" : "Registrar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <Label>{label}</Label>
      {children}
      {error && (
        <p className="text-destructive text-xs" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
