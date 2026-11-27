// Единственная точка доступа к данным тренера: настоящий клиент или (в дев-сборке по флагу
// `NEXT_PUBLIC_COACH_MOCK=1`) моки из `mock.ts`. Типы и функции — как в `lib/coach-api.ts`.
import { coachApi } from "@/lib/coach-api";
import { COACH_MOCK, mockCoachApi } from "./mock";

export const coach: typeof coachApi = COACH_MOCK ? mockCoachApi : coachApi;
export { COACH_MOCK };
