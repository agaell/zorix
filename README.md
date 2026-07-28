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

- обнаружение Docker-контейнеров через read-only Docker Adapter.
- Resource Graph foundation provides a validated in-memory model for resources and directed relations.

Run Docker container discovery through the example plugin:

```bash
zorix scan --plugins ./examples/plugins/docker
```

## Architecture Foundation

Current foundation:

```text
Adapters
    ↓
Scan Engine
    ↓
Runtime
    ↓
Resource Graph
    ↓
Presentation / future API / AI
```

Runtime does not automatically build Resource Graph yet. Resource Graph can be built explicitly from discovered resources through the public `ResourceGraphBuilder` API.

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

Exit codes:

- `0` — `SUCCESS`
- `1` — execution error
- `2` — usage error
- `3` — `PARTIAL`
- `4` — `FAILED`
