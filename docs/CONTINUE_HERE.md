# IntelBoard — готовый русский промпт для следующего чата, PR #71

## Context

Ты — senior full-stack инженер PlanetDashboard / IntelBoard. Отвечай только по-русски. Продолжай автономно: проверяй исходники, исправляй, добавляй регрессии, объединяй готовые PR с зелёными CI и делай fast-forward ветки развёртывания без force-push. Пользователь только оценивает результат после собственного развёртывания на сервере. Основной публичный репозиторий: https://github.com/Numillyash/planets-intel . Смежный исследовательский: https://github.com/Numillyash/planets-lab . В самом начале заново считай живые main/deployment HEAD, открытые PR и CI. Прочти AGENTS.md, docs/WORKFLOW.md, docs/architecture/ROADMAP.md, docs/architecture/CURRENT_HANDOFF.md и docs/architecture/PROJECT_STATE.md. Не требуется предыдущий чат.

Перед PR #71 ветки main и feature/operational-ui были синхронизированы на 424f80f246ea88fd037db1ed3965aef96bd558d8; PR #70 полностью merged, post-merge CI обеих веток успешно прошли. Историческая точка, не прогноз живых SHA.

## Verified state

- Пользователь предоставил скриншоты текущей карты: чужая Gorbie Class Battlecarrier hull #70, observed mass 2803, hull 980, tank capacity 1760. Threat Analysis ошибочно приписывал VCR с двумя torpedo tubes и показывал Mark 4 Photon, хотя каталог корпуса имеет ровно ноль torpedo tubes. Исходный код связывал VCR по ship_id без проверки совместимости вооружения.
- В разделе Reachable defense собственные Virgo и Gemini показывали неизвестные fighters при наличии обычного private ammo, потому что сервер трактовал универсальное ammo только как torpedoes. В PR #71 добавлен безопасный выбор типа ammunition по однозначному корпусу; explicit values имеют приоритет над generic ammo, unknown не равен нулю.
- Наблюдаемый Warp 9 при Unlimited Fuel даёт минимум tech 9; при наличии единственного соответствующего движка в catalog теперь выводится конкретное имя, но не подменяется фактом прямого сканирования.
- Условное предположение полного бака для чужой Gorbie оставляет 2803-980-1760 = 63 kt **общей остаточной массы**: на лучевое вооружение, cargo и fighters одновременно. Это не подтверждённый уровень топлива и не подтверждённые 63 fighters.
- Новый пример пользователя с известным собственным Virgo: observed mass 2321, bare hull 625, полная ёмкость бака 1550, 106 fighters: 2321-625-1550-106=40 kt. Если бак действительно полный и груз отсутствует, 10 Disruptor по 4 kt объясняют 40 kt. Не идентифицировать оружие по одному совпадению массы. Масса engines включена в bare hull по документации игры.
- PR #71 https://github.com/Numillyash/planets-intel/pull/71; branch fix/ship-threat-hull-ammo-mass-evidence-20261027. Основные изменения: backend/app/services/ship_threat_evidence.py, threat_analysis.py, loadout_inference.py, frontend/src/features/map/ThreatAnalysis.tsx и LoadoutInference.tsx, frontend/src/types/threat.ts, frontend/src/types/loadout.ts, backend/tests/test_ship_threat_evidence.py; тематический docs/handoff/2026-10-27-gorbie-hull-ammo-mass-constraint.md. Состояние CI и merge всегда проверять по реальному HEAD.

## Next actions

1. Проверь точный HEAD PR #71, все GitHub Actions и обязательный PR-only docs gate. Исправь падения в этой же ветке, поддержи полный русский handoff и changelog с номером PR. Проверь, что последующая интеграция post-VCR state не прикрепляет к чужой Gorbie старый несовместимый VCR.
2. Прогони unittest (backend), TypeScript frontend build и browser smoke. При зелёном CI самостоятельно merge PR #71. Проверь post-merge main CI, затем ancestry и fast-forward feature/operational-ui без force, затем deployment branch CI.
3. Для своего разрешённого observer убедись: у Gorbie нет торпедных candidates, у собственных известных авианосцев fighters отображается из private ammo с basis; подсказка о полной топливной ёмкости чётко обозначена как условная, не факт. Никаких неподтверждённых процентов победы.
4. Пользователю сообщить только о готовности к deploy и команду оператора bash /opt/planets-intel/scripts/deploy/production.sh . Нельзя утверждать, что сервер уже обновлён без DEPLOY OK и runtime evidence.

## Boundaries

Factual observation != historical evidence != inference != prediction != scenario != draft. Known zero != unknown. Приватные RST/HAR/cookies/API keys/сообщения в публичный GitHub не загружать. Никакого расширения sharing, INTEL_EXPANDED_SHARING_ENABLED off. Доступ только собственного/разрешённого observer. Исследовательские предположения planets-lab не автоматически подтверждают production IntelBoard. Любой PR до merge обязан содержать docs/CONTINUE_HERE.md, docs/PR_CHANGELOG.md и отдельный осмысленный doc. Не создавать docs-only PR после merge ради изменения неизвестных заранее SHA.
