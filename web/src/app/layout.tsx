import type { Metadata, Viewport } from "next";
import { Montserrat } from "next/font/google";
import { AuthProvider } from "@/components/auth/auth-provider";
import "./globals.css";

const montserrat = Montserrat({
  variable: "--font-main",
  subsets: ["latin", "cyrillic"],
  weight: ["400", "500", "600", "700", "800"],
});

// Заголовок вкладки на языке интерфейса ставит DocumentTitle (язык известен только в браузере);
// title в metadata нет: второй <title> от Next перебивал бы его.
export const metadata: Metadata = {
  description: "Chess game review on Stockfish · Разбор шахматных партий на Stockfish",
};

export const viewport: Viewport = { themeColor: "#2c2925" };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // Язык документа меняет lib/i18n/use-i18n.ts.
    <html lang="ru" className={`${montserrat.variable} h-full antialiased`} suppressHydrationWarning>
      <body className="min-h-full">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
