# Topology Engine

`modules/topology_engine` содержит движок построения топологии Zorix.

Topology Engine работает с уже обнаруженными `Resource`. Он не запускает resource discovery повторно и не вызывает `Adapter.discover()`.

## Назначение

Topology Engine связывает несколько существующих слоев:

1. Получает `Resource`, например из `ScanResult.resources`.
2. Создает единый `TopologyContext`.
3. Получает актуальный список адаптеров через `Registry.adapters()`.
4. Находит адаптеры с optional capability `TopologyProvider`.
5. Вызывает `discover_relations(context)`.
6. Передает ресурсы и связи в `ResourceGraphBuilder`.
7. Возвращает `TopologyResult` с `ResourceGraph`, статусом, ошибками и статистикой providers.

## Отличие от Topology Provider API

Topology Provider API описывает контракт:

```python
provider.discover_relations(context)
```

Topology Engine выполняет providers последовательно, собирает их результат, применяет политику ошибок и строит итоговый граф.

## Отличие от ResourceGraphBuilder

`ResourceGraphBuilder` отвечает за целостность графа: ресурсы, связи, дубликаты и dangling relations.

Topology Engine не дублирует полную валидацию `ResourceRelation`. Он проверяет только то, что provider вернул `list`, а содержимое списка передает в `ResourceGraphBuilder`.

## Capability Detection

Topology providers определяются только через:

```python
isinstance(adapter, TopologyProvider)
```

Обычные адаптеры без `discover_relations()` игнорируются, не входят в `provider_count` и не считаются ошибкой.

## Единый TopologyContext

В рамках одного `build()` все providers получают один и тот же объект `TopologyContext`.

Это сохраняет единый snapshot ресурсов для всех providers.

## Fail-Fast

По умолчанию `continue_on_error=False`.

Если provider выбрасывает исключение, возвращает не `list` или передает некорректные relations, Topology Engine немедленно прерывает выполнение и передает исходную ошибку вызывающему коду.

`KeyboardInterrupt`, `SystemExit` и другие `BaseException` не перехватываются.

## Continue-On-Error

При `continue_on_error=True` ошибка одного provider сохраняется как `TopologyProviderError`, остальные providers продолжают выполняться.

Ошибочный batch provider отклоняется целиком. Это обеспечивается одним вызовом:

```python
builder.add_relations(relations)
```

Если одна связь внутри batch некорректна, ни одна связь этого provider не попадет в граф.

## TopologyStatus

`TopologyStatus.SUCCESS`:

- providers отсутствуют; или
- все найденные providers завершились успешно.

`TopologyStatus.PARTIAL`:

- часть providers завершилась успешно;
- часть providers завершилась ошибкой.

`TopologyStatus.FAILED`:

- найден хотя бы один provider;
- все providers завершились ошибкой.

Provider, вернувший пустой список, считается успешным.

## TopologyResult

`TopologyResult` содержит:

- `status`
- `graph`
- `errors`
- `provider_count`
- `successful_provider_count`

Дополнительные свойства:

- `failed_provider_count`
- `relation_count`

## Порядок

Порядок providers соответствует `Registry.adapters()`.

Порядок relations сохраняется так:

1. порядок providers в Registry;
2. порядок relations внутри списка, который вернул provider.

Topology Engine не сортирует providers и relations.

## Пример

```python
from zorix_topology_engine import TopologyEngine


engine = TopologyEngine(registry)

result = engine.build(
    scan_result.resources,
    continue_on_error=True,
)

graph = result.graph

for relation in graph.relations():
    print(
        relation.source_id,
        relation.type,
        relation.target_id,
    )
```

## Ограничения

В этой итерации не реализованы:

- Runtime integration;
- CLI-команда `graph`;
- renderer для графа;
- Docker `TopologyProvider`;
- Kubernetes `TopologyProvider`;
- retries;
- timeouts;
- async;
- parallel provider execution;
- logging;
- persistence;
- JSON/YAML export;
- Graphviz;
- NetworkX;
- shortest path;
- cycle detection;
- topological sorting;
- AI planner.

Providers выполняются последовательно.
