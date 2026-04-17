"use client";

import { Activity, FileSpreadsheet, LayoutDashboard, LogOut, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { PositionCreateDialog } from "@/components/positions/dialogs/position-create-dialog";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { createClient } from "@/lib/supabase/client";

type Family = "physical" | "cbot" | "basis" | "fx";

export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [family, setFamily] = useState<Family>("physical");

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((v) => !v);
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, []);

  const openCreate = useCallback((f: Family) => {
    setFamily(f);
    setOpen(false);
    setCreateOpen(true);
  }, []);

  const goto = useCallback(
    (path: string) => {
      setOpen(false);
      router.push(path);
    },
    [router],
  );

  const signOut = useCallback(async () => {
    setOpen(false);
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  }, [router]);

  return (
    <>
      <CommandDialog open={open} onOpenChange={setOpen}>
        <CommandInput placeholder="Digite um comando ou pesquise…" />
        <CommandList>
          <CommandEmpty>Nenhum resultado.</CommandEmpty>
          <CommandGroup heading="Nova posição">
            <CommandItem onSelect={() => openCreate("physical")}>
              <Plus /> Frame físico
            </CommandItem>
            <CommandItem onSelect={() => openCreate("cbot")}>
              <Plus /> Derivativo CBOT
            </CommandItem>
            <CommandItem onSelect={() => openCreate("basis")}>
              <Plus /> Basis forward
            </CommandItem>
            <CommandItem onSelect={() => openCreate("fx")}>
              <Plus /> Derivativo FX
            </CommandItem>
          </CommandGroup>
          <CommandGroup heading="Navegação">
            <CommandItem onSelect={() => goto("/dashboard")}>
              <LayoutDashboard /> Dashboard
            </CommandItem>
            <CommandItem onSelect={() => goto("/positions")}>
              <Activity /> Posições
            </CommandItem>
            <CommandItem onSelect={() => goto("/positions/import")}>
              <FileSpreadsheet /> Importar posições
            </CommandItem>
          </CommandGroup>
          <CommandGroup heading="Sessão">
            <CommandItem onSelect={signOut}>
              <LogOut /> Sair
            </CommandItem>
          </CommandGroup>
        </CommandList>
      </CommandDialog>
      <PositionCreateDialog open={createOpen} onOpenChange={setCreateOpen} initialFamily={family} />
    </>
  );
}
