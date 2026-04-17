"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ProblemDetailsError } from "@/lib/api/fetcher";
import {
  useCreateBasis,
  useCreateCbot,
  useCreateFx,
  useCreatePhysicalFrame,
} from "@/lib/api/hooks/use-positions";

type Family = "physical" | "cbot" | "basis" | "fx";

const physicalSchema = z.object({
  commodity: z.enum(["soja", "milho"]),
  side: z.enum(["buy", "sell"]),
  quantity_tons: z.string().min(1),
  delivery_start: z.string().min(1),
  delivery_end: z.string().min(1),
  counterparty: z.string().optional(),
  notes: z.string().optional(),
});

const cbotSchema = z
  .object({
    commodity: z.enum(["soja", "milho"]),
    instrument: z.enum(["future", "swap", "european_option", "american_option", "barrier_option"]),
    side: z.enum(["buy", "sell"]),
    contract: z.string().min(1),
    quantity_contracts: z.string().min(1),
    trade_date: z.string().min(1),
    trade_price: z.string().min(1),
    maturity_date: z.string().min(1),
    option_type: z.enum(["call", "put"]).optional(),
    strike: z.string().optional(),
    barrier_type: z.enum(["up_and_in", "up_and_out", "down_and_in", "down_and_out"]).optional(),
    barrier_level: z.string().optional(),
    rebate: z.string().optional(),
    counterparty: z.string().optional(),
    notes: z.string().optional(),
  })
  .superRefine((data, ctx) => {
    const isOption = data.instrument.endsWith("option");
    if (isOption && (!data.option_type || !data.strike)) {
      ctx.addIssue({
        code: "custom",
        message: "Opções exigem option_type e strike",
        path: ["strike"],
      });
    }
    if (data.instrument === "barrier_option" && (!data.barrier_type || !data.barrier_level)) {
      ctx.addIssue({
        code: "custom",
        message: "Barreira exige barrier_type e barrier_level",
        path: ["barrier_level"],
      });
    }
  });

const basisSchema = z.object({
  commodity: z.enum(["soja", "milho"]),
  side: z.enum(["buy", "sell"]),
  quantity_tons: z.string().min(1),
  trade_date: z.string().min(1),
  basis_price: z.string().min(1),
  delivery_date: z.string().min(1),
  reference_cbot_contract: z.string().min(1),
  counterparty: z.string().optional(),
  notes: z.string().optional(),
});

const fxSchema = z
  .object({
    instrument: z.enum(["ndf", "swap", "european_option", "american_option", "barrier_option"]),
    side: z.enum(["buy", "sell"]),
    notional_usd: z.string().min(1),
    trade_date: z.string().min(1),
    trade_rate: z.string().min(1),
    maturity_date: z.string().min(1),
    option_type: z.enum(["call", "put"]).optional(),
    strike: z.string().optional(),
    barrier_type: z.enum(["up_and_in", "up_and_out", "down_and_in", "down_and_out"]).optional(),
    barrier_level: z.string().optional(),
    rebate: z.string().optional(),
    counterparty: z.string().optional(),
    notes: z.string().optional(),
  })
  .superRefine((data, ctx) => {
    const isOption = data.instrument.endsWith("option");
    if (isOption && (!data.option_type || !data.strike)) {
      ctx.addIssue({
        code: "custom",
        message: "Opções exigem option_type e strike",
        path: ["strike"],
      });
    }
  });

type PhysicalForm = z.infer<typeof physicalSchema>;
type CbotForm = z.infer<typeof cbotSchema>;
type BasisForm = z.infer<typeof basisSchema>;
type FxForm = z.infer<typeof fxSchema>;

function getErrorMessage(err: unknown): string {
  if (err instanceof ProblemDetailsError) {
    const detail = err.problem.detail;
    if (typeof detail === "string") return detail;
    if (
      detail &&
      typeof detail === "object" &&
      "title" in detail &&
      typeof detail.title === "string"
    ) {
      return detail.title;
    }
    return err.problem.title ?? err.message;
  }
  if (err instanceof Error) return err.message;
  return "Erro desconhecido";
}

function blankToUndef<T extends Record<string, unknown>>(input: T): T {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(input)) {
    out[k] = typeof v === "string" && v === "" ? undefined : v;
  }
  return out as T;
}

