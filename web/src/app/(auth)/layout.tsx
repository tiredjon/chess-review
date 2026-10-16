import { GuestOnly } from "@/components/auth/gates";
import { AuthFrame } from "@/components/auth/auth-frame";

/** Вход и регистрация: без навигации, карточка по центру. */
export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <GuestOnly>
      <AuthFrame>{children}</AuthFrame>
    </GuestOnly>
  );
}
