import type { Color } from "@/lib/types";

/** Квадрат-аватар: первая буква ника на цвете стороны. */
export function PlayerAvatar({ name, color, size = 40 }: { name: string; color: Color; size?: number }) {
  return (
    <span
      aria-hidden
      className={`inline-flex shrink-0 items-center justify-center rounded-md font-extrabold ${
        color === "white" ? "bg-[#ebe6de] text-[#3b3833]" : "bg-[#4b4741] text-[#ebe6de]"
      }`}
      style={{ width: size, height: size, fontSize: size * 0.45 }}
    >
      {name.trim().charAt(0).toUpperCase() || "?"}
    </span>
  );
}

/** Маленький квадрат цвета стороны (как в таблицах). */
export function ColorSquare({ color }: { color: Color }) {
  return (
    <span
      aria-label={color === "white" ? "белые" : "чёрные"}
      role="img"
      className={`inline-block h-3.5 w-3.5 shrink-0 rounded-[3px] border-2 ${
        color === "white" ? "border-[#ebe6de] bg-[#ebe6de]" : "border-muted bg-transparent"
      }`}
    />
  );
}
