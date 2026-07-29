# Action Model

`modules/action_model` содержит read-only модель планирования инфраструктурных действий.

Модуль описывает только dry-run plan. Он не содержит executor, shell-команд, SSH target, sudo, environment variables, паролей или параметров выполнения.

Основные объекты:

- `ActionRequest` - запрос на действие над конкретным `Resource`;
- `ActionStep` - человекочитаемый шаг будущего плана без команды выполнения;
- `ActionPlan` - валидированный dry-run план;
- `ActionPlanResult` - результат планирования: `READY` или `REJECTED`.

`ActionRisk` задаёт риск будущего действия: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`. Сравнение риска должно выполняться через rank helper, а не через строковые значения.
