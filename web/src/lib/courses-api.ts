// Клиент API курсов (сессия 13.4, контракт — SPEC «Сессия 13»): каталог линий, «Мои курсы»,
// курс с деревом и идеями. Типы дерева — зеркало `backend/app/courses/types.py` и
// `backend/app/plans/types.py`; формы ответов (обёртка каталога, поля курса) сверены с 13.4.
import type { OpeningNode } from "@/components/openings/types";
import { request } from "./api";
import type { Lang } from "./i18n";
import type { Color } from "./types";

// --- Идеи позиции (app/plans/types.py) ---

export type Side = Color;

export type PawnBreak = {
  side: Side;
  uci: string;
  /** Только при `legal_now`. */
  san: string | null;
  /** Клетка пешки, по которой бьёт прорыв. */
  target: string;
  legal_now: boolean;
};

export type Outpost = { side: Side; square: string };

export type WeaknessKind = "isolated" | "backward" | "doubled" | "hanging" | "hole" | "passed";
export type Weakness = { side: Side; square: string; kind: WeaknessKind };

export type Idea = { key: string; side: Side; params: Record<string, string> };

export type PositionIdeas = {
  structures: string[];
  ideas: Idea[];
  breaks: PawnBreak[];
  outposts: Outpost[];
  weaknesses: Weakness[];
  open_files: string[];
  half_open_files: Partial<Record<Side, string[]>>;
};

export type RenderedIdea = { key: string; side: Side; text: string };

export type RenderedIdeas = {
  structures: string[];
  structure_title: string | null;
  structure_summary: string | null;
  ideas: RenderedIdea[];
};

// --- Дерево курса (app/courses/types.py) ---

export type MoveStats = {
  source: "masters" | "lichess";
  games: number;
  white: number;
  draws: number;
  black: number;
  average_rating: number | null;
};

/** Оценка позиции узла, с точки зрения белых: ровно одно из cp / mate. */
export type NodeEval = { cp: number | null; mate: number | null; depth: number; best_uci: string | null };

export type KeyMoment = "book_exit" | "structure" | "line_end";

export type CourseNode = OpeningNode & {
  /** Ход ученика из основной линии курса. */
  main: boolean;
  /** У ходов соперника — доля среди ответов мастеров. */
  weight: number;
  stats: MoveStats | null;
  eval: NodeEval | null;
  ideas: PositionIdeas | null;
  /** Почему узел ключевой (там же есть `ideas`). Сборщик может прислать и неизвестное значение. */
  key_moment: KeyMoment | string | null;
};

export type ModelGame = {
  id: string;
  node_id: number;
  white: string;
  black: string;
  white_rating: number | null;
  black_rating: number | null;
  year: number | null;
  result: string;
  /** PGN; у партий из книг — с комментариями автора (на английском). */
  pgn: string;
  /** "masters" — база мастеров Lichess, "book" — партия из открытой книги. Старые ответы — без поля. */
  source?: "masters" | "book";
  /** Автор комментариев и название книги — у партий из книг. */
  annotator?: string | null;
  book?: string | null;
};

export type CourseTree = {
  version: number;
  color: Color;
  /** Узел, где кончается исходная линия; дальше — «дальше теории». */
  line_end: number;
  nodes: CourseNode[];
  model_games: ModelGame[];
};

// --- Курсы ---

export type CourseStatus = "queued" | "building" | "ready" | "failed";
export type CourseSource = "catalog" | "repertoire";

export type CourseOut = {
  id: string;
  name: string;
  eco: string | null;
  color: Color;
  line_uci: string[];
  /** SAN тех же ходов. */
  line_san: string[];
  source: CourseSource;
  status: CourseStatus;
  /** 0…100 — индикатор сборки. */
  progress: number;
  /** Код ошибки сборки (словарь `errors.codes`), при `failed`. */
  error_code: string | null;
  added_at: string;
  last_studied_at: string | null;
  built_at: string | null;
};

export type CourseDetail = CourseOut & {
  /** Есть при `ready`. */
  tree: CourseTree | null;
  /** Тексты идей узлов на языке запроса: id узла (строкой) → тексты. */
  ideas_text: Record<string, RenderedIdeas>;
};

export const isBuilding = (course: Pick<CourseOut, "status">) =>
  course.status === "queued" || course.status === "building";

// --- Каталог ---

export type CatalogLine = { name: string; eco: string; uci: string[]; pgn: string };
export type CatalogVariation = { name: string; lines: CatalogLine[] };
export type CatalogFamily = { name: string; variations: CatalogVariation[] };
export type Catalog = { families: CatalogFamily[] };

/** Каталог принимается и голым массивом семейств — на случай, если 13.4 отдаст его без обёртки. */
const normalizeCatalog = (raw: Catalog | CatalogFamily[]): CatalogFamily[] =>
  Array.isArray(raw) ? raw : (raw.families ?? []);

export const coursesApi = {
  catalog: () => request<Catalog | CatalogFamily[]>("/courses/catalog").then(normalizeCatalog),
  list: () => request<CourseOut[]>("/courses"),
  course: (id: string, lang: Lang) => request<CourseDetail>(`/courses/${encodeURIComponent(id)}?lang=${lang}`),
  /** Идемпотентно по ключу (цвет + линия): повтор вернёт тот же курс (200), новый — 202;
   * упавший курс тем же запросом ставится в очередь заново. */
  create: (body: { line_uci: string[]; color: Color; source: CourseSource; name?: string }) =>
    request<CourseOut>("/courses", { method: "POST", body: JSON.stringify(body) }),
  remove: (id: string) => request<null>(`/courses/${encodeURIComponent(id)}`, { method: "DELETE" }),
};
