import type { Dict } from "..";
import type { ErrorParams } from "../ru/errors";

const rateLimited: Record<string, (wait: string) => string> = {
  import: (wait) => `Too many imports. Try again in ${wait}.`,
  analyze: (wait) => `Too many analyses started. Try again in ${wait}.`,
  llm: (wait) => `Too many explanation requests. Try again in ${wait}.`,
  login: (wait) => `Too many sign-in attempts. Try again in ${wait}.`,
  register: (wait) => `Too many sign-ups from this address. Try again in ${wait}.`,
  browser: (wait) => `Too many in-browser analyses saved. Try again in ${wait}.`,
  explore: (wait) => `Too many server engine requests. Switch to the browser or wait ${wait}.`,
};

const wait = (seconds: number) => {
  if (seconds < 60) return `${seconds} s`;
  if (seconds < 3600) return `${Math.ceil(seconds / 60)} min`;
  return `${Math.ceil(seconds / 3600)} h`;
};

export const errors: Dict["errors"] = {
  codes: {
    not_authenticated: () => "Please sign in",
    token_expired: () => "Your session has expired, please sign in again",
    token_invalid: () => "Your session is no longer valid, please sign in again",
    refresh_invalid: () => "Your session has expired, please sign in again",
    refresh_rotated: () => "Session is being refreshed, please try again",
    origin_forbidden: () => "Request from another site was rejected",
    email_taken: () => "This email is already registered",
    invalid_credentials: () => "Wrong email or password",
    rate_limited: (p: ErrorParams) =>
      (rateLimited[String(p.scope)] ?? ((w: string) => `Too many requests. Try again in ${w}.`))(
        wait(Number(p.retry_after ?? 60)),
      ),
    game_not_found: () => "Game not found",
    analysis_not_found: () => "Analysis not found",
    analysis_not_ready: () => "The analysis is not ready yet",
    move_not_found: () => "Move not found",
    import_not_found: () => "Import not found",
    puzzle_not_found: () => "Puzzle not found",
    puzzle_attempt_invalid: () => "The move doesn't match the puzzle — reload the page",
    invalid_cursor: () => "The list is outdated — reload the page",
    pgn_invalid: (p: ErrorParams) => `Game ${p.game}: could not parse PGN (${p.reason})`,
    pgn_too_many: (p: ErrorParams) => `Too many games at once: at most ${p.max}`,
    pgn_empty: () => "No games found in the text",
    pgn_variant: (p: ErrorParams) => `Game ${p.game}: only standard chess is supported`,
    pgn_no_moves: (p: ErrorParams) => `Game ${p.game}: the game has no moves`,
    queue_unavailable: () => "The task queue is unavailable, try again later",
    enqueue_failed: () => "Could not queue the task",
    interrupted: () => "The task was interrupted — start it again",
    internal: () => "Internal server error",
    source_user_not_found: (p: ErrorParams) => `User ${p.username} not found on ${p.source}`,
    source_rate_limited: (p: ErrorParams) => `${p.source} is rate limiting requests, try again later`,
    source_unavailable: (p: ErrorParams) => `${p.source} is unavailable, try again later`,
    source_bad_response: (p: ErrorParams) => `${p.source} returned an invalid response`,
    // Клиентский код: ошибка валидации поля email.
    invalid_email: () => "Invalid email address",
    share_not_found: () => "Link is no longer valid",
    source_no_games: (p) => `${p.username ?? "The player"} has no standard chess games`,
    engine_data_invalid: () => "The in-browser engine sent invalid evaluations — try again",
    depth_too_low: (p) => `Analysis depth must be at least ${p.min}`,
    invalid_fen: () => "Invalid position",
    engine_unavailable: () => "The server engine is unavailable — switch to the browser",
    validation_error: (p: ErrorParams) => (p.field ? `Check the “${p.field}” field` : "Check the entered data"),
    http_error: (p: ErrorParams) => `Request failed (${p.status})`,
  },
  network: (url) => `Cannot reach the API (${url}). Make sure the backend is running.`,
  server: "The server didn't respond. Try again in a minute.",
  request: (status) => `Request failed (${status})`,
  generic: "Request failed",
};
