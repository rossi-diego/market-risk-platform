"use client";

import { FileSpreadsheet, Plus } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { PositionCreateDialog } from "@/components/positions/dialogs/position-create-dialog";
import { BasisTable } from "@/components/positions/tables/basis-table";
import { CbotTable } from "@/components/positions/tables/cbot-table";
import { FxTable } from "@/components/positions/tables/fx-table";
import { PhysicalFramesTable } from "@/components/positions/tables/physical-frames-table";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

type TabValue = "physical" | "cbot" | "basis" | "fx";
const VALID: TabValue[] = ["physical", "cbot", "basis", "fx"];

export default function PositionsPage() {
  return (
    <Suspense fallback={null}>
      <PositionsInner />
    </Suspense>
  );
}

function PositionsInner() {
  const router = useRouter();
  const search = useSearchParams();
  const requested = search.get("tab");
  const initialTab: TabValue =
    requested && (VALID as string[]).includes(requested) ? (requested as TabValue) : "physical";

  const [tab, setTab] = useState<TabValue>(initialTab);
  const [createOpen, setCreateOpen] = useState(false);

  const onTabChange = (next: string) => {
    const value = next as TabValue;
    setTab(value);
    const params = new URLSearchParams(search.toString());
    params.set("tab", value);
    router.replace(`/positions?${params.toString()}`, { scroll: false });
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Posições</h1>
          <p className="text-muted-foreground text-sm">
            CRUD das 4 famílias de instrumento. Use <kbd>Cmd/Ctrl + K</kbd> para o palette de
            comandos.
          </p>
        </div>
        <div className="flex gap-2">
          <Link
            href="/positions/import"
            className="border-input hover:bg-accent inline-flex h-9 items-center gap-2 rounded-md border px-4 text-sm"
          >
            <FileSpreadsheet className="size-4" /> Importar
          </Link>
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="size-4" /> Nova posição
          </Button>
        </div>
      </div>

      <Tabs value={tab} onValueChange={onTabChange}>
        <TabsList>
          <TabsTrigger value="physical">Physical</TabsTrigger>
          <TabsTrigger value="cbot">CBOT</TabsTrigger>
          <TabsTrigger value="basis">Basis</TabsTrigger>
          <TabsTrigger value="fx">FX</TabsTrigger>
        </TabsList>
        <TabsContent value="physical" className="mt-4">
          <PhysicalFramesTable />
        </TabsContent>
        <TabsContent value="cbot" className="mt-4">
          <CbotTable />
        </TabsContent>
        <TabsContent value="basis" className="mt-4">
          <BasisTable />
        </TabsContent>
        <TabsContent value="fx" className="mt-4">
          <FxTable />
        </TabsContent>
      </Tabs>

      <PositionCreateDialog open={createOpen} onOpenChange={setCreateOpen} initialFamily={tab} />
    </div>
  );
}
