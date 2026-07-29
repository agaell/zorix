# Presentation Layer

`modules/presentation` содержит независимый слой представления результатов Zorix.

Presentation Layer получает уже сформированные объекты результата и преобразует их в plain-text строку для терминала. Он не запускает scan, не строит topology, не загружает plugins, не обращается к Registry и не разбирает аргументы командной строки.

## Renderer'ы

### ConsoleRenderer

`ConsoleRenderer` форматирует `ScanResult`.

Он выводит:

- статус scan;
- количество adapters, если оно передано вызывающим кодом;
- количество resources;
- список resources;
- список adapter errors.

Пример:

```text
Status: SUCCESS
Adapters: 1
Resources: 2

Resources:
- Service: api
- Container: nginx
```

### TopologyConsoleRenderer

`TopologyConsoleRenderer` форматирует `TopologyResult`.

Он выводит:

- статус topology;
- количество providers;
- количество successful и failed providers;
- количество resources;
- количество relations;
- список relations;
- список provider errors.

Пример:

```text
Topology: SUCCESS
Providers: 1
Successful providers: 1
Failed providers: 0
Resources: 3
Relations: 2

Relations:
- Container zorix-api --uses_image--> Image zorix/api:latest
- Container zorix-api --connected_to--> Network backend
```

## Общие правила

Оба renderer'а:

- возвращают строку;
- не вызывают `print()`;
- не завершают процесс;
- не запускают engine;
- не знают о CLI;
- не изменяют переданные result, graph, resources или relations.

Вызывающий слой сам решает, куда отправить строку.

## Формат relations

`TopologyConsoleRenderer` выводит relation в формате:

```text
- <SourceType> <SourceName> --<relation_type>--> <TargetType> <TargetName>
```

`relation.type` выводится как стабильный машинный идентификатор без преобразования: например, `uses_image`, `connected_to`, `depends_on`.

Metadata relation в основном выводе не показывается. Для детального вывода или JSON export может быть добавлен отдельный renderer.

## Fallback для ресурсов в topology

Для типа ресурса используется:

1. непустое строковое `resource.type`;
2. имя класса.

`snake_case` и `kebab-case` типы преобразуются в Pascal-style display:

- `container` -> `Container`;
- `docker_network` -> `DockerNetwork`;
- `load-balancer` -> `LoadBalancer`.

Для имени ресурса используется:

1. непустое строковое `resource.name`;
2. непустое строковое `resource.id`;
3. имя класса.

## Пример использования ScanResult

```python
from zorix_presentation import ConsoleRenderer

text = ConsoleRenderer().render(scan_result, adapter_count=len(runtime.adapters()))
print(text, end="")
```

`print()` находится снаружи renderer.

## Пример использования TopologyResult

```python
from zorix_presentation import TopologyConsoleRenderer

text = TopologyConsoleRenderer().render(topology_result)
print(text, end="")
```

CLI `scan` пока использует только форматирование inventory. CLI-команда для topology будет добавлена отдельно.
