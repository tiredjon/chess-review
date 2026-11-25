// Фейковый API для разработки страниц курсов и тренажёра (сессия 13.7), пока бэкенда курсов
// (13.4) нет: вход (dev-пользователь), `/courses/*` и `/trainer/*` по контракту SPEC на
// типизированных фикстурах `src/components/courses/fixtures/`. Состояние — в памяти.
// Каталог — из настоящей базы дебютов backend/app/review/data/openings.tsv.
//
//   node scripts/courses-mock-api.mjs [порт=8057]
//   NEXT_PUBLIC_API_URL=http://localhost:8057 npx next dev -p 3057
//
// Только для dev: в приложение не импортируется и в сборку не попадает (Node ≥ 23 —
// импорт .ts без компиляции).
import { readFileSync } from "node:fs";
import { createServer } from "node:http";
import { fileURLToPath } from "node:url";
import { NAJDORF_ID, fixtureCourses } from "../src/components/courses/fixtures/courses.ts";
import { najdorfAlternatives, najdorfIdeas, najdorfTree } from "../src/components/courses/fixtures/najdorf-data.ts";

const PORT = Number(process.argv[2] ?? 8057);
const LANG_DEFAULT = "ru";
const BOX_DAYS = [1, 3, 7, 16, 35];
const LEARNED_BOX = 3;

const user = {
  id: "00000000-0000-0000-0000-0000000000d1",
  email: "dev@example.test",
  lang: process.env.MOCK_LANG ?? LANG_DEFAULT,
  lichess_username: null,
  chesscom_username: null,
  created_at: "2026-10-01T00:00:00Z",
};

// --- Каталог из openings.tsv: семейство → вариант → линии ---
function buildCatalog() {
  const tsv = readFileSync(fileURLToPath(new URL("../../backend/app/review/data/openings.tsv", import.meta.url)), "utf8");
  const families = new Map();
  for (const row of tsv.trim().split("\n").slice(1)) {
    const [eco, name, pgn, uci] = row.split("\t");
    // Как в 13.4: семейство — до «:», у имени без «:» — до первой «,».
    const [family, rest] = name.includes(":") ? [name.split(":")[0], name.slice(name.indexOf(":") + 1).trim()] : [name.split(",")[0], ""];
    const variation = rest ? rest.split(",")[0].trim() : family;
    if (!families.has(family)) families.set(family, new Map());
    const variations = families.get(family);
    if (!variations.has(variation)) variations.set(variation, []);
    variations.get(variation).push({ name, eco, uci: uci.split(" "), pgn });
  }
  return {
    families: [...families].map(([name, variations]) => ({
      name,
      variations: [...variations].map(([vname, lines]) => ({ name: vname, lines })),
    })),
  };
}
const catalog = buildCatalog();

// --- Курсы ---
const started = Date.now();
const courses = new Map(fixtureCourses.map((course) => [course.id, { ...course, createdAt: started }]));
const mine = new Set(courses.keys());

function liveCourse(course) {
  if (course.status !== "building" && course.status !== "queued") return course;
  // Сборка идёт медленно: прогресс растёт, но до готовности не доходит (кроме созданных здесь).
  const elapsed = (Date.now() - course.createdAt) / 1000;
  if (course.finishAt && Date.now() >= course.finishAt) {
    return Object.assign(course, { status: "failed", progress: 100, error_code: "explorer_unavailable" });
  }
  const progress = Math.min(95, Math.round(course.progress + elapsed * 3));
  return { ...course, status: elapsed < 2 && course.status === "queued" ? "queued" : "building", progress };
}

function publicCourse(course) {
  const out = { ...course };
  delete out.createdAt;
  delete out.finishAt;
  return out;
}

function courseDetail(course, lang) {
  const live = liveCourse(course);
  const ready = live.status === "ready" && live.id === NAJDORF_ID;
  return {
    ...publicCourse(live),
    tree: ready ? najdorfTree : null,
    ideas_text: ready ? (najdorfIdeas[lang] ?? najdorfIdeas.ru) : {},
  };
}

// --- Тренажёр (логика — как app/trainer: карточки, очередь, SRS пазлов) ---
const byId = new Map(najdorfTree.nodes.map((node) => [node.id, node]));
const cards = new Map(); // `${course}:${node}` → {course_id, node_id, box, next, attempts}

