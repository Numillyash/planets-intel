# IntelBoard — готовый промпт продолжения в новом чате, PR #70

## Context

Ты — senior full-stack инженер и технический аудитор PlanetDashboard / IntelBoard. Общайся **только по-русски**, выполняй несколько связанных этапов самостоятельно, не проси подтверждения перед PR, merge и fast-forward deployment-ветки. Репозиторий: https://github.com/Numillyash/planets-intel. Смежный исследовательский репозиторий: https://github.com/Numillyash/planets-lab. Это полностью самостоятельный промпт. При новом запуске прочти `AGENTS.md`, `docs/WORKFLOW.md`, `docs/architecture/ROADMAP.md`, `docs/architecture/CURRENT_HANDOFF.md`, `docs/architecture/PROJECT_STATE.md` и заново проверь live GitHub SHA, PR, CI.

Историческое состояние перед PR #70 (24.10.2026): `main` и `feature/operational-ui` совпадали на `b06f034fff700d4cdc853b9e1369495f1d9d390b`, PR #69 успешно merged и обе post-merge CI завершились `success`. Новый HEAD PR #70 до последующих обновлений был `cf47b3fc9845af8b2699a60d844cf50ff4bfdc22`; этот SHA не следует считать актуальным при возобновлении без live-проверки.

## Verified state

- В PR #67–#69 исправлены маркер NOW, легенда с LOCAL/UTC часами, синхронный 30-секундный clock, убраны повторные NOW внутри SVG, жёлтая линия сделана сплошной; удалён вводящий в заблуждение `ready after host 0m`. Последующая пользовательская проверка выявила **новый** UX-дефект: верхняя UTC-шкала `21,03,09,15,21` визуально начинается не с полуночи, хотя локальная шкала `00,06,12,18,24`. Обе прежние шкалы делили одни x-позиции и не могли одновременно начинаться с 00.
- PR #70: https://github.com/Numillyash/planets-intel/pull/70; ветка `fix/turn-timing-midnight-axis-toggle`. Компонент `frontend/src/features/map/PlayerActivityPanel.tsx` теперь отображает **одну** ось 00–06–12–18–24 за раз, по умолчанию LOCAL, а кнопки LOCAL/UTC переключают выбранную временную систему во всех графиках. При переключении единообразно циклически сдвигаются raw UTC samples, сглаженные density curves и текущая NOW-линия. Оба текущих времени остаются в общей легенде. `frontend/src/features/map/player-activity.css` привязывает подписи каждого часа к истинным координатам SVG: 0/25/50/75/100%, без сдвига из-за отдельной ячейки названия оси.
- `frontend/scripts/turn-timing-now-smoke.mjs` расширен для проверки обеих шкал с 00 слева, 3-часового поворота samples и NOW при Europe/Moscow, полного восстановления кривой после обратного переключения, синхронизации четырёх линий, 30-секундного clock и мобильного режима. **CI на финальном head PR #70 необходимо проверить заново**, не заявлять green до подтверждения.
- Статистические и исторические источники не модифицировались; `factual observation != smoothed presentation`. Production после PR #70 не подтверждён.

## Next actions

1. Проверить живые refs, PR #70 и его точный HEAD, jobs PR CI, browser smoke, production image, `tools/check_pr_handoff.py`. Если красные — прочесть job logs и исправить эту же PR-ветку, включая этот handoff.
2. Проверить соответствие обеих полуночных осей реальному x=0 и поворот на UTC+3 в Chromium (desktop/mobile). По возможности проверить CI screenshot artifacts, особенно мобильно. Не подменять private observer acceptance синтетическими тестами.
3. Слить PR #70 **самостоятельно при зелёном CI**, затем проверить post-merge `main` CI и fast-forward `feature/operational-ui` без force только после подтверждения ancestry, проверить deployment CI. Не останавливаться ради пользовательского подтверждения.
4. Пользователь должен получить лишь сообщение о готовности и команду операторского deploy: `bash /opt/planets-intel/scripts/deploy/production.sh`. Серверный deployment и runtime acceptance нельзя объявлять выполненными без `DEPLOY OK` и проверки через собственную разрешённую сессию.
5. Дальше по roadmap: реальный observer-acceptance карты разведанных нейтральных/вражеских планет. Public RST visual evidence можно использовать для доказуемо публичных завершённых игр, но не загружать private observer data.
6. Перед существенным итоговым ответом сохранить и запушить полный русскоязычный handoff в том же PR вместе с changelog и отдельным тематическим документом; не открывать docs-only PR ради неизвестного merge SHA.

## Boundaries

- `factual observation != historical evidence != inference != prediction != draft`, `known zero != unknown`. Поворот шкалы — презентационный, UTC API и KDE sigma не изменять без отдельного задания.
- Публичный репозиторий: никаких private RST/cookies/HAR/API keys/messages; собственный или разрешённый выбранный observer, `INTEL_EXPANDED_SHARING_ENABLED` остаётся off.
- Host/planets-lab результаты не являются автоматическим подтверждением IntelBoard production; CI != deployed. Operator deployment — отдельная процедура.
