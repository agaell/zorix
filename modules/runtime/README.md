# Runtime

`modules/runtime` содержит прикладной слой, который собирает `PluginLoader`, `Registry`, `ScanEngine`, `TopologyEngine`, `HealthEngine`, `ActionEngine` и `ActionExecutionEngine` в единую рабочую цепочку Zorix.

Runtime не добавляет новую архитектурную модель. Он только связывает уже существующие компоненты.

## Назначение

`ZorixRuntime` отвечает за:

- создание стандартных экземпляров `PluginLoader` и `Registry`, если они не переданы явно;
- загрузку адаптеров через `PluginLoader`;
- регистрацию загруженных адаптеров в `Registry`;
- запуск сканирования через `ScanEngine`;
- построение топологии уже обнаруженных ресурсов через `TopologyEngine`;
- health evaluation уже обнаруженных ресурсов через `HealthEngine`;
- dry-run планирование действий через `ActionEngine`;
- исполнение подтверждённого action plan через `ActionExecutionEngine`;
- очистку зарегистрированных адаптеров.

## Схема

```text
                 PluginLoader
                      |
                      v
                   Registry
              /      |        |        \
             v       v        v         v
      ScanEngine ActionEngine ActionExecutionEngine HealthEngine TopologyEngine
          |          |              |              |             |
          v          v              v              v             v
     ScanResult ActionPlanResult ActionExecutionResult HealthResult TopologyResult
                                               |
                                               v
                                        ResourceGraph
```

`PluginLoader` загружает адаптеры из каталога.

`Registry` хранит зарегистрированные адаптеры и запрещает дубликаты по типу класса.

`ScanEngine` вызывает `discover()` у адаптеров из `Registry` и возвращает `ScanResult`.

`TopologyEngine` использует тот же экземпляр `Registry`: он видит адаптеры, которые структурно реализуют `TopologyProvider`, и строит `TopologyResult` из уже переданных ресурсов.

`HealthEngine`, `ActionEngine` и `ActionExecutionEngine` также используют тот же `Registry`, но работают только с уже переданными resources. `plan_action()` возвращает dry-run plan. `execute_action()` сначала строит план, проверяет подтверждение и только затем делегирует исполнение adapter-у, реализующему `ActionExecutor`.

`Runtime` связывает загрузку, регистрацию, сканирование, health evaluation, action planning, action execution и построение топологии.

`Presentation Layer` преобразует готовый `ScanResult` в текст для CLI вне границ Runtime.

## Пример

```python
runtime = ZorixRuntime()

runtime.load_plugins("modules/mock_adapter")
scan_result = runtime.scan(continue_on_error=True)
topology_result = runtime.build_topology(
    scan_result.resources,
    continue_on_error=True,
)
action_result = runtime.plan_action(scan_result.resources, request)
execution_result = runtime.execute_action(
    scan_result.resources,
    request,
    confirmed=True,
)

for relation in topology_result.graph.relations():
    print(relation.source_id, relation.type, relation.target_id)
```

`build_topology()`, `evaluate_health()`, `plan_action()` и `execute_action()` не запускают `scan()` автоматически и не вызывают `discover()` повторно. Сканирование, evaluation, planning, execution и построение топологии остаются явными этапами.

## Границы ответственности

Runtime не должен:

- реализовывать собственное обнаружение плагинов;
- дублировать поведение `Registry`;
- самостоятельно вызывать `discover()` у адаптеров;
- самостоятельно создавать `TopologyContext` или `ResourceGraph`;
- находить topology providers или обрабатывать их результаты;
- самостоятельно выполнять action plan без `ActionExecutionEngine`;
- выполнять SSH, systemctl или shell-команды изменения состояния;
- форматировать вывод для терминала;
- читать конфигурационные файлы;
- знать конкретные реализации адаптеров.

## Ошибки и дубликаты

`ZorixRuntime` не подавляет ошибки `PluginLoader`, `Registry`, `ScanEngine`, `TopologyEngine`, `HealthEngine`, `ActionEngine` или `ActionExecutionEngine`.

Если один и тот же класс адаптера загружается повторно, `Registry` выбрасывает `DuplicateAdapterError`, а Runtime передает это исключение вызывающему коду.

`scan()` сохраняет семантику `ScanEngine`: fail-fast по умолчанию и `continue_on_error=True` для продолжения после ошибок адаптеров.

`build_topology()` сохраняет семантику `TopologyEngine`: в режиме fail-fast исходная ошибка provider или построения графа передается вызывающему коду; при `continue_on_error=True` ошибки отдельных topology providers включаются в `TopologyResult`, а остальные providers продолжают работу.

`plan_action()` возвращает `ActionPlanResult`: `READY` для валидного dry-run плана или `REJECTED` для отсутствующего ресурса/unsupported action. Provider exceptions не скрываются.

`execute_action()` возвращает `ActionExecutionResult`. Если план отклонён или требуется подтверждение, executor не вызывается. Ошибки executor-а передаются согласно политике `ActionExecutionEngine` и конкретного adapter-а.

`clear()` очищает общий `Registry`. После этого `scan()` не видит адаптеров, `build_topology(resources)` строит граф только из переданных ресурсов, а `evaluate_health()`, `plan_action()` и `execute_action()` не видят providers/executors.