const learnerKids = (node) =>
  node.children.map((id) => byId.get(id)).filter((kid) => kid?.mover === "learner").sort((a, b) => Number(b.main) - Number(a.main));
const cardNodes = () => najdorfTree.nodes.filter((node) => learnerKids(node).length > 0);
function pathUci(nodeId) {
  const out = [];
  for (let node = byId.get(nodeId); node; node = node.parent === null ? undefined : byId.get(node.parent)) {
    if (node.uci) out.unshift(node.uci);
  }
  return out;
}
function ideasNode(nodeId) {
  for (let node = byId.get(nodeId); node; node = node.parent === null ? undefined : byId.get(node.parent)) {
    if (node.ideas) return node.id;
  }
  return null;
}

function nextCard(courseId) {
  const now = Date.now();
  const list = [...cards.values()].filter((card) => !courseId || card.course_id === courseId);
  const due = list.filter((card) => card.next !== null && card.next <= now).sort((a, b) => a.next - b.next)[0];
  const fresh = list.filter((card) => card.next === null).sort((a, b) => byId.get(a.node_id).ply - byId.get(b.node_id).ply)[0];
  const card = due ?? fresh;
  if (!card) return null;
  const node = byId.get(card.node_id);
  return { course_id: card.course_id, node_id: card.node_id, fen: node.fen, path_uci: pathUci(node.id), color: najdorfTree.color, box: card.box, due: Boolean(due) };
}

function answer(courseId, nodeId, { uci, hint_used: hint }) {
  const card = cards.get(`${courseId}:${nodeId}`);
  if (!card) return null;
  const node = byId.get(nodeId);
  const expected = learnerKids(node).map((kid) => ({ uci: kid.uci, san: kid.san }));
  const alt = (najdorfAlternatives[String(nodeId)] ?? []).find((move) => move.uci === uci);
  const verdict = expected.some((move) => move.uci === uci) ? "main" : alt ? "alternative" : "wrong";
  const winLoss = verdict === "main" ? null : alt ? alt.win_loss : 14.2;
  const now = Date.now();
  if (verdict === "wrong") {
    card.box = 0;
    card.next = now + 10 * 60_000;
  } else {
    card.box = hint || verdict === "alternative" ? Math.max(card.box, 1) : Math.min(card.box + 1, BOX_DAYS.length);
    card.next = now + BOX_DAYS[card.box - 1] * 86_400_000;
  }
  card.attempts += 1;
  return { verdict, expected, win_loss: winLoss, box: card.box, next_review_at: new Date(card.next).toISOString(), ideas_node_id: ideasNode(nodeId) };
}

function summary() {
  const now = Date.now();
  const out = new Map();
  for (const card of cards.values()) {
    const row = out.get(card.course_id) ?? { course_id: card.course_id, name: courses.get(card.course_id).name, total: 0, due: 0, new: 0, learned: 0 };
    row.total += 1;
    if (card.next !== null && card.next <= now) row.due += 1;
    if (card.next === null) row.new += 1;
    if (card.box >= LEARNED_BOX) row.learned += 1;
    out.set(card.course_id, row);
  }
  return [...out.values()];
}

// Немного истории: часть карточек уже пройдена, две — пора повторить.
for (const node of cardNodes()) cards.set(`${NAJDORF_ID}:${node.id}`, { course_id: NAJDORF_ID, node_id: node.id, box: 0, next: null, attempts: 0 });
[...cards.values()].slice(0, 5).forEach((card, i) => {
  card.box = i < 3 ? 3 : 1;
  card.next = i === 3 || i === 4 ? Date.now() - 60_000 : Date.now() + 3 * 86_400_000;
  card.attempts = 2;
});

// --- HTTP ---
const error = (status, code, detail = code, params = {}) => ({ status, body: { detail, code, params } });

