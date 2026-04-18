"use client";

import { Save, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { useRiskPortfolio } from "@/components/risk/portfolio-store";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { apiFetch, ProblemDetailsError } from "@/lib/api/fetcher";
import type { StressRow } from "@/lib/api/hooks/use-risk";
import {
  type ScenarioIn,
  type ScenarioOut,
  useCreateScenario,
  useDeleteScenario,
  useScenarioTemplates,
  useScenarios,
  useUpdateScenario,
} from "@/lib/api/hooks/use-scenarios";
import { formatSignedBRL } from "@/lib/formatters";

type SliderField =
  | "cbot_soja_shock_pct"
  | "cbot_milho_shock_pct"
  | "basis_soja_shock_pct"
  | "basis_milho_shock_pct"
  | "fx_shock_pct";

const SLIDERS: { field: SliderField; label: string }[] = [
  { field: "cbot_soja_shock_pct", label: "CBOT soja" },
  { field: "cbot_milho_shock_pct", label: "CBOT milho" },
  { field: "basis_soja_shock_pct", label: "Basis soja" },
  { field: "basis_milho_shock_pct", label: "Basis milho" },
  { field: "fx_shock_pct", label: "FX" },
];

const EMPTY_FORM = {
  name: "",
  description: "",
  cbot_soja_shock_pct: "0",
  cbot_milho_shock_pct: "0",
  basis_soja_shock_pct: "0",
  basis_milho_shock_pct: "0",
  fx_shock_pct: "0",
  is_historical: false,
  source_period: null,
} satisfies ScenarioIn;

export default function ScenariosPage() {
  const scenarios = useScenarios();
  const templates = useScenarioTemplates();
  const createScenario = useCreateScenario();
  const updateScenario = useUpdateScenario();
  const deleteScenario = useDeleteScenario();

  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<ScenarioIn>(EMPTY_FORM);

  const resetForm = () => {
    setEditingId(null);
    setForm(EMPTY_FORM);
  };

  const loadScenario = (s: ScenarioOut) => {
    setEditingId(s.id);
    setForm({
      name: s.name,
      description: s.description ?? null,
      cbot_soja_shock_pct: s.cbot_soja_shock_pct,
      cbot_milho_shock_pct: s.cbot_milho_shock_pct,
      basis_soja_shock_pct: s.basis_soja_shock_pct,
      basis_milho_shock_pct: s.basis_milho_shock_pct,
      fx_shock_pct: s.fx_shock_pct,
      is_historical: s.is_historical,
      source_period: s.source_period ?? null,
    });
  };

  const onSave = async () => {
    try {
      if (editingId) {
        await updateScenario.mutateAsync({ id: editingId, body: form });
        toast.success("Cenário atualizado.");
      } else {
        const row = await createScenario.mutateAsync(form);
        setEditingId(row.id);
        toast.success("Cenário criado.");
      }
    } catch (err) {
      toast.error(
        err instanceof ProblemDetailsError
          ? (err.problem.title ?? "Falha ao salvar")
          : err instanceof Error
            ? err.message
            : "Erro desconhecido",
      );
    }
  };

  const onDelete = async () => {
    if (!editingId) return;
    if (!window.confirm("Apagar este cenário?")) return;
    try {
      await deleteScenario.mutateAsync(editingId);
      toast.success("Cenário removido.");
      resetForm();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro desconhecido");
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Cenários</h1>
          <p className="text-muted-foreground text-sm">
            Templates oficiais + cenários personalizados. Shocks em fração (-0.5 a +0.5).
          </p>
        </div>
        <Button onClick={resetForm} variant="outline">
          Novo cenário
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-[2fr_3fr]">
        {/* LEFT — list */}
        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle>Templates históricos</CardTitle>
              <CardDescription>
                Built-ins: GFC, drought, COVID, Ukraine. Somente leitura.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {templates.isLoading ? (
                <Skeleton className="h-24 w-full" />
              ) : (
                templates.data?.map((t) => (
                  <div key={t.id} className="rounded-md border p-3">
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{t.name}</span>
                      <Badge variant="outline">template</Badge>
                    </div>
                    <p className="text-muted-foreground mt-1 text-xs">
                      {t.description ?? t.source_period ?? "cenário histórico"}
                    </p>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Meus cenários</CardTitle>
              <CardDescription>Cenários salvos pelo usuário atual.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {scenarios.isLoading ? (
                <Skeleton className="h-24 w-full" />
              ) : scenarios.data?.length === 0 ? (
                <p className="text-muted-foreground text-sm">Nenhum cenário salvo.</p>
              ) : (
                scenarios.data?.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => loadScenario(s)}
                    className={`hover:bg-accent rounded-md border p-3 text-left ${
                      editingId === s.id ? "border-primary" : ""
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{s.name}</span>
                      {s.is_historical && <Badge variant="outline">histórico</Badge>}
                    </div>
                    <p className="text-muted-foreground mt-1 text-xs">
                      {s.description ?? "sem descrição"}
                    </p>
                  </button>
                ))
              )}
            </CardContent>
          </Card>
        </div>

        {/* RIGHT — editor */}
        <Card>
          <CardHeader>
            <CardTitle>{editingId ? "Editar cenário" : "Novo cenário"}</CardTitle>
            <CardDescription>
              Ajuste os shocks. Preview atualiza conforme o portfólio configurado em
              &quot;Controles&quot;.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1">
                <Label>Nome</Label>
                <Input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
              </div>
              <div className="flex flex-col gap-1">
                <Label>Descrição</Label>
                <Input
                  value={form.description ?? ""}
                  onChange={(e) => setForm({ ...form, description: e.target.value || null })}
                />
              </div>
            </div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {SLIDERS.map(({ field, label }) => (
                <ShockRow
                  key={field}
                  label={label}
                  value={form[field] as string}
                  onChange={(next) => setForm({ ...form, [field]: next })}
                />
              ))}
            </div>
            <div className="flex flex-col gap-1">
              <Label>Notas adicionais</Label>
              <Textarea
                rows={2}
                value={form.source_period ?? ""}
                onChange={(e) => setForm({ ...form, source_period: e.target.value || null })}
                placeholder="Período-fonte / notas (opcional)"
              />
            </div>
            <PreviewPnL form={form} />
            <div className="flex flex-wrap justify-end gap-2">
              {editingId && (
                <Button variant="outline" onClick={onDelete}>
                  <Trash2 className="size-4" /> Apagar
                </Button>
              )}
              <Button
                onClick={onSave}
                disabled={!form.name || createScenario.isPending || updateScenario.isPending}
              >
                <Save className="size-4" />
                {editingId
                  ? updateScenario.isPending
                    ? "Atualizando…"
                    : "Atualizar"
                  : createScenario.isPending
                    ? "Salvando…"
                    : "Salvar"}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function ShockRow({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  const pct = Math.round(Number(value) * 10000) / 100;
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <Label className="text-sm">{label}</Label>
        <span className="text-muted-foreground text-xs">{pct.toFixed(2)}%</span>
      </div>
      <input
        type="range"
        min={-0.5}
        max={0.5}
        step={0.01}
        value={Number(value)}
        onChange={(e) => onChange(e.target.value)}
        className="accent-primary w-full"
        aria-label={`${label} shock (fraction)`}
      />
    </div>
  );
}

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

function PreviewPnL({ form }: { form: ScenarioIn }) {
  const state = useRiskPortfolio();
  const debouncedForm = useDebouncedValue(form, 250);
  const [preview, setPreview] = useState<StressRow | null>(null);
  const [error, setError] = useState<string | null>(null);

  const payload = useMemo(
    () => ({
      scenario: {
        name: debouncedForm.name || "preview",
        cbot_soja: debouncedForm.cbot_soja_shock_pct,
        cbot_milho: debouncedForm.cbot_milho_shock_pct,
        basis_soja: debouncedForm.basis_soja_shock_pct,
        basis_milho: debouncedForm.basis_milho_shock_pct,
        fx: debouncedForm.fx_shock_pct,
        source_period: debouncedForm.source_period ?? "inline",
      },
      exposure_tons_by_commodity: state.exposureTons,
      prices_current: state.pricesCurrent,
    }),
    [debouncedForm, state.exposureTons, state.pricesCurrent],
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const row = await apiFetch<StressRow>("/risk/stress/custom", {
          method: "POST",
          body: payload,
        });
        if (!cancelled) {
          setPreview(row);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "preview failed");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [payload]);

  return (
    <div className="rounded-md border p-3">
      <p className="text-muted-foreground text-xs uppercase">Preview P&L</p>
      {error ? (
        <p className="text-destructive text-sm">{error}</p>
      ) : preview ? (
        <>
          <p className="text-xl font-semibold">{formatSignedBRL(preview.total_pnl_brl)}</p>
          <div className="text-muted-foreground mt-1 grid grid-cols-3 gap-2 text-xs">
            <span>CBOT {formatSignedBRL(preview.per_leg_pnl.cbot)}</span>
            <span>Basis {formatSignedBRL(preview.per_leg_pnl.basis)}</span>
            <span>FX {formatSignedBRL(preview.per_leg_pnl.fx)}</span>
          </div>
        </>
      ) : (
        <Skeleton className="mt-1 h-6 w-40" />
      )}
    </div>
  );
}
