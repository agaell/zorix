# Action API

`modules/action_api` задаёт контракт read-only планирования действий.

`ActionContext` - snapshot набора `Resource`, полученного после inventory scan. Он сохраняет исходный порядок ресурсов, строит индекс по `Resource.id` один раз и возвращает tuple для публичных коллекций.

`ActionProvider` - structural protocol:

```python
isinstance(adapter, ActionProvider)
```

Provider возвращает `ActionPlan`, если поддерживает запрос, или `None`, если действие не относится к нему. Метод `plan_action()` не выполняет действие, не выполняет сеть и не меняет context.
