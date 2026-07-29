# Action Engine

`modules/action_engine` выполняет read-only планирование действий поверх уже найденных `Resource`.

Engine:

- получает adapters из `Registry`;
- выбирает только объекты, структурно реализующие `ActionProvider`;
- создаёт один `ActionContext`;
- проверяет существование target resource;
- последовательно вызывает providers;
- возвращает `READY`, если ровно один provider сформировал валидный `ActionPlan`;
- возвращает `REJECTED`, если ресурс отсутствует или действие не поддержано;
- выбрасывает ошибку, если несколько providers одновременно готовы планировать один request.

Action Engine не выполняет SSH, systemctl, shell-команды, topology, health evaluation или изменение состояния. Результат является dry-run планом для будущей execution-итерации.
