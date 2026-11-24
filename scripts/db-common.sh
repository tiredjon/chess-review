# Общее для db-backup.sh и db-restore.sh (подключается через source).

TABLES=(users games analyses moves puzzles puzzle_attempts explanations position_evals
  import_jobs telegram_chats)

compose() {
  docker compose "$@"
}

psql_in() { # psql_in <база> <sql>
  compose exec -T -e PGOPTIONS=--client-min-messages=warning postgres psql -U chess -d "$1" -v ON_ERROR_STOP=1 -tAc "$2"
}

table_counts() { # table_counts <база> → строки «таблица число»
  local sql="" t
  for t in "${TABLES[@]}"; do
    sql+="${sql:+ UNION ALL }SELECT '$t', count(*) FROM $t"
  done
  psql_in "$1" "$sql" | tr '|' ' '
}

latest_backup() {
  ls -1t "${BACKUP_DIR:-backups}"/chess_review-*.dump 2>/dev/null | head -1
}
