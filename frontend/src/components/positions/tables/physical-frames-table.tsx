"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useRouter } from "next/navigation";

import { DataTable } from "@/components/positions/data-table";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { usePhysicalFrames, type PhysicalFrameWithExposure } from "@/lib/api/hooks/use-positions";
import { formatDate, formatTons, ratio } from "@/lib/formatters";

function LegProgress({ label, locked, total }: { label: string; locked: string; total: string }) {
  const value = ratio(locked, total) * 100;
  return (
    <div className="flex flex-col gap-1" aria-label={`${label} locked ${locked} of ${total}`}>
      <span className="text-muted-foreground text-[10px] uppercase">{label}</span>
      <Progress value={value} className="h-1.5 w-24" />
    </div>
  );
}

const columns: ColumnDef<PhysicalFrameWithExposure>[] = [
  { accessorKey: "counterparty", header: "Contraparte" },
  {
    accessorKey: "commodity",
    header: "Commodity",
    cell: ({ row }) => <Badge variant="outline">{row.original.commodity}</Badge>,
  },
  {
    accessorKey: "side",
    header: "Side",
    cell: ({ row }) => (
      <Badge variant={row.original.side === "buy" ? "default" : "secondary"}>
        {row.original.side}
      </Badge>
    ),
  },
  {
    accessorKey: "quantity_tons",
    header: "Tonelagem",
    cell: ({ row }) => formatTons(row.original.quantity_tons),
  },
  {
    id: "delivery",
    header: "Entrega",
    cell: ({ row }) =>
      `${formatDate(row.original.delivery_start)} → ${formatDate(row.original.delivery_end)}`,
  },
  {
    id: "legs",
    header: "Legs locked",
    cell: ({ row }) => (
      <div className="flex gap-3">
        <LegProgress
          label="CBOT"
          locked={row.original.locked_cbot_tons}
          total={row.original.quantity_tons}
        />
        <LegProgress
          label="Basis"
          locked={row.original.locked_basis_tons}
          total={row.original.quantity_tons}
        />
        <LegProgress
          label="FX"
          locked={row.original.locked_fx_tons}
          total={row.original.quantity_tons}
        />
      </div>
    ),
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => <Badge variant="outline">{row.original.status}</Badge>,
  },
];

export function PhysicalFramesTable() {
  const router = useRouter();
  const query = usePhysicalFrames();

  return (
    <DataTable
      columns={columns}
      data={query.data ?? []}
      filterColumn="counterparty"
      filterPlaceholder="Filtrar por contraparte…"
      isLoading={query.isLoading}
      onRowClick={(row) => router.push(`/positions/frames/${row.id}`)}
      emptyState={
        <span className="text-muted-foreground text-sm">
          Nenhum frame físico. Crie um em &quot;Nova posição&quot;.
        </span>
      }
    />
  );
}
