# Resource Graph

`modules/resource_graph` содержит независимый фундамент графа ресурсов Zorix.

Модуль строит валидированную in-memory модель ресурсов и направленных связей между ними. Он не зависит от CLI, Presentation Layer, Docker Adapter, PluginLoader, Registry или Runtime. Production-код модуля зависит только от Core Model.

## Назначение

Сейчас Zorix получает плоский список `Resource`. Resource Graph позволяет представить эти данные как направленный граф:

```text
Resource --Relation--> Resource
```

Граф нужен для дальнейшего анализа связей между инфраструктурными объектами. В этой итерации модуль только хранит и проверяет явно переданные связи; автоматическое извлечение связей из адаптеров пока не реализовано.

## Resource

`Resource` является узлом графа.

Граф хранит те же объекты `Resource`, которые были добавлены через `ResourceGraphBuilder`. Он не выполняет `deepcopy` и не изменяет ресурсы.

Важно различать:

- `ResourceGraph` структурно неизменяем: после создания нельзя добавить или удалить узлы и связи;
- сами объекты `Resource` из Core Model сейчас могут оставаться изменяемыми.

## ResourceRelation

`ResourceRelation` является направленным ребром графа.

Поля связи:

- `source_id`
- `target_id`
- `type`
- `metadata`

`source_id`, `target_id` и `type` обязательны, должны быть строками и не могут быть пустыми после `strip()`. Значения нормализуются удалением внешних пробелов. Регистр не изменяется.

Самосвязи разрешены:

```text
resource-a --references--> resource-a
```

## Идентичность связи

Идентичность связи определяется тройкой:

```text
(source_id, type, target_id)
```

`metadata` не участвует в определении дубликата. Поэтому две связи с одинаковыми `source_id`, `type` и `target_id`, но разной metadata считаются дубликатами.

## Metadata

`ResourceRelation.metadata` содержит только пары `str -> str`.

При создании связи metadata копируется и становится недоступной для внешнего изменения. Исходный mapping не изменяется.

## Dangling Relations

Связь можно добавить только между ресурсами, уже зарегистрированными в builder.

Если `source_id` или `target_id` отсутствует, builder выбрасывает `InvalidRelationError`. Такой подход запрещает dangling relations и сохраняет целостность графа.

## ResourceGraphBuilder

`ResourceGraphBuilder` хранит рабочее изменяемое состояние.

Он поддерживает:

- `add_resource(resource)`
- `add_resources(resources)`
- `add_relation(relation)`
- `add_relations(relations)`
- `build()`
- `clear()`

Batch-операции `add_resources()` и `add_relations()` атомарны: если хотя бы один элемент некорректен или дублируется, состояние builder не меняется.

## ResourceGraph

`ResourceGraph` является структурно неизменяемым снимком.

Он поддерживает:

- получение всех ресурсов;
- получение всех связей;
- поиск ресурса по id;
- получение исходящих связей;
- получение входящих связей;
- получение соседних ресурсов.

Изменение builder после `build()` не меняет уже построенный граф.

## Пример создания

```python
from zorix_resource_graph import (
    ResourceGraphBuilder,
    ResourceRelation,
)

builder = ResourceGraphBuilder()
builder.add_resources(resources)
builder.add_relation(
    ResourceRelation(
        source_id="service:api",
        target_id="database:main",
        type="depends_on",
    )
)

graph = builder.build()

for resource in graph.neighbors("service:api"):
    print(resource.name)
```

## Поиск связей

```python
outgoing = graph.outgoing("service:api")
incoming = graph.incoming("database:main")
neighbors = graph.neighbors("service:api")
```

`outgoing()`, `incoming()` и `neighbors()` поддерживают фильтрацию по `relation_type`.

## Ограничения

В текущей итерации модуль не реализует:

- автоматическое обнаружение связей адаптерами;
- изменение Adapter API;
- Docker-specific логику;
- CLI-команду `graph`;
- визуализацию;
- Graphviz;
- NetworkX;
- сериализацию;
- хранение в базе данных;
- shortest path;
- cycle detection;
- topological sorting.
