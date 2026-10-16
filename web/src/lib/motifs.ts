// Названия тактических мотивов (backend/app/review/motifs/, RU — как в explain/templates.py)
// и тем пазлов.
const MOTIF_NAMES: Record<string, string> = {
  hanging_piece: "Незащищённая фигура",
  fork: "Вилка",
  pin: "Связка",
  skewer: "Линейный удар",
  discovered_attack: "Вскрытое нападение",
  discovered_check: "Вскрытый шах",
  double_check: "Двойной шах",
  mate_in_n: "Мат",
  mate_threat: "Угроза мата",
  back_rank: "Мат по последней горизонтали",
  trapped_piece: "Пойманная фигура",
  removing_defender: "Устранение защитника",
  overload: "Перегрузка",
  promotion: "Превращение пешки",
  promotion_threat: "Угроза превращения",
  only_move: "Единственный ход",
};

export const motifName = (type: string) => MOTIF_NAMES[type] ?? type;
