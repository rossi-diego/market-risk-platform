"use client";

import { AlertCircle, CheckCircle2 } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useHealth } from "@/lib/api/hooks/use-health";

export default function HealthDebugPage() {
  const query = useHealth();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Backend health</h1>
        <p className="text-muted-foreground text-sm">
          Smoke test: the browser fetches <code>/api/v1/health</code> through the typed client.
        </p>
      </div>
      <Card>
        <CardHeader className="flex flex-row items-center gap-2">
          {query.isLoading ? (
            <Skeleton className="size-5 rounded-full" />
          ) : query.error ? (
            <AlertCircle className="text-destructive size-5" aria-hidden="true" />
          ) : (
            <CheckCircle2 className="size-5 text-green-500" aria-hidden="true" />
          )}
          <div>
            <CardTitle>API status</CardTitle>
            <CardDescription>
              {query.isLoading ? "carregando…" : query.error ? "offline" : "online"}
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          {query.isLoading ? (
            <Skeleton className="h-20 w-full" />
          ) : query.error ? (
            <pre className="text-destructive text-sm whitespace-pre-wrap">
              {String(query.error)}
            </pre>
          ) : (
            <pre className="bg-muted text-foreground rounded-md p-3 text-sm">
              {JSON.stringify(query.data, null, 2)}
            </pre>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
