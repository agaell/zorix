# Health Model

`modules/health_model` содержит минимальные общие модели health evaluation.

Модуль не знает об адаптерах, Linux, CLI, выводе в терминал или способе загрузки plugin. Его задача - описать:

- severity отдельного finding;
- итоговый health level;
- immutable `HealthFinding`.

`HealthFinding.identity` состоит из `source`, `code` и `resource_id`. `metadata` хранит дополнительные данные, доступна только для чтения и не участвует в equality/hash.

`HealthLevel` вычисляется по findings: `CRITICAL` имеет приоритет над `WARNING`, а `INFO` не повышает уровень выше `HEALTHY`.
