import { AppShell } from "@/components/app-shell";
import { RequireAuth } from "@/components/auth/gates";

/** Страницы за входом: навигация слева (на телефоне — сверху) и содержимое. */
export default function AppLayout({ children }: LayoutProps<"/">) {
  return (
    <RequireAuth>
      <AppShell>{children}</AppShell>
    </RequireAuth>
  );
}
