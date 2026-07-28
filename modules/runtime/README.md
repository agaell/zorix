# Runtime

`modules/runtime` содержит прикладной слой, который собирает `PluginLoader`, `Registry` и `ScanEngine` в единую рабочую цепочку Zorix.

Runtime не добавляет новую архитектурную модель. Он только связывает уже существующие компоненты.

## Назначение

`ZorixRuntime` отвечает за:

- создание стандартных экземпляров `PluginLoader` и `Registry`, если они не переданы явно;
- загрузку адаптеров через `PluginLoader`;
- регистрацию загруженных адаптеров в `Registry`;
- запуск сканирования через `ScanEngine`;
- очистку зарегистрированных адаптеров.

## Схема

```text
PluginLoader -> Registry -> ScanEngine -> Runtime -> Presentation Layer -> future CLI
```

`PluginLoader` загружает адаптеры из каталога.

`Registry` хранит зарегистрированные адаптеры и запрещает дубликаты по типу класса.

`ScanEngine` вызывает `discover()` у адаптеров из `Registry` и возвращает `ScanResult`.

`Runtime` связывает загрузку, регистрацию и запуск сканирования.

`Presentation Layer` преобразует готовый `ScanResult` в текст для будущего CLI.

## Пример

```python
runtime = ZorixRuntime()

runtime.load_plugins("modules/mock_adapter")
result = runtime.scan(continue_on_error=True)
```

## Границы ответственности

Runtime не должен:

- реализовывать собственное обнаружение плагинов;
- дублировать поведение `Registry`;
- самостоятельно вызывать `discover()` у адаптеров;
- форматировать вывод для терминала;
- читать конфигурационные файлы;
- знать конкретные реализации адаптеров.

## Ошибки и дубликаты

`ZorixRuntime` не подавляет ошибки `PluginLoader`, `Registry` или `ScanEngine`.

Если один и тот же класс адаптера загружается повторно, `Registry` выбрасывает `DuplicateAdapterError`, а Runtime передает это исключение вызывающему коду.

`scan()` сохраняет семантику `ScanEngine`: fail-fast по умолчанию и `continue_on_error=True` для продолжения после ошибок адаптеров.
