"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { createClient } from "@/lib/supabase/client";

const schema = z.object({
  email: z.string().email({ message: "E-mail inválido" }),
  password: z.string().min(8, { message: "Senha mínima: 8 caracteres" }),
});
type FormValues = z.infer<typeof schema>;

export default function SignupPage() {
  const [formError, setFormError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async ({ email, password }: FormValues) => {
    setFormError(null);
    setSubmitting(true);
    try {
      const supabase = createClient();
      const { error } = await supabase.auth.signUp({ email, password });
      if (error) {
        setFormError(error.message);
        return;
      }
      setSubmitted(true);
      toast.success("Conta criada — confira o e-mail para confirmar.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Criar conta</CardTitle>
        <CardDescription>Cadastre-se para acessar o painel de risco de mercado.</CardDescription>
      </CardHeader>
      <CardContent>
        {submitted ? (
          <div className="flex flex-col gap-4" role="status" aria-live="polite">
            <p>
              Enviamos um e-mail de confirmação. Siga o link para ativar sua conta e depois volte
              aqui para entrar.
            </p>
            <Link
              href="/login"
              className="border-input bg-background hover:bg-accent inline-flex h-9 items-center justify-center rounded-md border px-4 py-2 text-sm font-medium transition-colors"
            >
              Voltar para login
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
            <div className="flex flex-col gap-2">
              <Label htmlFor="email">E-mail</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                {...register("email")}
                aria-invalid={errors.email ? "true" : "false"}
              />
              {errors.email && (
                <p className="text-destructive text-sm" role="alert">
                  {errors.email.message}
                </p>
              )}
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="password">Senha</Label>
              <Input
                id="password"
                type="password"
                autoComplete="new-password"
                {...register("password")}
                aria-invalid={errors.password ? "true" : "false"}
              />
              {errors.password && (
                <p className="text-destructive text-sm" role="alert">
                  {errors.password.message}
                </p>
              )}
            </div>
            {formError && (
              <p className="text-destructive text-sm" role="alert">
                {formError}
              </p>
            )}
            <Button type="submit" disabled={submitting}>
              {submitting ? "Enviando…" : "Criar conta"}
            </Button>
          </form>
        )}
        <p className="text-muted-foreground mt-4 text-center text-sm">
          Já tem conta?{" "}
          <Link href="/login" className="text-foreground underline">
            Entrar
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}
