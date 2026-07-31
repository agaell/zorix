# Action Model

`modules/action_model` содержит модель планирования и результата исполнения инфраструктурных действий.

Модуль не содержит executor, shell-команд, SSH target, sudo, environment variables, паролей или параметров выполнения. Он описывает только данные, которыми обмениваются planning и execution слои.

Основные объекты:

- `ActionRequest` - запрос на действие над конкретным `Resource`;
- `ActionStep` - человекочитаемый шаг будущего плана без команды выполнения;
- `ActionPlan` - валидированный dry-run план;
- `ActionPlanResult` - результат планирования: `READY` или `REJECTED`.
- `ActionExecutionResult` - структурированный результат попытки исполнения уже принятого плана;
- `ActionExecutionRejection` - причина отказа до исполнения;
- `ActionExecutionStatus` - итог исполнения: `SUCCESS`, `FAILED` или `REJECTED`.

`ActionRisk` задаёт риск будущего действия: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`. Сравнение риска должно выполняться через rank helper, а не через строковые значения.

`ActionExecutionResult` хранит previous/current state, флаги `changed` и `verified`, человекочитаемое сообщение и необязательные metadata. Metadata копируются во внутренний read-only mapping и не участвуют в equality/hash.
