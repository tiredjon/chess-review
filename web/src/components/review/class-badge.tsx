import { CLASS_META, type ClassKey } from "@/lib/classes";

/** Круглый значок класса хода: на доске, в списке ходов и в панели. */
export function ClassBadge({
  value,
  size = 18,
  title = true,
}: {
  value: ClassKey;
  size?: number;
  title?: boolean;
}) {
  const meta = CLASS_META[value];
  return (
    <span
      role="img"
      aria-label={meta.label}
      title={title ? meta.label : undefined}
      className="inline-flex shrink-0 items-center justify-center rounded-full font-bold leading-none text-white"
      style={{
        width: size,
        height: size,
        background: meta.color,
        fontSize: size * (meta.glyph.length > 1 ? 0.5 : 0.62),
        letterSpacing: meta.glyph.length > 1 ? "-0.04em" : undefined,
      }}
    >
      {meta.glyph}
    </span>
  );
}
