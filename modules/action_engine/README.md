# Action Engine

`modules/action_engine` выполняет планирование действий и управляет безопасным запуском уже построенного плана поверх найденных `Resource`.

Engine:

- получает adapters из `Registry`;
- выбирает только объекты, структурно реализующие `ActionProvider`;
- создаёт один `ActionContext`;
- проверяет существование target resource;
- последовательно вызывает providers;
- возвращает `READY`, если ровно один provider сформировал валидный `ActionPlan`;
- возвращает `REJECTED`, если ресурс отсутствует или действие не поддержано;
- выбрасывает ошибку, если несколько providers одновременно готовы планировать один request.

`ActionEngine` не выполняет SSH, systemctl, shell-команды, topology, health evaluation или изменение состояния. Результат является dry-run планом.

## ActionExecutionEngine

`ActionExecutionEngine` строит один `ActionContext`, использует ту же planning-логику, что и `ActionEngine`, и только после этого выбирает executor по `ActionPlan.provider`.

Правила:

- если planning вернул `REJECTED`, execution возвращает `ActionExecutionResult` со статусом `REJECTED` без вызова executor-а;
- если план требует подтверждения, но `confirmed=False`, execution возвращает `REJECTED` с кодом `action.confirmation_required`;
- executor выбирается среди зарегистрированных adapters, структурно реализующих `ActionExecutor`;
- executor должен совпадать с `ActionPlan.provider` по полному имени класса;
- если executor отсутствует или найден неоднозначно, engine выбрасывает typed error;
- executor не должен возвращать `REJECTED`: отказ до исполнения является ответственностью engine.

`ActionExecutionEngine` не загружает plugins, не регистрирует adapters, не запускает scan, topology или health evaluation и не форматирует вывод.
