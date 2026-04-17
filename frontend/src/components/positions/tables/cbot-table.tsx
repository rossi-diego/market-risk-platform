"use client";

import type { ColumnDef } from "@tanstack/react-table";

import { DataTable } from "@/components/positions/data-table";
import { Badge } from "@/components/ui/badge";
import { useCbotDerivatives, type CBOTDerivativeOut } from "@/lib/api/hooks/use-positions";
import { formatDate, formatPrice } from "@/lib/formatters";

const columns: ColumnDef<CBOTDerivativeOut>[] = [
  {
    accessorKey: "instrument",
    header: "Instrumento",
    cell: ({ row }) => <Badge variant="outline">{row.original.instrument}</Badge>,
  },
  { accessorKey: "commodity", header: "Commodity" },
  { accessorKey: "contract", header: "Contrato" },
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
    accessorKey: "quantity_contracts",
    header: "# contratos",
    cell: ({ row }) => row.original.quantity_contracts,
  },
  {
    accessorKey: "trade_price",
    header: "Preço (USc/bu)",
    cell: ({ row }) => formatPrice(row.original.trade_price),
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

export function CbotTable() {
  const query = useCbotDerivatives();
  return (
    <DataTable
      columns={columns}
      data={query.data ?? []}
      filterColumn="contract"
      filterPlaceholder="Filtrar por contrato…"
      isLoading={query.isLoading}
      emptyState={
        <span className="text-muted-foreground text-sm">
          Nenhum derivativo CBOT. Crie um em &quot;Nova posição&quot;.
        </span>
      }
    />
  );
}
