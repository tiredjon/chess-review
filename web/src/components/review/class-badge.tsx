import type { ReactNode } from "react";
import { CLASS_META, type ClassKey } from "@/lib/classes";

// Белые символы на цветном круге, viewBox 0 0 24 24.
const text = (value: string, size = 13) => (
  <text
    x="12"
    y="12.5"
    textAnchor="middle"
    dominantBaseline="central"
    fontSize={size}
    fontWeight={800}
    fontFamily="var(--font-main), sans-serif"
    letterSpacing={value.length > 1 ? -1 : 0}
    fill="white"
  >
    {value}
  </text>
);

const GLYPHS: Record<ClassKey, ReactNode> = {
  brilliant: text("!!", 12),
  great: text("!", 14),
  best: <path fill="white" d="m12 5.2 2 4.3 4.7.5-3.5 3.2 1 4.6L12 15.4l-4.2 2.4 1-4.6L5.3 10l4.7-.5z" />,
  excellent: (
    <path
      fill="white"
      d="M7 11h2.2v6.5H7zM10.3 11.2l2.3-4.2c.8-.1 1.5.6 1.3 1.5l-.5 2h3.3c.8 0 1.4.8 1.2 1.6l-1 4.3c-.2.6-.7 1.1-1.4 1.1h-5.2z"
    />
  ),
  good: <path fill="none" stroke="white" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" d="m7.3 12.4 3.1 3 6.3-6.6" />,
  book: (
    <path
      fill="white"
      d="M5.5 7.3c2.2-.6 4.4-.3 5.8.9v9.5c-1.4-1-3.6-1.3-5.8-.7zM18.5 7.3c-2.2-.6-4.4-.3-5.8.9v9.5c1.4-1 3.6-1.3 5.8-.7z"
    />
  ),
  forced: <path fill="none" stroke="white" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" d="M6.5 12h10m-3.5-4 4 4-4 4" />,
  inaccuracy: text("?!", 12),
  mistake: text("?", 14),
  miss: <path fill="none" stroke="white" strokeWidth="2.8" strokeLinecap="round" d="m8 8 8 8m0-8-8 8" />,
  blunder: text("??", 12),
};

/** Круглый значок класса хода: на доске, в списке ходов и в таблицах. */
export function ClassBadge({
  value,
  size = 18,
  title = true,
}: {
  value: ClassKey;
  /** Пиксели или CSS-длина («100%» — по ширине родителя). */
  size?: number | string;
  title?: boolean;
}) {
  const meta = CLASS_META[value];
  return (
    <svg
      role="img"
      aria-label={meta.label}
      viewBox="0 0 24 24"
      width={size}
      height={typeof size === "number" ? size : undefined}
      className="block shrink-0"
    >
      {title && <title>{meta.label}</title>}
      <circle cx="12" cy="12" r="12" fill={meta.color} />
      {GLYPHS[value]}
    </svg>
  );
}
