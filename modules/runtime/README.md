# Runtime

`modules/runtime` содержит прикладной слой, который собирает `PluginLoader`, `Registry`, `ScanEngine` и `TopologyEngine` в единую рабочую цепочку Zorix.

Runtime не добавляет новую архитектурную модель. Он только связывает уже существующие компоненты.

## Назначение

`ZorixRuntime` отвечает за:

- создание стандартных экземпляров `PluginLoader` и `Registry`, если они не переданы явно;
- загрузку адаптеров через `PluginLoader`;
- регистрацию загруженных адаптеров в `Registry`;
- запуск сканирования через `ScanEngine`;
- построение топологии уже обнаруженных ресурсов через `TopologyEngine`;
- очистку зарегистрированных адаптеров.

## Схема

```text
                 PluginLoader
                      |
                      v
                   Registry
                   /      \
                  v        v
           ScanEngine  TopologyEngine
               |            |
               v            v
          ScanResult   TopologyResult
                                |
                                v
                         ResourceGraph
```

`PluginLoader` загружает адаптеры из каталога.

`Registry` хранит зарегистрированные адаптеры и запрещает дубликаты по типу класса.

`ScanEngine` вызывает `discover()` у адаптеров из `Registry` и возвращает `ScanResult`.

`TopologyEngine` использует тот же экземпляр `Registry`: он видит адаптеры, которые структурно реализуют `TopologyProvider`, и строит `TopologyResult` из уже переданных ресурсов.

`Runtime` связывает загрузку, регистрацию, сканирование и построение топологии.

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

for relation in topology_result.graph.relations():
    print(relation.source_id, relation.type, relation.target_id)
```

`build_topology()` не запускает `scan()` автоматически и не вызывает `discover()` повторно. Сканирование и построение топологии остаются двумя явными этапами.

## Границы ответственности

Runtime не должен:

- реализовывать собственное обнаружение плагинов;
- дублировать поведение `Registry`;
- самостоятельно вызывать `discover()` у адаптеров;
- самостоятельно создавать `TopologyContext` или `ResourceGraph`;
- находить topology providers или обрабатывать их результаты;
- форматировать вывод для терминала;
- читать конфигурационные файлы;
- знать конкретные реализации адаптеров.

## Ошибки и дубликаты

`ZorixRuntime` не подавляет ошибки `PluginLoader`, `Registry`, `ScanEngine` или `TopologyEngine`.

Если один и тот же класс адаптера загружается повторно, `Registry` выбрасывает `DuplicateAdapterError`, а Runtime передает это исключение вызывающему коду.

`scan()` сохраняет семантику `ScanEngine`: fail-fast по умолчанию и `continue_on_error=True` для продолжения после ошибок адаптеров.

`build_topology()` сохраняет семантику `TopologyEngine`: в режиме fail-fast исходная ошибка provider или построения графа передается вызывающему коду; при `continue_on_error=True` ошибки отдельных topology providers включаются в `TopologyResult`, а остальные providers продолжают работу.

`clear()` очищает общий `Registry`. После этого `scan()` не видит адаптеров, а `build_topology(resources)` строит граф только из переданных ресурсов, без relations от ранее загруженных providers.
