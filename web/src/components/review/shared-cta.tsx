"use client";

import Link from "next/link";
import { useAuth } from "@/components/auth/auth-provider";
import { useI18n } from "@/lib/i18n/use-i18n";

/** Шапка публичного разбора: гостю — регистрация, вошедшему — к своим партиям. */
export function SharedCta() {
  const { t } = useI18n();
  const { status } = useAuth();
  const authed = status === "authed";
  return (
    <Link
      href={authed ? "/" : "/register"}
      className="rounded-lg bg-green px-3 py-1.5 text-sm font-extrabold text-white shadow-[0_3px_0_0_rgba(0,0,0,0.3)] hover:brightness-110"
    >
      {authed ? t.common.titles.home : t.review.shared.cta}
    </Link>
  );
}
