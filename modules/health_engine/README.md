# Health Engine

`modules/health_engine` выполняет read-only health evaluation поверх уже найденных `Resource`.

Engine:

- получает adapters из `Registry`;
- выбирает только объекты, структурно реализующие `HealthProvider`;
- создаёт один `HealthContext`;
- последовательно вызывает providers;
- сохраняет порядок providers и findings;
- дедуплицирует findings по `HealthFinding.identity`;
- не выполняет scan, SSH, topology или actions.

`HealthStatus` описывает статус выполнения evaluators: `SUCCESS`, `PARTIAL`, `FAILED`.

`HealthLevel` описывает состояние найденных ресурсов и вычисляется только по успешным findings: `CRITICAL` > `WARNING` > `HEALTHY`. Ошибка provider не создаёт finding автоматически.

По умолчанию используется fail-fast. В режиме `continue_on_error=True` ошибки provider записываются в `HealthProviderError`, а остальные providers продолжают работу.
