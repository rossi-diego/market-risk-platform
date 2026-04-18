"use client";

import { AlertCircle, CheckCircle2, FileSpreadsheet, Upload } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ProblemDetailsError } from "@/lib/api/fetcher";
import {
  type ImportPreviewResponse,
  useImportCommit,
  useImportPreview,
} from "@/lib/api/hooks/use-imports";

export default function ImportPositionsPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);

  const previewMutation = useImportPreview();
  const commitMutation = useImportCommit();

  const dropzone = useDropzone({
    accept: {
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
      "application/vnd.ms-excel": [".xls"],
    },
    multiple: false,
    onDrop: async ([dropped]) => {
      if (!dropped) return;
      setFile(dropped);
      setPreview(null);
      try {
        const result = await previewMutation.mutateAsync(dropped);
        setPreview(result);
      } catch (err) {
        toast.error(
          err instanceof ProblemDetailsError
            ? (err.problem.title ?? "Falha no preview")
            : err instanceof Error
              ? err.message
              : "Erro desconhecido",
        );
      }
    },
  });

  const onCommit = async () => {
    if (!file) return;
    if (preview && preview.invalid_count > 0) {
      toast.error("Corrija os erros antes de commit.");
      return;
    }
    const importId = crypto.randomUUID();
    try {
      const result = await commitMutation.mutateAsync({ file, importId });
      toast.success(
        result.status === "already_applied"
          ? "Import já havia sido aplicado (idempotente)."
          : `Import commitado: ${JSON.stringify(result.inserted)}`,
      );
      router.push("/positions");
    } catch (err) {
      toast.error(
        err instanceof ProblemDetailsError
          ? (err.problem.title ?? "Falha no commit")
          : err instanceof Error
            ? err.message
            : "Erro desconhecido",
      );
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Importar posições</h1>
        <p className="text-muted-foreground text-sm">
          Suba um .xlsx com as abas <code>physical_frames</code>, <code>physical_fixations</code>,{" "}
          <code>cbot</code>, <code>basis</code>, <code>fx</code>. Preview valida as linhas sem
          gravar; commit aplica em uma transação atômica (idempotente pelo import_id).
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>1. Upload</CardTitle>
        </CardHeader>
        <CardContent>
          <div
            {...dropzone.getRootProps()}
            className={`cursor-pointer rounded-md border-2 border-dashed p-8 text-center transition-colors ${
              dropzone.isDragActive ? "bg-accent" : "bg-muted/20 hover:bg-muted/40"
            }`}
          >
            <input {...dropzone.getInputProps()} />
            <Upload className="text-muted-foreground mx-auto mb-2 size-6" />
            <p className="text-sm font-medium">Arraste seu .xlsx aqui ou clique para selecionar</p>
            <p className="text-muted-foreground mt-1 text-xs">
              Precisa de um modelo?{" "}
              <a
                href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"}/imports/template`}
                className="text-foreground underline"
                download
              >
                Baixar template
              </a>
            </p>
          </div>
          {file && (
            <p className="text-muted-foreground mt-3 text-sm">
              <FileSpreadsheet className="mr-1 inline size-4" />
              {file.name} ({(file.size / 1024).toFixed(1)} KB)
            </p>
          )}
        </CardContent>
      </Card>

      {preview && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {preview.invalid_count === 0 ? (
                <CheckCircle2 className="size-5 text-green-500" />
              ) : (
                <AlertCircle className="text-destructive size-5" />
              )}
              2. Preview: {preview.valid_count} válidas · {preview.invalid_count} inválidas
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <ul className="text-sm">
              {Object.entries(preview.rows_by_sheet).map(([sheet, count]) => (
                <li key={sheet} className="flex justify-between border-b py-1">
                  <code>{sheet}</code>
                  <span>{count}</span>
                </li>
              ))}
            </ul>
            {preview.errors.length > 0 && (
              <div className="text-destructive flex flex-col gap-2 text-xs">
                <p className="font-semibold">Erros ({preview.errors.length})</p>
                <ul className="max-h-48 overflow-y-auto">
                  {preview.errors.slice(0, 50).map((e, idx) => (
                    <li key={`${e.sheet}-${e.row_index}-${idx}`} className="rounded border p-2">
                      <code>
                        {e.sheet} · linha {e.row_index}
                      </code>
                      <pre className="mt-1 text-[11px] whitespace-pre-wrap">
                        {JSON.stringify(e.errors, null, 2)}
                      </pre>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div className="flex justify-end gap-2">
              <Button
                onClick={onCommit}
                disabled={preview.invalid_count > 0 || commitMutation.isPending}
              >
                {commitMutation.isPending ? "Commitando…" : `Commit ${preview.valid_count} linhas`}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
