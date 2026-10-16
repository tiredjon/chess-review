// Множественное число: русские формы «1 партия / 2 партии / 5 партий», английские «1 game / 2 games».

const ruRules = new Intl.PluralRules("ru");

/** `ruPlural(n, "партия", "партии", "партий")` — форма по числу (без самого числа). */
export function ruPlural(n: number, one: string, few: string, many: string): string {
  switch (ruRules.select(n)) {
    case "one":
      return one;
    case "few":
      return few;
    default:
      return many;
  }
}

export const enPlural = (n: number, one: string, other: string) => (n === 1 ? one : other);
