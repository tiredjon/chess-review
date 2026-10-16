// Названия тактических мотивов и тем пазлов — словарь `common.motifs`.
import type { Dict } from "./i18n";

export const motifName = (t: Dict, type: string) => t.common.motifs[type] ?? type;
