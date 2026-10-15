import type { Metadata, Viewport } from "next";
import { Montserrat } from "next/font/google";
import { AppShell } from "@/components/app-shell";
import "./globals.css";

const montserrat = Montserrat({
  variable: "--font-main",
  subsets: ["latin", "cyrillic"],
  weight: ["400", "500", "600", "700", "800"],
});

export const metadata: Metadata = {
  title: { default: "Chess Review", template: "%s — Chess Review" },
  description: "Разбор шахматных партий на Stockfish с объяснениями ошибок",
};

export const viewport: Viewport = { themeColor: "#2c2925" };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ru" className={`${montserrat.variable} h-full antialiased`}>
      <body className="min-h-full">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
