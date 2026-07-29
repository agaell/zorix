<p align="center">
  <img src="assets/source/logo.png" alt="Zorix" width="220">
</p>

<h1 align="center">Zorix</h1>

<p align="center">
  <strong>Open-source infrastructure intelligence platform</strong>
</p>

<p align="center">
  Infrastructure as Knowledge · MCP Native · AI Native
</p>

<p align="center">
  English · <a href="README.ru.md">Русский</a>
</p>

---

## About

Zorix is an open-source platform for understanding, modeling, and managing modern infrastructure.

The project aims to combine infrastructure data, DevOps tools, MCP servers, AI agents, and plugins into a unified infrastructure model.

Zorix is currently in early development.

## Core Ideas

- Infrastructure as Knowledge
- Native Model Context Protocol support
- AI-assisted infrastructure analysis
- Extensible plugin architecture
- Local-first execution
- Explainable and human-controlled operations

## Planned Capabilities

- Unified infrastructure model
- MCP server
- Command-line interface
- Plugin SDK
- Infrastructure graph
- AI agent runtime
- Secure infrastructure operations

## Implemented Capabilities

- read-only Docker Adapter discovers Docker containers, images, and networks.
- Docker Adapter builds container `uses_image` image and container `connected_to` network relations.
- read-only Linux Adapter discovers one SSH host, systemd services, system memory, persistent filesystems, and listening TCP/UDP sockets through OpenSSH.
- Linux Adapter builds host `hosts` service, `has_memory`, `mounts`, and `listens_on` relations.
- Linux Adapter evaluates basic read-only health findings from already discovered resources.
- Linux Adapter creates dry-run action plans for systemd service start, stop, and restart.
- Resource Graph foundation provides a validated in-memory model for resources and directed relations.
- Topology Provider API defines an optional capability for adapters to provide directed resource relations.
- Topology Engine builds a Resource Graph from discovered resources and optional topology providers.
- Health Model, Health API, and Health Engine provide a read-only health evaluation vertical slice.
- Action Model, Action API, and Action Engine provide read-only safe action planning.
- Runtime provides a Python API for the explicit scan and topology-building workflow.
- Presentation Layer can format scan, topology, health, and action planning results through Python API.

Run Docker discovery through the example plugin:

```bash
zorix scan --plugins ./examples/plugins/docker
```

Run Linux host inventory through OpenSSH:

```bash
export ZORIX_SSH_TARGET=tandem
zorix scan --plugins ./examples/plugins/linux
```

Evaluate Linux health through the same snapshot-based inventory:

```bash
export ZORIX_SSH_TARGET=tandem
zorix health --plugins ./examples/plugins/linux
```

Create a dry-run Linux action plan:

```bash
export ZORIX_SSH_TARGET=tandem
zorix action plan \
  service.restart \
  linux:service:tandem:tandem.service \
  --plugins ./examples/plugins/linux
```

## Architecture Foundation

Current topology foundation:

```text
PluginLoader
    ↓
Registry
    ├── ScanEngine
    │       ↓
    │   ScanResult
    ├── HealthEngine
    │       ↓
    │   HealthResult
    ├── ActionEngine
    │       ↓
    │   ActionPlanResult
    └── TopologyEngine
            ↓
       TopologyResult
            ↓
       ResourceGraph
```

Runtime can build topology, evaluate health, and plan actions through its Python API. The CLI also provides `topology`, `health`, and `action plan` commands. CLI `scan` still outputs only inventory, and there is no `graph` command yet.

Topology is built only from adapters that implement `TopologyProvider`. Docker Adapter now provides Docker container-to-image and container-to-network topology through this API.

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

Health evaluation through the Python Runtime API:

```python
from zorix_runtime import ZorixRuntime
from zorix_presentation import HealthConsoleRenderer

runtime = ZorixRuntime()
runtime.load_plugins("./examples/plugins/linux")

scan_result = runtime.scan()
health_result = runtime.evaluate_health(scan_result.resources)

text = HealthConsoleRenderer().render(health_result)
print(text, end="")
```

Action planning through the Python Runtime API:

```python
from zorix_action_model import ActionRequest
from zorix_runtime import ZorixRuntime
from zorix_presentation import ActionPlanConsoleRenderer

runtime = ZorixRuntime()
runtime.load_plugins("./examples/plugins/linux")

scan_result = runtime.scan()
action_result = runtime.plan_action(
    scan_result.resources,
    ActionRequest("service.restart", "linux:service:tandem:tandem.service"),
)

text = ActionPlanConsoleRenderer().render(action_result)
print(text, end="")
```

Docker topology through the Python Runtime API:

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

Current Docker support does not include Docker management, Docker Compose topology, volumes, a CLI `graph` command, or a web topology UI. Current Linux support does not execute systemd actions, does not include confirmation prompts, journal logs, process ownership for sockets, public port accessibility, firewall analysis, configurable health thresholds, CPU load, sudo, or multiple hosts in one adapter. Current CLI `scan` still displays only inventory.

## Project Status

> **Early development**

The architecture and public API may change while the foundation of the project is being developed.

## Development

Clone the repository:

```bash
git clone https://github.com/agaell/zorix.git
cd zorix
```

Set up editable installation:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m unittest discover
```

## CLI

Show the installed Zorix version:

```bash
zorix --version
```

Run a resource scan with adapters loaded from a plugin directory:

```bash
zorix scan --plugins ./plugins
```

Continue scanning remaining adapters after adapter errors:

```bash
zorix scan --plugins ./plugins --continue-on-error
```

Build topology through the CLI:

```bash
zorix topology --plugins ./examples/plugins/docker
```

Continue both inventory scan and topology building after adapter or provider errors:

```bash
zorix topology \
  --plugins ./examples/plugins/docker \
  --continue-on-error
```

Evaluate health through the CLI:

```bash
zorix health --plugins ./examples/plugins/linux
```

`zorix health`:

- runs an inventory scan;
- evaluates health from discovered resources without repeating SSH;
- prints only the health report after a successful scan;
- prints scan output first only when scan is partial.

Linux health MVP treats failed services as critical, filesystem usage `>=80` as warning, filesystem usage `>=90` as critical, available memory `<=20%` as warning, and available memory `<=10%` as critical. Inactive services and sockets do not create findings in this iteration.

Create a dry-run action plan:

```bash
zorix action plan \
  service.restart \
  linux:service:tandem:tandem.service \
  --plugins ./examples/plugins/linux
```

`zorix action plan`:

- runs an inventory scan;
- finds the requested resource;
- asks an action provider for a dry-run plan;
- shows operation, risk, confirmation requirement, and steps;
- does not execute `systemctl`, SSH mutation commands, arbitrary shell commands, or server changes.

Linux action planning MVP supports only `service.start`, `service.stop`, and `service.restart` for systemd service resources. `service.stop` has `HIGH` risk; `service.start` and `service.restart` have `MEDIUM` risk. Real action execution is not implemented yet.

`zorix topology`:

- runs an inventory scan;
- builds topology from discovered resources;
- prints resources;
- prints relations.

Example output:

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

Docker CLI is required only when using the Docker plugin. Commands are read-only: the CLI does not manage resources. Relation metadata is not shown in plain-text output yet, and JSON/YAML export is not implemented.

Exit codes:

- `0` — `SUCCESS`
- `1` — execution error
- `2` — usage error
- `3` — `PARTIAL` workflow or warning health
- `4` — `FAILED` workflow, critical health, or rejected action plan
