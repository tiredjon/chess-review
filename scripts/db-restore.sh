#!/usr/bin/env bash
# Восстановление из бэкапа.
#   scripts/db-restore.sh --check [файл]   `make restore-check`: в отдельную БД
#       chess_review_restore_check, сверка числа строк с файлом .counts бэкапа, БД
#       удаляется. Рабочая БД не трогается. Без файла — последний бэкап.
#   scripts/db-restore.sh --yes <файл>     `make restore FILE=…`: в рабочую БД. Сначала
#       свежий бэкап текущего состояния, на время восстановления api / worker / web / bot
#       остановлены; восстановление в одной транзакции (ошибка — БД как была).
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/db-common.sh

mode=${1:-}
file=${2:-}
case "$mode" in
  --check) file=${file:-$(latest_backup)} ;;
  --yes) [[ -n "$file" ]] || { echo "Укажите файл: make restore FILE=backups/…dump" >&2; exit 2; } ;;
  *) echo "Использование: $0 --check [файл] | --yes <файл>" >&2; exit 2 ;;
esac
[[ -f "$file" ]] || { echo "Нет файла бэкапа: ${file:-backups/ пуст}" >&2; exit 1; }
counts="${file%.dump}.counts"

compose up -d --wait postgres >/dev/null 2>&1

verify() { # verify <база>: число строк совпадает с .counts бэкапа
  if [[ ! -f "$counts" ]]; then
    echo "Нет $counts — сверять не с чем; число строк после восстановления:"
    table_counts "$1" | sed 's/^/  /'
    return 0
  fi
  if diff <(sort "$counts") <(table_counts "$1" | sort) >/dev/null; then
    echo "Сверка с $counts: совпадает"
    sed 's/^/  /' "$counts"
  else
    echo "Сверка с $counts: РАСХОЖДЕНИЕ (бэкап → восстановлено):" >&2
    diff <(sort "$counts") <(table_counts "$1" | sort) >&2 || true
    return 1
  fi
}

if [[ "$mode" == --check ]]; then
  db=chess_review_restore_check
  psql_in postgres "DROP DATABASE IF EXISTS $db" >/dev/null
  psql_in postgres "CREATE DATABASE $db" >/dev/null
  trap 'psql_in postgres "DROP DATABASE IF EXISTS $db" >/dev/null' EXIT
  echo "Проверка восстановления $file → $db"
  compose exec -T postgres pg_restore -U chess -d "$db" --no-owner --exit-on-error <"$file"
  verify "$db"
  exit
fi

echo "Восстановление рабочей БД из $file"
echo "Сначала — бэкап текущего состояния:"
scripts/db-backup.sh
running=$(compose ps --status running --services | grep -xE 'api|worker|web|bot' || true)
# shellcheck disable=SC2086 # список сервисов — отдельными словами
[[ -z "$running" ]] || compose stop $running
compose exec -T postgres pg_restore -U chess -d chess_review --no-owner --clean --if-exists \
  --single-transaction --exit-on-error <"$file"
verify chess_review
# shellcheck disable=SC2086
[[ -z "$running" ]] || compose start $running
echo "Готово."
