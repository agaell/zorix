
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

- read-only Docker Adapter обнаруживает Docker containers, images и networks;
- Docker Adapter строит связи container `uses_image` image и container `connected_to` network;
- read-only Linux Adapter обнаруживает один SSH host, systemd services, system memory, persistent filesystems и listening TCP/UDP sockets через OpenSSH;
- Linux Adapter строит связи host `hosts` service, `has_memory`, `mounts` и `listens_on`;
- фундамент Resource Graph предоставляет валидированную in-memory модель ресурсов и направленных связей.
- Topology Provider API задает необязательную capability, через которую адаптеры смогут предоставлять направленные связи между ресурсами.
- Topology Engine строит Resource Graph из уже обнаруженных ресурсов и optional topology providers.
- Runtime предоставляет Python API для явного цикла сканирования и построения топологии.
- Presentation Layer умеет форматировать scan results и topology results через Python API.

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

Runtime может строить topology через Python API. CLI также предоставляет команду `topology`, которая выполняет inventory scan, строит topology и выводит resources вместе с relations. CLI `scan` по-прежнему выводит только inventory, а команды `graph` пока нет.

Topology строится только для adapters, реализующих `TopologyProvider`. Docker Adapter теперь предоставляет Docker container-to-image и container-to-network topology через этот API.

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

Docker topology через Python Runtime API:

```python
from zorix_runtime import ZorixRuntime
from zorix_presentation import TopologyConsoleRenderer

runtime = ZorixRuntime()
runtime.load_plugins("./examples/plugins/docker")

scan_result = runtime.scan()
topology_result = runtime.build_topology(scan_result.resources)

text = TopologyConsoleRenderer().render(topology_result)
print(text, end="")
```

Текущая Docker-поддержка не включает управление Docker, Docker Compose topology, volumes, CLI-команду `graph`, а также web UI для topology. Текущая CLI `scan` по-прежнему отображает только inventory.

Linux host inventory можно обнаружить через OpenSSH:

```bash
export ZORIX_SSH_TARGET=tandem
zorix scan --plugins ./examples/plugins/linux
```

Текущая Linux-поддержка не включает управление systemd, journal logs, process ownership для sockets, public port accessibility, firewall analysis, disk health, memory alerts, CPU load, sudo или несколько hosts в одном adapter.

## Статус проекта

> **Ранняя стадия разработки**

Архитектура и публичный API могут изменяться по мере формирования основы проекта.

## Разработка

Клонируйте репозиторий:

```bash
git clone https://github.com/agaell/zorix.git
cd zorix
```

Настройте editable installation:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m unittest discover
```

## CLI

Показать установленную версию Zorix:

```bash
zorix --version
```

Запустить inventory scan с адаптерами из директории plugins:

```bash
zorix scan --plugins ./plugins
```

Продолжать scan после ошибок отдельных adapters:

```bash
zorix scan --plugins ./plugins --continue-on-error
```

Построить topology через CLI:

```bash
zorix topology --plugins ./examples/plugins/docker
```

Продолжать inventory scan и topology building после ошибок adapters или providers:

```bash
zorix topology \
  --plugins ./examples/plugins/docker \
  --continue-on-error
```

`zorix topology`:

- выполняет inventory scan;
- строит topology по обнаруженным resources;
- выводит resources;
- выводит relations.

Пример вывода:

```text
Status: SUCCESS
Adapters: 1
Resources: 3

Resources:
- Container: zorix-api
- Image: zorix/api:latest
- Network: backend

Topology: SUCCESS
Providers: 1
Successful providers: 1
Failed providers: 0
Resources: 3
Relations: 2

Relations:
- Container zorix-api --uses_image--> Image zorix/api:latest
- Container zorix-api --connected_to--> Network backend
```

Docker CLI требуется только при использовании Docker plugin. Команды read-only: CLI не управляет ресурсами. Relation metadata в plain-text выводе пока не показывается, JSON/YAML export пока отсутствует.

Exit codes:

- `0` — `SUCCESS`
- `1` — execution error
- `2` — usage error
- `3` — `PARTIAL` workflow
- `4` — `FAILED` workflow