export function PositionCreateDialog({
  open,
  onOpenChange,
  initialFamily,
}: {
  open: boolean;
  onOpenChange: (next: boolean) => void;
  initialFamily?: Family;
}) {
  const [family, setFamily] = useState<Family>(initialFamily ?? "physical");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Nova posição</DialogTitle>
          <DialogDescription>Escolha a família e preencha o formulário.</DialogDescription>
        </DialogHeader>
        <RadioGroup
          value={family}
          onValueChange={(v) => setFamily(v as Family)}
          className="grid grid-cols-4 gap-2"
        >
          {(["physical", "cbot", "basis", "fx"] as const).map((f) => (
            <label
              key={f}
              className="hover:bg-accent flex cursor-pointer items-center justify-center gap-2 rounded-md border px-2 py-3 text-sm"
            >
              <RadioGroupItem value={f} />
              <span className="capitalize">{f}</span>
            </label>
          ))}
        </RadioGroup>
        {family === "physical" && <PhysicalForm onClose={() => onOpenChange(false)} />}
        {family === "cbot" && <CbotForm onClose={() => onOpenChange(false)} />}
        {family === "basis" && <BasisForm onClose={() => onOpenChange(false)} />}
        {family === "fx" && <FxForm onClose={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  );
}

function PhysicalForm({ onClose }: { onClose: () => void }) {
  const create = useCreatePhysicalFrame();
  const { register, handleSubmit, setValue, watch, formState } = useForm<PhysicalForm>({
    resolver: zodResolver(physicalSchema),
    defaultValues: { commodity: "soja", side: "buy" },
  });

  const onSubmit = handleSubmit(async (values) => {
    try {
      await create.mutateAsync({
        commodity: values.commodity,
        side: values.side,
        quantity_tons: values.quantity_tons,
        delivery_start: values.delivery_start,
        delivery_end: values.delivery_end,
        counterparty: values.counterparty || null,
        notes: values.notes || null,
      });
      toast.success("Frame físico criado.");
      onClose();
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  });

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-3">
        <Field label="Commodity">
          <Select value={watch("commodity")} onValueChange={(v) => v && setValue("commodity", v)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="soja">soja</SelectItem>
              <SelectItem value="milho">milho</SelectItem>
            </SelectContent>
          </Select>
        </Field>
        <Field label="Side">
          <Select value={watch("side")} onValueChange={(v) => v && setValue("side", v)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="buy">buy</SelectItem>
              <SelectItem value="sell">sell</SelectItem>
            </SelectContent>
          </Select>
        </Field>
      </div>
      <Field label="Tonelagem" error={formState.errors.quantity_tons?.message}>
        <Input type="number" step="0.0001" {...register("quantity_tons")} />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Entrega início" error={formState.errors.delivery_start?.message}>
          <Input type="date" {...register("delivery_start")} />
        </Field>
        <Field label="Entrega fim" error={formState.errors.delivery_end?.message}>
          <Input type="date" {...register("delivery_end")} />
        </Field>
      </div>
      <Field label="Contraparte">
        <Input {...register("counterparty")} />
      </Field>
      <Field label="Notas">
        <Textarea rows={2} {...register("notes")} />
      </Field>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose}>
          Cancelar
        </Button>
        <Button type="submit" disabled={create.isPending}>
          {create.isPending ? "Salvando…" : "Criar"}
        </Button>
      </DialogFooter>
    </form>
  );
}

function CbotForm({ onClose }: { onClose: () => void }) {
  const create = useCreateCbot();
  const { register, handleSubmit, setValue, watch, formState } = useForm<CbotForm>({
    resolver: zodResolver(cbotSchema),
    defaultValues: {
      commodity: "soja",
      instrument: "future",
      side: "buy",
    },
  });
  const instrument = watch("instrument");
  const isOption = instrument.endsWith("option");
  const isBarrier = instrument === "barrier_option";

  const onSubmit = handleSubmit(async (values) => {
    try {
      const clean = blankToUndef(values);
      await create.mutateAsync({
        commodity: clean.commodity,
        instrument: clean.instrument,
        side: clean.side,
        contract: clean.contract,
        quantity_contracts: clean.quantity_contracts,
        trade_date: clean.trade_date,
        trade_price: clean.trade_price,
        maturity_date: clean.maturity_date,
        option_type: clean.option_type ?? null,
        strike: clean.strike ?? null,
        barrier_type: clean.barrier_type ?? null,
        barrier_level: clean.barrier_level ?? null,
        rebate: clean.rebate ?? null,
        counterparty: clean.counterparty ?? null,
        notes: clean.notes ?? null,
      });
      toast.success("Derivativo CBOT criado.");
      onClose();
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  });

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-3">
        <Field label="Commodity">
          <Select value={watch("commodity")} onValueChange={(v) => v && setValue("commodity", v)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="soja">soja</SelectItem>
              <SelectItem value="milho">milho</SelectItem>
            </SelectContent>
          </Select>
        </Field>
        <Field label="Instrumento">
          <Select
            value={watch("instrument")}
            onValueChange={(v) => v && setValue("instrument", v as CbotForm["instrument"])}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="future">future</SelectItem>
              <SelectItem value="swap">swap</SelectItem>
              <SelectItem value="european_option">european_option</SelectItem>
              <SelectItem value="american_option">american_option</SelectItem>
              <SelectItem value="barrier_option">barrier_option</SelectItem>
            </SelectContent>
          </Select>
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Side">
          <Select value={watch("side")} onValueChange={(v) => v && setValue("side", v)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="buy">buy</SelectItem>
              <SelectItem value="sell">sell</SelectItem>
            </SelectContent>
          </Select>
        </Field>
        <Field label="Contrato" error={formState.errors.contract?.message}>
          <Input {...register("contract")} placeholder="ZSK26" />
        </Field>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <Field label="# contratos" error={formState.errors.quantity_contracts?.message}>
          <Input type="number" step="0.0001" {...register("quantity_contracts")} />
        </Field>
        <Field label="Preço (USc/bu)" error={formState.errors.trade_price?.message}>
          <Input type="number" step="0.0001" {...register("trade_price")} />
        </Field>
        <Field label="Data op." error={formState.errors.trade_date?.message}>
          <Input type="date" {...register("trade_date")} />
        </Field>
      </div>
      <Field label="Vencimento" error={formState.errors.maturity_date?.message}>
        <Input type="date" {...register("maturity_date")} />
      </Field>
      {isOption && (
        <div className="grid grid-cols-2 gap-3">
          <Field label="Option type">
            <Select
              value={watch("option_type") ?? ""}
              onValueChange={(v) => v && setValue("option_type", v as "call" | "put")}
            >
              <SelectTrigger>
                <SelectValue placeholder="escolha" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="call">call</SelectItem>
                <SelectItem value="put">put</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <Field label="Strike" error={formState.errors.strike?.message}>
            <Input type="number" step="0.0001" {...register("strike")} />
          </Field>
        </div>
      )}
      {isBarrier && (
        <div className="grid grid-cols-2 gap-3">
          <Field label="Barrier type">
            <Select
              value={watch("barrier_type") ?? ""}
              onValueChange={(v) =>
                v && setValue("barrier_type", v as NonNullable<CbotForm["barrier_type"]>)
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="escolha" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="up_and_in">up_and_in</SelectItem>
                <SelectItem value="up_and_out">up_and_out</SelectItem>
                <SelectItem value="down_and_in">down_and_in</SelectItem>
                <SelectItem value="down_and_out">down_and_out</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <Field label="Barrier level" error={formState.errors.barrier_level?.message}>
            <Input type="number" step="0.0001" {...register("barrier_level")} />
          </Field>
        </div>
      )}
      <Field label="Contraparte">
        <Input {...register("counterparty")} />
      </Field>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose}>
          Cancelar
        </Button>
        <Button type="submit" disabled={create.isPending}>
          {create.isPending ? "Salvando…" : "Criar"}
        </Button>
      </DialogFooter>
    </form>
  );
}

function BasisForm({ onClose }: { onClose: () => void }) {
  const create = useCreateBasis();
  const { register, handleSubmit, setValue, watch, formState } = useForm<BasisForm>({
    resolver: zodResolver(basisSchema),
    defaultValues: { commodity: "soja", side: "buy" },
  });

  const onSubmit = handleSubmit(async (values) => {
    try {
      await create.mutateAsync({
        commodity: values.commodity,
        side: values.side,
        quantity_tons: values.quantity_tons,
        trade_date: values.trade_date,
        basis_price: values.basis_price,
        delivery_date: values.delivery_date,
        reference_cbot_contract: values.reference_cbot_contract,
        counterparty: values.counterparty || null,
        notes: values.notes || null,
      });
      toast.success("Basis forward criado.");
      onClose();
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  });

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-3">
        <Field label="Commodity">
          <Select value={watch("commodity")} onValueChange={(v) => v && setValue("commodity", v)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="soja">soja</SelectItem>
              <SelectItem value="milho">milho</SelectItem>
            </SelectContent>
          </Select>
        </Field>
        <Field label="Side">
          <Select value={watch("side")} onValueChange={(v) => v && setValue("side", v)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="buy">buy</SelectItem>
              <SelectItem value="sell">sell</SelectItem>
            </SelectContent>
          </Select>
        </Field>
      </div>
      <Field label="Tonelagem" error={formState.errors.quantity_tons?.message}>
        <Input type="number" step="0.0001" {...register("quantity_tons")} />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Basis (USD/bu)" error={formState.errors.basis_price?.message}>
          <Input type="number" step="0.0001" {...register("basis_price")} />
        </Field>
        <Field label="Contrato CBOT ref." error={formState.errors.reference_cbot_contract?.message}>
          <Input {...register("reference_cbot_contract")} placeholder="ZSK26" />
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Data op." error={formState.errors.trade_date?.message}>
          <Input type="date" {...register("trade_date")} />
        </Field>
        <Field label="Entrega" error={formState.errors.delivery_date?.message}>
          <Input type="date" {...register("delivery_date")} />
        </Field>
      </div>
      <Field label="Contraparte">
        <Input {...register("counterparty")} />
      </Field>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose}>
          Cancelar
        </Button>
        <Button type="submit" disabled={create.isPending}>
          {create.isPending ? "Salvando…" : "Criar"}
        </Button>
      </DialogFooter>
    </form>
  );
}

function FxForm({ onClose }: { onClose: () => void }) {
  const create = useCreateFx();
  const { register, handleSubmit, setValue, watch, formState } = useForm<FxForm>({
    resolver: zodResolver(fxSchema),
    defaultValues: { instrument: "ndf", side: "buy" },
  });
  const instrument = watch("instrument");
  const isOption = instrument.endsWith("option");
  const isBarrier = instrument === "barrier_option";

  const onSubmit = handleSubmit(async (values) => {
    try {
      const clean = blankToUndef(values);
      await create.mutateAsync({
        instrument: clean.instrument,
        side: clean.side,
        notional_usd: clean.notional_usd,
        trade_date: clean.trade_date,
        trade_rate: clean.trade_rate,
        maturity_date: clean.maturity_date,
        option_type: clean.option_type ?? null,
        strike: clean.strike ?? null,
        barrier_type: clean.barrier_type ?? null,
        barrier_level: clean.barrier_level ?? null,
        rebate: clean.rebate ?? null,
        counterparty: clean.counterparty ?? null,
        notes: clean.notes ?? null,
      });
      toast.success("Derivativo FX criado.");
      onClose();
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  });

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-3">
        <Field label="Instrumento">
          <Select
            value={watch("instrument")}
            onValueChange={(v) => v && setValue("instrument", v as FxForm["instrument"])}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ndf">ndf</SelectItem>
              <SelectItem value="swap">swap</SelectItem>
              <SelectItem value="european_option">european_option</SelectItem>
              <SelectItem value="american_option">american_option</SelectItem>
              <SelectItem value="barrier_option">barrier_option</SelectItem>
            </SelectContent>
          </Select>
        </Field>
        <Field label="Side">
          <Select value={watch("side")} onValueChange={(v) => v && setValue("side", v)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="buy">buy</SelectItem>
              <SelectItem value="sell">sell</SelectItem>
            </SelectContent>
          </Select>
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Notional USD" error={formState.errors.notional_usd?.message}>
          <Input type="number" step="0.01" {...register("notional_usd")} />
        </Field>
        <Field label="Taxa (BRL/USD)" error={formState.errors.trade_rate?.message}>
          <Input type="number" step="0.0001" {...register("trade_rate")} />
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Data op." error={formState.errors.trade_date?.message}>
          <Input type="date" {...register("trade_date")} />
        </Field>
        <Field label="Vencimento" error={formState.errors.maturity_date?.message}>
          <Input type="date" {...register("maturity_date")} />
        </Field>
      </div>
      {isOption && (
        <div className="grid grid-cols-2 gap-3">
          <Field label="Option type">
            <Select
              value={watch("option_type") ?? ""}
              onValueChange={(v) => v && setValue("option_type", v as "call" | "put")}
            >
              <SelectTrigger>
                <SelectValue placeholder="escolha" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="call">call</SelectItem>
                <SelectItem value="put">put</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <Field label="Strike" error={formState.errors.strike?.message}>
            <Input type="number" step="0.0001" {...register("strike")} />
          </Field>
        </div>
      )}
      {isBarrier && (
        <div className="grid grid-cols-2 gap-3">
          <Field label="Barrier type">
            <Select
              value={watch("barrier_type") ?? ""}
              onValueChange={(v) =>
                v && setValue("barrier_type", v as NonNullable<FxForm["barrier_type"]>)
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="escolha" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="up_and_in">up_and_in</SelectItem>
                <SelectItem value="up_and_out">up_and_out</SelectItem>
                <SelectItem value="down_and_in">down_and_in</SelectItem>
                <SelectItem value="down_and_out">down_and_out</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <Field label="Barrier level" error={formState.errors.barrier_level?.message}>
            <Input type="number" step="0.0001" {...register("barrier_level")} />
          </Field>
        </div>
      )}
      <Field label="Contraparte">
        <Input {...register("counterparty")} />
      </Field>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose}>
          Cancelar
        </Button>
        <Button type="submit" disabled={create.isPending}>
          {create.isPending ? "Salvando…" : "Criar"}
        </Button>
      </DialogFooter>
    </form>
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
