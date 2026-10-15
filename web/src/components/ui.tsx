import type { ButtonHTMLAttributes, ReactNode } from "react";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "green" | "raised";
  size?: "sm" | "md" | "lg";
};

/** Объёмная кнопка: зелёная — главное действие, тёмная — остальные. */
export function Button({ variant = "green", size = "md", className = "", ...props }: ButtonProps) {
  const look =
    variant === "green"
      ? "bg-green text-white shadow-[0_4px_0_0_var(--green-edge)] hover:bg-green-hover"
      : "bg-raised text-soft shadow-[0_3px_0_0_rgba(0,0,0,0.35)] hover:bg-raised-hover hover:text-ink";
  const dims = { sm: "min-h-9 px-3 text-sm", md: "min-h-10 px-4 text-[15px]", lg: "min-h-14 px-6 text-xl" }[size];
  return (
    <button
      type="button"
      {...props}
      className={`inline-flex items-center justify-center gap-2 rounded-lg font-bold transition-[transform,box-shadow] active:translate-y-[2px] active:shadow-none disabled:cursor-not-allowed disabled:opacity-50 disabled:active:translate-y-0 ${look} ${dims} ${className}`}
    />
  );
}

/** Переключатель-чип (как выбор контроля времени). */
export function Chip({
  active,
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { active: boolean }) {
  return (
    <button
      type="button"
      {...props}
      className={`min-h-11 rounded-lg px-3 text-sm font-semibold ${
        active
          ? "bg-raised text-ink ring-2 ring-green ring-inset"
          : "bg-raised/60 text-soft hover:bg-raised hover:text-ink"
      } ${className}`}
    />
  );
}

export function Panel({ title, children, className = "", aside }: { title?: ReactNode; children: ReactNode; className?: string; aside?: ReactNode }) {
  return (
    <section className={`rounded-xl bg-panel p-4 sm:p-5 ${className}`}>
      {title && (
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-lg font-bold">{title}</h2>
          {aside}
        </div>
      )}
      {children}
    </section>
  );
}

export function ErrorText({ children }: { children: ReactNode }) {
  if (!children) return null;
  return (
    <p role="alert" className="text-sm font-medium text-danger">
      {children}
    </p>
  );
}
