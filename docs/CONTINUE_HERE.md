# IntelBoard — полный русский промпт продолжения после PR #72

## Context

Ты — senior full-stack инженер, тестировщик и технический аудитор IntelBoard / PlanetDashboard. Продолжай разработку автономно, по-русски; пользователю отправлять завершённые этапы и в основном команду deployment, а не запрашивать разрешение на каждый PR. Основной репозиторий https://github.com/Numillyash/planets-intel ; исследовательский https://github.com/Numillyash/planets-lab . Это **полный самостоятельный промпт для нового чата**. На старте заново получи live main / feature/operational-ui HEAD, PR и CI из GitHub; прошлые SHA не гарантируют текущие. Прочти `AGENTS.md`, `docs/WORKFLOW.md`, `docs/architecture/ROADMAP.md`, `docs/architecture/CURRENT_HANDOFF.md`, `docs/architecture/PROJECT_STATE.md`, а также тематические docs.

Состояние перед PR #72 (историческое, 27.10.2026): merged PR #71, обе ветки main/feature/operational-ui на `e7970dc3a5bb447b853cb5e97cb72d438ace2e83` с зелёными post-merge CI. PR #72: https://github.com/Numillyash/planets-intel/pull/72 ; ветка `fix/full-tank-beam-fighter-scenarios-20261027`. Номер PR известен, но актуальный head и merge-коммит необходимо проверить заново.

## Verified state

- Пользователь показал на private карте Горби #50, hull #70: observed mass 2803, hull mass 980, ёмкость бака 1760. PR #71 удалил неподходящий VCR и невозможные торпеды, правильно показал fighters своих Virgo/Gemini. Однако в Combat `Fuel tank capacity —`, а предполагаемые fighters не отображались, хотя в Intel виден 1760: `threat_analysis.py` использовал только поле `fuel`, тогда как `loadout_inference.py` поддерживал `fuel/fueltank/fuelcapacity`.
- PR #72 добавляет shared `hull_fuel_capacity()` с вариантами ключа и `uniform_beam_fighter_scenarios()` в `backend/app/services/ship_threat_evidence.py`. Backend threat и Intel loadout возвращают одинаковые conditional beam варианты из **правил текущей игры**, а не из хардкода: наблюдаемая масса − голый корпус − **предполагаемая полная** ёмкость − 10 * масса выбранного одинакового beam = максимум 1-kt fighters при нулевом cargo. Возможные варианты не равно реальным параметрам противника.
- Гипотеза для Горби: после hull и полного топлива остаётся 63 kt. Если все 10 beam slots заняты одинаковыми лучами, Laser/X-Ray → до 53 fighters, Plasma Bolt → 43, Positron → 33, Blaster/Disruptor → 23, Phaser → 13, Heavy Phaser → 3; два 70-kt комплекта невозможно совместить с полным баком. Если бак не полон, границы изменятся; отсутствующие данные не заменять нулём.
- Создан `frontend/src/features/map/FullTankBeamScenarios.tsx` — общий компактный блок в Combat и Intel с подсказкой hypothetical / NOT observed. Список объединяет одинаковые значения массы.
- Для лучевых кандидатов прежнее сравнение `minimum_hull_plus_beams_mass > minimum_observed_mass` могло ошибочно исключить текущее вооружение из-за refit/старой массы: в PR #72 сравнивается с массой текущего наблюдения, исторический минимум остаётся исследовательским контекстом.
- Пользовательская контрольная масса Virgo: 2321 - 625 hull - 1550 полного бака - 106 известных fighters = 40 kt. Это объясняется 10 Disruptor по 4 kt лишь **при полном баке и отсутствии иных грузов**, и не доказывает тип вооружения.
- Тесты в `backend/tests/test_ship_threat_evidence.py` проверяют ключи каталога, точные условные значения Горби, невозможные альтернативы, unknown/known zero, контроль Virgo. Технический handoff: `docs/handoff/2026-10-27-full-tank-beam-fighter-ceilings.md`.

## Next actions

1. Проверить живой HEAD PR #72, review/checks. Backend tests, frontend typecheck/build, Chromium smoke и production image, PR continuation/docs gate должны быть зелёными на **точном final PR head**. При красных тестах исправлять код и документацию в той же ветке; не объявлять success без подтверждения.
2. Слить PR #72 без запроса дополнительного подтверждения пользователя после всех успешных проверок. Проверить postmerge `main` CI; проверить ancestry и обновить `feature/operational-ui` **fast-forward без force-push**, проверить её post-push CI. Не оставлять PR подвешенным, если тесты уже зелёные.
3. Текущая production не подтверждена. Пользователю нужно выполнить `bash /opt/planets-intel/scripts/deploy/production.sh` на своём сервере; реальные acceptance проверить только после `DEPLOY OK`, по собственной/разрешённой private observer сессии, без копирования приватных RST/HAR в публичный репозиторий. На Горби должны быть условные потолки в обеих вкладках и 1760 вместо — в Combat.
4. Если необходимо дальше улучшить вероятности боя, не выдавать симуляционные проценты без конкретного сценария противника, модификаторов и проверенного solver; отделять оценки от фактов. Продолжать аудит остальных UI/roadmap задач.
5. После каждого PR обновлять полный `docs/CONTINUE_HERE.md` на русском, `docs/PR_CHANGELOG.md` с реальным номером PR и отдельный тематический документ **в том же PR**. Не делать отдельные docs-only PR ради угадывания SHA после merge.

## Boundaries

`factual observation != historical evidence != inference != hypothetical scenario != prediction`. `known zero != unknown`. Полный бак / 10 одинаковых орудий / нулевой груз — **только допущения**, не наблюдения. Engines включены в hull mass по официальной игре. Использовать API лишь для своего или явно разрешённого observer; публичный GitHub не предназначен для private RST, cookies, HAR, ключей и сообщений. `INTEL_EXPANDED_SHARING_ENABLED` остаётся off. NuHost causal evidence из planets-lab не автоматически переносится на production. Нет утверждений об успешном развёртывании без DEPLOY OK и runtime проверки. Ответ пользователю по-русски.
