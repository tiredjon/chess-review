#!/usr/bin/env bash
# Бэкап рабочей БД (`make backup`): pg_dump -Fc в backups/ + рядом файл с числом строк
# в каждой таблице (по нему `make restore-check` сверяет восстановление). Хранятся
# последние BACKUP_KEEP дампов (по умолчанию 14), старые удаляются.
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/db-common.sh

dir=${BACKUP_DIR:-backups}
keep=${BACKUP_KEEP:-14}
mkdir -p "$dir"

compose up -d --wait postgres >/dev/null 2>&1
name="$dir/chess_review-$(date +%Y%m%d-%H%M%S)"
compose exec -T postgres pg_dump -U chess -d chess_review -Fc >"$name.dump.tmp"
# Дамп читается — значит, записан целиком.
compose exec -T postgres pg_restore -l <"$name.dump.tmp" >/dev/null
mv "$name.dump.tmp" "$name.dump"
table_counts chess_review >"$name.counts"

echo "Бэкап: $name.dump ($(du -h "$name.dump" | cut -f1))"
sed 's/^/  /' "$name.counts"

# Ротация: самые новые — первыми, всё после KEEP-го удаляется вместе с .counts.
ls -1t "$dir"/chess_review-*.dump | tail -n +$((keep + 1)) | while read -r old; do
  rm -f "$old" "${old%.dump}.counts"
  echo "Удалён старый бэкап: $old"
done