function route(method, path, query, body) {
  if (path === "/auth/refresh" && method === "POST") return { status: 200, body: { access_token: "dev", token_type: "bearer", expires_in: 3600, user } };
  if (path === "/auth/me") return { status: 200, body: method === "PATCH" ? Object.assign(user, body) : user };
  if (path === "/auth/logout") return { status: 204 };
  if (path === "/courses/catalog") return { status: 200, body: catalog };
  if (path === "/courses" && method === "GET") return { status: 200, body: [...mine].map((id) => publicCourse(liveCourse(courses.get(id)))) };
  if (path === "/courses" && method === "POST") {
    if (query.get("fail") === "limit") return error(429, "rate_limited", "limit", { scope: "course", retry_after: 1200 });
    const key = `${body.color}:${body.line_uci.join(" ")}`;
    const existing = [...courses.values()].find((course) => `${course.color}:${course.line_uci.join(" ")}` === key);
    if (existing) {
      mine.add(existing.id);
      if (existing.status === "failed") {
        // Как в 13.4: упавший курс тем же POST ставится в очередь заново.
        Object.assign(existing, { status: "queued", progress: 0, error_code: null, createdAt: Date.now(), finishAt: Date.now() + 20_000 });
        return { status: 202, body: publicCourse(existing) };
      }
      return { status: 200, body: publicCourse(liveCourse(existing)) };
    }
    const id = crypto.randomUUID();
    const course = {
      id,
      name: body.name ?? "Course",
      eco: null,
      color: body.color,
      line_uci: body.line_uci,
      line_san: [],
      source: body.source ?? "catalog",
      status: "queued",
      progress: 0,
      error_code: null,
      added_at: new Date().toISOString(),
      last_studied_at: null,
      built_at: null,
      createdAt: Date.now(),
      finishAt: Date.now() + 20_000,
    };
    courses.set(id, course);
    mine.add(id);
    return { status: 202, body: publicCourse(course) };
  }
  let m = path.match(/^\/courses\/([^/]+)$/);
  if (m) {
    const course = courses.get(m[1]);
    if (!course || !mine.has(course.id)) return error(404, "course_not_found");
    if (method === "DELETE") {
      mine.delete(course.id);
      for (const [key, card] of cards) if (card.course_id === course.id) cards.delete(key);
      return { status: 204 };
    }
    return { status: 200, body: courseDetail(course, query.get("lang") ?? user.lang) };
  }
  if ((m = path.match(/^\/trainer\/courses\/([^/]+)\/start$/))) {
    const course = courses.get(m[1]);
    if (!course || !mine.has(course.id)) return error(404, "course_not_found");
    if (course.id !== NAJDORF_ID || course.status !== "ready") return error(409, "course_not_ready");
    let created = 0;
    for (const node of cardNodes()) {
      const key = `${course.id}:${node.id}`;
      if (!cards.has(key)) {
        cards.set(key, { course_id: course.id, node_id: node.id, box: 0, next: null, attempts: 0 });
        created += 1;
      }
    }
    return { status: 200, body: { course_id: course.id, total: cardNodes().length, created } };
  }
  if (path === "/trainer/next") {
    const courseId = query.get("course_id");
    if (courseId && !courses.has(courseId)) return error(404, "course_not_found");
    return { status: 200, body: nextCard(courseId) };
  }
  if ((m = path.match(/^\/trainer\/courses\/([^/]+)\/nodes\/(\d+)\/answer$/))) {
    if (!courses.has(m[1])) return error(404, "course_not_found");
    const result = answer(m[1], Number(m[2]), body);
    return result ? { status: 200, body: result } : error(404, "trainer_card_not_found");
  }
  if (path === "/trainer/summary") return { status: 200, body: summary() };
  return error(404, "http_error", `not mocked: ${method} ${path}`, { status: 404 });
}

createServer(async (req, res) => {
  const origin = req.headers.origin ?? "*";
  res.setHeader("Access-Control-Allow-Origin", origin);
  res.setHeader("Access-Control-Allow-Credentials", "true");
  res.setHeader("Access-Control-Allow-Headers", "Authorization, Content-Type, Accept-Language");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS");
  if (req.method === "OPTIONS") return res.writeHead(204).end();
  const url = new URL(req.url ?? "/", "http://localhost");
  const path = url.pathname.replace(/^\/api\/v1/, "");
  let raw = "";
  for await (const chunk of req) raw += chunk;
  const body = raw ? JSON.parse(raw) : {};
  // Задержка как у настоящего API, чтобы видеть состояния загрузки.
  await new Promise((resolve) => setTimeout(resolve, path.includes("/answer") ? 350 : 150));
  const out = route(req.method ?? "GET", path, url.searchParams, body);
  if (out.status === 204) return res.writeHead(204).end();
  res.writeHead(out.status, { "Content-Type": "application/json" }).end(JSON.stringify(out.body));
}).listen(PORT, () => console.log(`courses mock API: http://localhost:${PORT}/api/v1`));
