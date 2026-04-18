"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { Method } from "@/lib/api/hooks/use-risk";

import { useRiskPortfolio } from "./portfolio-store";

const CONFIDENCES = [
  { label: "90%", value: 0.9 },
  { label: "95%", value: 0.95 },
  { label: "97.5%", value: 0.975 },
  { label: "99%", value: 0.99 },
];

export function RiskControls({ compact = false }: { compact?: boolean }) {
  const state = useRiskPortfolio();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium">Controles</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="grid grid-cols-3 gap-3">
          <div className="flex flex-col gap-1">
            <Label className="text-xs">Método</Label>
            <Tabs value={state.method} onValueChange={(v) => state.setMethod(v as Method)}>
              <TabsList>
                <TabsTrigger value="historical">Hist</TabsTrigger>
                <TabsTrigger value="parametric">Param</TabsTrigger>
                <TabsTrigger value="monte_carlo">MC</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
          <div className="flex flex-col gap-1">
            <Label className="text-xs">Confiança</Label>
            <Select
              value={String(state.confidence)}
              onValueChange={(v) => v && state.setConfidence(Number(v))}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CONFIDENCES.map((c) => (
                  <SelectItem key={c.value} value={String(c.value)}>
                    {c.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <Label className="text-xs">Horizonte (dias)</Label>
            <Tabs
              value={String(state.horizonDays)}
              onValueChange={(v) => state.setHorizonDays(Number(v))}
            >
              <TabsList>
                <TabsTrigger value="1">1d</TabsTrigger>
                <TabsTrigger value="5">5d</TabsTrigger>
                <TabsTrigger value="10">10d</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
        </div>
        {!compact && (
          <div className="grid grid-cols-3 gap-3">
            <WeightInput label="ZS=F (soja CBOT)" instrument="ZS=F" />
            <WeightInput label="ZC=F (milho CBOT)" instrument="ZC=F" />
            <WeightInput label="USDBRL=X (FX)" instrument="USDBRL=X" />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function WeightInput({
  label,
  instrument,
}: {
  label: string;
  instrument: "ZS=F" | "ZC=F" | "USDBRL=X";
}) {
  const weight = useRiskPortfolio((s) => s.weights[instrument]);
  const setWeight = useRiskPortfolio((s) => s.setWeight);
  return (
    <div className="flex flex-col gap-1">
      <Label className="text-xs">{label} · peso BRL</Label>
      <Input
        type="number"
        step="10"
        value={weight}
        onChange={(e) => setWeight(instrument, e.target.value)}
      />
    </div>
  );
}
