"use client";

import type { ColumnDef } from "@tanstack/react-table";

import { DataTable } from "@/components/positions/data-table";
import { Badge } from "@/components/ui/badge";
import { useBasisForwards, type BasisForwardOut } from "@/lib/api/hooks/use-positions";
import { formatDate, formatPrice, formatTons } from "@/lib/formatters";

const columns: ColumnDef<BasisForwardOut>[] = [
  { accessorKey: "commodity", header: "Commodity" },
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
    accessorKey: "basis_price",
    header: "Basis (USD/bu)",
    cell: ({ row }) => formatPrice(row.original.basis_price),
  },
  { accessorKey: "reference_cbot_contract", header: "Contrato ref." },
  {
    accessorKey: "delivery_date",
    header: "Entrega",
    cell: ({ row }) => formatDate(row.original.delivery_date),
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => <Badge variant="outline">{row.original.status}</Badge>,
  },
];

export function BasisTable() {
  const query = useBasisForwards();
  return (
    <DataTable
      columns={columns}
      data={query.data ?? []}
      filterColumn="reference_cbot_contract"
      filterPlaceholder="Filtrar por contrato ref.…"
      isLoading={query.isLoading}
      emptyState={<span className="text-muted-foreground text-sm">Nenhum basis forward.</span>}
    />
  );
}
