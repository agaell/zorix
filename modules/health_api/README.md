# Health API

`modules/health_api` задаёт контракт для read-only health evaluation.

`HealthContext` - immutable snapshot набора `Resource`, полученного после scan. Он сохраняет исходный порядок ресурсов, строит индекс по `Resource.id` один раз и предоставляет lookup без изменения самих ресурсов.

`HealthProvider` - structural protocol. Provider определяется через:

```python
isinstance(adapter, HealthProvider)
```

Контракт содержит один метод: `evaluate_health(context) -> list[HealthFinding]`.

API слой не выполняет scan, не строит topology, не загружает plugins и не знает о конкретных адаптерах.
