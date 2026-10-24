# IntelBoard — готовый промпт продолжения в новом чате, PR #69

## Context

Ты — senior full-stack engineer и технический аудитор PlanetDashboard / IntelBoard. **Отвечай по-русски.** Продолжай самостоятельно по нескольким этапам, с подтверждаемыми проверками. Основной репозиторий: https://github.com/Numillyash/planets-intel; смежный проект https://github.com/Numillyash/planets-lab. Это **полный самостоятельный промпт**: прежний чат не нужен. При старте обязательно заново проверь живые GitHub HEAD, PR, CI и deployment branch. Ознакомься с `AGENTS.md`, `docs/WORKFLOW.md`, `docs/architecture/ROADMAP.md`, `docs/architecture/CURRENT_HANDOFF.md`, `docs/architecture/PROJECT_STATE.md`.

Точка отсчёта на момент создания PR #69 24.10.2026: `main` и `feature/operational-ui` на `54014c3fe75b802e6c88cac26b4114d029c1f66a`. PR #68 слит, его PR CI, main CI и deployment branch CI успешны; проверка production runtime после #68 **не подтверждена**. Эти SHA — исторические контрольные точки, не гарантированное состояние в новом чате.

## Verified state

- PR #67 добавил явный маркер NOW и единый 30-секундный clock в `frontend/src/features/map/PlayerActivityPanel.tsx`; линия всегда обозначает текущие часы браузера, не среднее KDE. Сглаживание и реальные семплы не менялись.
- На реальном скриншоте пользователь указал два UX-дефекта: надпись NOW поверх каждого графика выглядит плохо, пунктир предпочтительнее заменить на сплошную линию; `This-game median ready after host 0m` повторяется и бесполезно. В `formatDelay` обнаружено реальное логическое искажение: отрицательные интервалы принудительно превращались в `0m`. Backend готовую медиану вычисляет из `turnreadydate - hostcompleted`, что может быть отрицательным. Ни ноль, ни точный смысл всех таких интервалов на private production не доказаны.
- PR #69 (https://github.com/Numillyash/planets-intel/pull/69) меняет frontend: метку NOW оставляет только в существующей общепанельной легенде LOCAL/UTC; график показывает сплошную жёлтую вертикальную линию с SVG tooltip/a11y; удаляет из карточки misleading `median ready after host`, оставляет `Median first observed open after host (this game)`, отрицательные и отсутствующие задержки отображает `—`. Data/model/backend не изменены.
- PR #69 дополняет `frontend/scripts/turn-timing-now-smoke.mjs` проверками общей легенды, четырёх синхронных сплошных линий, исчезновения плавающих подпунктов, мобильного вида и отрицательной задержки. Статус CI/merge **нужно проверить заново**, не считать исходя из существования файлов.
- Правила PR #68: в **каждом** PR до merge обновляются полный `docs/CONTINUE_HERE.md`, `docs/PR_CHANGELOG.md` с реальным номером PR и тематический документ; PR-only gate `tools/check_pr_handoff.py` проверяет точный base/head SHA.

## Next actions

1. Проверить live PR #69, SHA, backend/frontend/Chromium browser CI, PR handoff gate. Если тесты красные — прочитать конкретные job logs, исправить эту же ветку, синхронизировать handoff и повторить CI.
2. Перед merge проверить desktop/mobile screenshot артефакты при возможности. Не путать synthetic Chromium с проверкой реальных личных игровых данных. Merge только после успешного CI на точном head SHA.
3. Проверить postmerge `main` CI, сравнить `feature/operational-ui` с main через compare; выполнить fast-forward **без force**, только при подтверждённом ancestry, проверить deployment branch CI.
4. После команды оператора `bash /opt/planets-intel/scripts/deploy/production.sh` и доказательства `DEPLOY OK` проверить собственный Turn timing: сплошная линия без NOW внутри графиков, легенда LOCAL/UTC обновляется автоматически, карточка больше не показывает бессмысленную медиану Ready. Без runtime-доказательств production не подтверждён.
5. Дальше провести реальную разрешённую observer-acceptance карты разведанных чужих и нейтральных планет, не публикуя private RST/HAR/cookies/ключи. Доступен workflow Public RST visual evidence для публичных завершённых игр.
6. Перед каждым существенным итоговым ответом сохранять актуальный полный **русский** промпт в Git; не открывать отдельный docs-only PR ради недостоверного прогнозируемого SHA.

## Boundaries

- Разделять `factual observation != historical evidence != inference != prediction != draft`; `known zero != unknown`. Не заявлять, что все отрицательные интервалы `turnreadydate - hostcompleted` объяснены; нужен отдельный аудит семантики Host по независимому источнику.
- Репозиторий публичный: не загружать private RST/cookies/HAR/API keys/личные сообщения. Private observer ограничен собственным/разрешённым выбранным; `INTEL_EXPANDED_SHARING_ENABLED` остаётся off.
- `planets-lab` не служит самостоятельным доказательством production NuHost parity.
- Не говорить `deployed` без `DEPLOY OK` и runtime evidence; сам deploy выполняет оператор. Итог на русском, после нескольких связанных действий.
