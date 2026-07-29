# Linux Adapter

`modules/linux_adapter` содержит read-only адаптер Zorix для одного Linux host, доступного через системный OpenSSH client.

Адаптер обнаруживает:

- Linux host;
- systemd services;
- состояние systemd services;
- базовую информацию об ОС, ядре и архитектуре;
- topology relation `host --hosts--> service`.

## Один target на Adapter

Один экземпляр `LinuxAdapter` представляет один SSH target.

Это сохраняет понятную изоляцию ошибок: если один сервер недоступен, ошибку получает один adapter, а другие adapters смогут продолжить работу в режиме `continue-on-error`.

## Конфигурация SSH

Zorix не хранит логины, пароли, IP-адреса или пути к ключам.

SSH configuration остаётся ответственностью OpenSSH. Пример:

```sshconfig
Host tandem
    HostName example.com
    User root
    IdentityFile ~/.ssh/id_ed25519
```

Официальный plugin читает target из environment variable:

```bash
export ZORIX_SSH_TARGET=tandem
zorix scan --plugins ./examples/plugins/linux
```

Если `ZORIX_SSH_TARGET` не задан или пустой, adapter завершится `LinuxConfigurationError`.

## Read-only команды

Адаптер выполняет только фиксированный набор remote-команд:

```text
env LC_ALL=C hostname
env LC_ALL=C uname -r
env LC_ALL=C uname -m
env LC_ALL=C cat /etc/os-release
env LC_ALL=C systemctl list-units --type=service --all --no-legend --no-pager --plain --full
```

SSH запускается через `subprocess.run(..., shell=False)` с:

```text
-o BatchMode=yes
-o ConnectTimeout=<seconds>
```

Адаптер не использует `sudo`, shell pipelines, redirects, password input или произвольные команды пользователя.

## Host Resource

Host преобразуется в `Resource`:

- `id`: `linux:host:<target>`
- `type`: `host`
- `name`: remote `hostname`, fallback - `target`
- `state`: `reachable`
- `labels`: `{}`
- `metadata`: `ssh_target`, `kernel`, `architecture`, `os_id`, `os_name`, `os_version`

## Service Resource

Каждый валидный systemd unit `.service` преобразуется в `Resource`:

- `id`: `linux:service:<target>:<unit>`
- `type`: `service`
- `name`: unit name, например `nginx.service`
- `state`: `active_state`, fallback - `unknown`
- `labels`: `{}`
- `metadata`: `host_id`, `unit`, `load_state`, `active_state`, `sub_state`, `description`

Порядок services совпадает с выводом `systemctl`. Дубликаты unit удаляются по `Resource.id`, первое появление сохраняется.

## Topology

`LinuxAdapter` структурно реализует `TopologyProvider`.

`discover_relations(context)` не выполняет SSH-команды. Он работает только с переданным `TopologyContext` и создаёт relations:

```text
linux:host:<target> --hosts--> linux:service:<target>:<unit>
```

Связи строятся только для services текущего target, имеющих matching `metadata["host_id"]`.

## Python API topology

```python
from zorix_runtime import ZorixRuntime

runtime = ZorixRuntime()
runtime.load_plugins("./examples/plugins/linux")

scan_result = runtime.scan()
topology_result = runtime.build_topology(scan_result.resources)

for relation in topology_result.graph.relations():
    print(relation.source_id, relation.type, relation.target_id)
```

## Ошибки

Все ошибки наследуются от `LinuxAdapterError`:

- `LinuxConfigurationError`;
- `SshExecutableNotFoundError`;
- `SshCommandError`;
- `SshCommandTimeoutError`;
- `LinuxOutputError`.

Command errors прерывают текущий adapter и обрабатываются стандартной семантикой `ScanEngine`: fail-fast или `continue-on-error`.

## Ограничения

В текущей версии:

- только systemd Linux;
- один target на adapter;
- только host и services;
- topology не вызывает SSH;
- нет management actions;
- нет `journalctl`;
- нет процессов;
- нет дисков и файловых систем;
- нет listening sockets;
- нет CPU/RAM metrics;
- нет `sudo`;
- нет нескольких hosts в одном adapter;
- нет Paramiko, async, retries или конфигурационного файла Zorix.
