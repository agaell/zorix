# Action API

`modules/action_api` задаёт контракты планирования и исполнения действий.

`ActionContext` - snapshot набора `Resource`, полученного после inventory scan. Он сохраняет исходный порядок ресурсов, строит индекс по `Resource.id` один раз и возвращает tuple для публичных коллекций.

`ActionProvider` - structural protocol:

```python
isinstance(adapter, ActionProvider)
```

Provider возвращает `ActionPlan`, если поддерживает запрос, или `None`, если действие не относится к нему. Метод `plan_action()` не выполняет действие, не выполняет сеть и не меняет context.

`ActionExecutor` - structural protocol:

```python
isinstance(adapter, ActionExecutor)
```

Executor принимает уже построенный `ActionPlan` и возвращает `ActionExecutionResult`. Выбор executor-а выполняется внешним engine по полному имени provider-а из плана. Контракт не добавляет произвольные параметры выполнения.
