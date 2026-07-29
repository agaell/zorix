
## `README.ru.md`

```markdown
<p align="center">
  <img src="assets/source/logo.png" alt="Zorix" width="220">
</p>

<h1 align="center">Zorix</h1>

<p align="center">
  <strong>Open-source платформа инфраструктурного интеллекта</strong>
</p>

<p align="center">
  Infrastructure as Knowledge · MCP Native · AI Native
</p>

<p align="center">
  <a href="README.md">English</a> · Русский
</p>

---

## О проекте

Zorix — open-source платформа для исследования, моделирования и управления современной IT-инфраструктурой.

Проект должен объединить данные об инфраструктуре, DevOps-инструменты, MCP-серверы, AI-агентов и плагины в единую модель инфраструктуры.

Сейчас Zorix находится на ранней стадии разработки.

## Основные идеи

- представление инфраструктуры в виде единой модели знаний;
- нативная поддержка Model Context Protocol;
- анализ инфраструктуры с помощью AI;
- расширяемая архитектура плагинов;
- возможность локального выполнения;
- объяснимые операции под контролем человека.

## Планируемые возможности

- единая модель инфраструктуры;
- MCP-сервер;
- интерфейс командной строки;
- SDK для разработки плагинов;
- граф инфраструктуры;
- среда выполнения AI-агентов;
- безопасное выполнение инфраструктурных операций.

## Реализованные возможности

- обнаружение Docker-контейнеров через read-only Docker Adapter;
- фундамент Resource Graph предоставляет валидированную in-memory модель ресурсов и направленных связей.
- Topology Provider API задает необязательную capability, через которую адаптеры смогут предоставлять направленные связи между ресурсами.
- Topology Engine строит Resource Graph из уже обнаруженных ресурсов и optional topology providers.
- Runtime предоставляет Python API для явного цикла сканирования и построения топологии.

## Архитектурная основа

Текущая основа топологии:

```text
PluginLoader
    ↓
Registry
    ├── ScanEngine
    │       ↓
    │   ScanResult
    └── TopologyEngine
            ↓
       TopologyResult
            ↓
       ResourceGraph
```

Runtime может строить topology через Python API. Это остается явным вторым шагом: `scan()` не строит topology автоматически. CLI `scan` по-прежнему выводит только `ScanResult`, а команды `graph` пока нет. Docker Adapter пока не реализует `TopologyProvider`.

Topology строится только для adapters, реализующих `TopologyProvider`. Это пока не поддержка Docker topology.

```python
from zorix_runtime import ZorixRuntime

runtime = ZorixRuntime()
runtime.load_plugins("./plugins")

scan_result = runtime.scan(continue_on_error=True)
topology_result = runtime.build_topology(
    scan_result.resources,
    continue_on_error=True,
)
```

## Статус проекта

> **Ранняя стадия разработки**

Архитектура и публичный API могут изменяться по мере формирования основы проекта.

## Разработка

Клонируйте репозиторий:

```bash
git clone https://github.com/agaell/zorix.git
cd zorix
