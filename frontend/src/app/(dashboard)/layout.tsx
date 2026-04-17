import { redirect } from "next/navigation";

import { AppSidebar } from "@/components/dashboard/app-sidebar";
import { DashboardBreadcrumbs } from "@/components/dashboard/dashboard-breadcrumbs";
import { UserMenu } from "@/components/dashboard/user-menu";
import { ThemeToggle } from "@/components/providers/theme-toggle";
import { Separator } from "@/components/ui/separator";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { createClient } from "@/lib/supabase/server";

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="bg-background sticky top-0 z-10 flex h-14 items-center gap-3 border-b px-4">
          <SidebarTrigger aria-label="Alternar sidebar" />
          <Separator orientation="vertical" className="h-5" />
          <div className="flex-1">
            <DashboardBreadcrumbs />
          </div>
          <ThemeToggle />
          <UserMenu email={user.email ?? ""} />
        </header>
        <main className="flex-1 p-6">{children}</main>
      </SidebarInset>
    </SidebarProvider>
  );
}
