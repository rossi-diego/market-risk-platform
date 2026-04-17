"use client";

import type { ColumnDef } from "@tanstack/react-table";

import { DataTable } from "@/components/positions/data-table";
import { Badge } from "@/components/ui/badge";
import { useFxDerivatives, type FXDerivativeOut } from "@/lib/api/hooks/use-positions";
import { formatDate, formatPrice, formatUsd } from "@/lib/formatters";

const columns: ColumnDef<FXDerivativeOut>[] = [
  {
    accessorKey: "instrument",
    header: "Instrumento",
    cell: ({ row }) => <Badge variant="outline">{row.original.instrument}</Badge>,
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
    accessorKey: "notional_usd",
    header: "Notional",
    cell: ({ row }) => formatUsd(row.original.notional_usd),
  },
  {
    accessorKey: "trade_rate",
    header: "Taxa (BRL/USD)",
    cell: ({ row }) => formatPrice(row.original.trade_rate),
  },
  {
    accessorKey: "trade_date",
    header: "Data op.",
    cell: ({ row }) => formatDate(row.original.trade_date),
  },
  {
    accessorKey: "maturity_date",
    header: "Vencimento",
    cell: ({ row }) => formatDate(row.original.maturity_date),
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => <Badge variant="outline">{row.original.status}</Badge>,
  },
];

export function FxTable() {
  const query = useFxDerivatives();
  return (
    <DataTable
      columns={columns}
      data={query.data ?? []}
      filterColumn="instrument"
      filterPlaceholder="Filtrar por instrumento…"
      isLoading={query.isLoading}
      emptyState={<span className="text-muted-foreground text-sm">Nenhum derivativo FX.</span>}
    />
  );
}
