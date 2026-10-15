// Угрозы после хода (красные стрелки, как «Показывать угрозы» в Chess.com): фигуры сделавшего
// ход, которые бьют фигуру соперника, если взятие выгодно — цель дороже нападающей или
// не защищена; шах — тоже угроза. Считается по геометрии атак (chess.js), без движка.
import { Chess, type Square } from "chess.js";
import type { Color } from "./types";

const VALUES: Record<string, number> = { p: 1, n: 3, b: 3, r: 5, q: 9, k: 100 };
const MAX_THREATS = 4;

export type Threat = { from: string; to: string };

export function threats(fenAfter: string, mover: Color): Threat[] {
  let board: Chess;
  try {
    board = new Chess(fenAfter, { skipValidation: true });
  } catch {
    return [];
  }
  const own = mover === "white" ? "w" : "b";
  const enemy = own === "w" ? "b" : "w";
  const found: (Threat & { value: number })[] = [];

  for (const row of board.board()) {
    for (const piece of row) {
      if (!piece || piece.color !== enemy) continue;
      const target = VALUES[piece.type];
      const defended = board.attackers(piece.square, enemy).length > 0;
      for (const from of board.attackers(piece.square, own)) {
        const attacker = board.get(from as Square);
        if (!attacker) continue;
        const value = VALUES[attacker.type];
        // Король может бить только незащищённую фигуру.
        if (attacker.type === "k" && defended) continue;
        if (piece.type === "k" || !defended || target > value) {
          found.push({ from, to: piece.square, value: target });
        }
      }
    }
  }
  // Самые ценные цели — первыми; стрелок немного, чтобы не загромождать доску.
  return found
    .sort((a, b) => b.value - a.value)
    .slice(0, MAX_THREATS)
    .map(({ from, to }) => ({ from, to }));
}
