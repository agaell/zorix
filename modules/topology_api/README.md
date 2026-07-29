# Topology Provider API

`modules/topology_api` содержит независимый API-контракт для адаптеров, которые смогут предоставлять связи между уже обнаруженными ресурсами Zorix.

Модуль не меняет существующий контракт `Adapter`. Поддержка topology является необязательной capability: адаптер может реализовывать только `discover()`, а может дополнительно реализовать `discover_relations()`.

## Resource Discovery И Relation Discovery

Resource discovery отвечает за обнаружение ресурсов:

```python
class Adapter:
    def discover(self) -> list[Resource]:
        ...
```

Relation discovery отвечает за обнаружение направленных связей между уже известными ресурсами:

```python
class TopologyProvider:
    def discover_relations(
        self,
        context: TopologyContext,
    ) -> list[ResourceRelation]:
        ...
```

В этой итерации API только определяет контракт. Production `TopologyEngine` пока не реализован.

## TopologyContext

`TopologyContext` предоставляет provider доступ к уже обнаруженным ресурсам.

Он поддерживает:

- `resources()`
- `has_resource(resource_id)`
- `resource(resource_id)`
- `resources_by_type(resource_type)`
- `__len__()`

Контекст строится как структурный snapshot поверх `ResourceGraphBuilder`. Он не хранит ссылку на исходный изменяемый список ресурсов и не предоставляет методов добавления, удаления или очистки.

Важно различать:

- `TopologyContext` структурно неизменяем;
- сами объекты `Resource` из Core Model не копируются глубоко и могут оставаться изменяемыми.

## TopologyProvider

`TopologyProvider` является `runtime_checkable Protocol`.

Он:

- не наследуется от `Adapter`;
- проверяется структурно;
- доступен через `isinstance`;
- не требует общего базового класса;
- не строит `ResourceGraph`;
- не знает о `ResourceGraphBuilder`;
- возвращает только `list[ResourceRelation]`.

Один объект может одновременно быть `Adapter` и `TopologyProvider`.

## Пример

```python
from zorix_core_model import Adapter, Resource
from zorix_resource_graph import ResourceRelation
from zorix_topology_api import TopologyContext


class ExampleAdapter(Adapter):
    def discover(self) -> list[Resource]:
        ...

    def discover_relations(
        self,
        context: TopologyContext,
    ) -> list[ResourceRelation]:
        return [
            ResourceRelation(
                source_id="service:api",
                target_id="database:main",
                type="depends_on",
            )
        ]
```

Проверка capability:

```python
from zorix_topology_api import TopologyProvider


if isinstance(adapter, TopologyProvider):
    relations = adapter.discover_relations(context)
```

## Целостность графа

`TopologyProvider` не выполняет автоматическую валидацию endpoints.

Provider должен возвращать связи, которые ссылаются на `Resource.id` из переданного `TopologyContext`, но финальной границей целостности графа остается `ResourceGraphBuilder`.

Будущий `TopologyEngine` сможет вызывать providers, собирать relations и передавать их в `ResourceGraphBuilder`.

## Текущие ограничения

В этой итерации не реализованы:

- `TopologyEngine`;
- обработка ошибок providers;
- `continue_on_error`;
- интеграция с Runtime;
- интеграция с Registry в production-коде;
- изменение Adapter API;
- изменение Resource Graph;
- изменение Docker Adapter;
- Docker network resources;
- Docker image resources;
- CLI graph;
- сериализация;
- persistence;
- визуализация;
- NetworkX;
- Graphviz.
