# IntelBoard — PR changelog

## PR #68 — обязательное сохранение контекста и репозиторной документации (2026-10-24)

- Перенесён из `planets-lab` доказуемый процесс handoff: обязательный русский `docs/CONTINUE_HERE.md` **в каждом PR**, эта запись в `docs/PR_CHANGELOG.md` и третий тематический документ.
- Добавлены `AGENTS.md`, `docs/WORKFLOW.md`, `tools/check_pr_handoff.py`, отдельный PR job в `.github/workflows/ci.yml`. Проверка работает по точным `base/head` SHA и фактическому номеру PR, исключая обход через устаревший чат.
- Инженерные границы: никаких частных RST/credentials, нет автоматического prod deployment; CI — проверка, а не доказательство результата на CentOS.
- PR #67 (не изменён в этом PR) уже добавил видимый маркер NOW на Turn timing; это зафиксировано в автономном продолжении и WORKFLOW.
- На момент подготовки этой записи итог PR #68 и postmerge CI ещё не известен. Следующий чат обязан заново проверить status, а не считать success заранее.

## Предшествующая история

Ранее выполненные PR #52–#67 описаны в `docs/handoff/`, `docs/architecture/CURRENT_HANDOFF.md` и истории GitHub. Не переносить устаревшие deployed-коммиты как текущие.
