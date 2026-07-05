# 1. Базовая модель

В Zorix есть пять фундаментальных сущностей:

```text
Resource
Tool
Adapter
Workflow
Event
```

До версии `0.1.0` новые фундаментальные сущности не добавляем, если нет серьёзной причины.

---

# 2. Краткое определение сущностей

## Resource

Описание объекта инфраструктуры.

Примеры:

- Server
- Service
- Container
- Database
- Network
- Certificate

Resource не выполняет действия.

---

## Tool

Описание действия, которое можно выполнить над Resource.

Примеры:

- Inspect
- Restart
- Backup
- Create
- Delete

Tool не работает с инфраструктурой напрямую.

---

## Adapter

Связь Zorix с конкретной внешней системой.

Примеры:

- Linux Adapter
- Docker Adapter
- SSH Adapter
- GitHub Adapter

Adapter знает, как получить данные из реального мира.

---

## Workflow

Последовательность Tool, объединённых в сценарий.

Пример:

```text
Backup
 ↓
Update
 ↓
Restart
 ↓
Health Check
```

---

## Event

Факт, который произошёл в системе.

Примеры:

- ResourceDiscovered
- ServiceFailed
- ToolExecuted
- WorkflowCompleted

Event нужен для истории, аудита и будущего Explain.

---

# 3. Связи между сущностями

## Resource ↔ Event

Event может ссылаться на Resource.

```text
Event
  └── resource_id
```

Пример:

```text
ServiceFailed → Service nginx
```

---

## Tool → Resource

Tool описывает действие над одним или несколькими типами Resource.

```text
Tool
  └── supports Resource type
```

Пример:

```text
RestartService → Service
```

---

## Tool → Adapter

Tool не выполняет действие сам.

Tool использует Adapter.

```text
Tool
  ↓
Adapter
  ↓
Infrastructure
```

---

## Workflow → Tool

Workflow состоит из Tool.

```text
Workflow
  ├── Tool 1
  ├── Tool 2
  └── Tool 3
```

---

## Adapter → Resource

Adapter может обнаруживать Resource.

```text
Linux Adapter
  ├── Service
  ├── Process
  └── User
```

---

## Adapter → Event

Adapter может создавать Event, если обнаружил изменение состояния.

Пример:

```text
Adapter обнаружил failed service
↓
Event: ServiceFailed
```

---

# 4. Запрещённые связи

## Resource не знает про Adapter

Плохо:

```text
Resource → Adapter
```

Почему плохо:

- Resource станет зависеть от источника;
- один и тот же Resource нельзя будет получить разными способами;
- модель станет сложнее.

---

## Resource не выполняет Tool

Плохо:

```python
resource.restart()
```

Правильно:

```text
Tool RestartService
  ↓
Adapter
  ↓
Infrastructure
```

---

## Workflow не обращается к Infrastructure напрямую

Workflow работает только через Tool.

---

## Tool не вызывает Docker, SSH или systemctl напрямую

Tool не должен знать, как именно выполняется действие.

Это задача Adapter.

---

# 5. Жизненный цикл Resource

Предварительная модель:

```text
planned
   ↓
active
   ↓
degraded
   ↓
failed
   ↓
deleted
```

Дополнительное состояние:

```text
unknown
```

Используется, когда Zorix знает о Resource, но не уверен в его текущем состоянии.

---

# 6. Кто создаёт, читает, изменяет и удаляет сущности

## Resource

Создаёт:

- Adapter;
- импорт;
- Planner в будущем.

Читает:

- Tool;
- Graph;
- CLI;
- MCP;
- AI-интерфейсы в будущем.

Изменяет:

- Core после получения новых данных от Adapter.

Удаляет:

- физически не удаляется;
- переводится в состояние `deleted`.

---

## Tool

Создаёт:

- разработчик модуля;
- SDK в будущем.

Читает:

- Workflow;
- CLI;
- MCP;
- Planner.

Изменяет:

- только разработчик модуля.

Удаляет:

- через версионирование модуля.

---

## Adapter

Создаёт:

- разработчик модуля.

Читает:

- Tool;
- Core.

Изменяет:

- внешний мир;
- но не меняет Resource напрямую.

Удаляет:

- через отключение или удаление модуля.

---

## Workflow

Создаёт:

- пользователь;
- разработчик;
- Planner в будущем.

Читает:

- CLI;
- MCP;
- AI-интерфейсы.

Изменяет:

- пользователь или Planner.

Удаляет:

- пользователь или система управления Workflow.

---

## Event

Создаёт:

- Adapter;
- Tool;
- Workflow;
- Core.

Читает:

- Graph;
- Explain;
- Audit;
- CLI;
- AI-интерфейсы.

Изменяет:

- никто.

Удаляет:

- никто в обычном режиме;
- Event должен быть неизменяемым.

---

# 7. Главное архитектурное правило

```text
Resource описывает состояние.
Tool описывает намерение.
Adapter взаимодействует с реальным миром.
Workflow описывает сценарий.
Event фиксирует факт.
```

Если новая функция не укладывается в эту модель, сначала обсуждаем архитектуру.
