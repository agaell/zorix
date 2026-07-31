# Linux Adapter

`modules/linux_adapter` содержит read-only адаптер Zorix для одного Linux host, доступного через системный OpenSSH client.

Адаптер обнаруживает:

- Linux host;
- systemd services;
- состояние systemd services;
- базовую информацию об ОС, ядре и архитектуре;
- system memory через `/proc/meminfo`;
- постоянные filesystems через `df`;
- listening TCP/UDP sockets через `ss`;
- topology relations от host к обнаруженным ресурсам;
- read-only health findings по уже обнаруженным resources;
- dry-run action plans для ограниченного набора systemd service actions;
- безопасное исполнение подтверждённых systemd service actions для уже построенных планов.

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

`discover()` выполняет один SSH-запуск на target:

```text
ssh -o BatchMode=yes -o ConnectTimeout=<seconds> <target> sh -s
```

Статический POSIX `sh` script передаётся в stdin. Script не формируется из пользовательского ввода и не содержит `sudo`, временных файлов, package managers, `curl`, `wget` или произвольных remote-команд.

Внутри script выполняется только фиксированный набор read-only команд:

```text
env LC_ALL=C hostname
env LC_ALL=C uname -r
env LC_ALL=C uname -m
env LC_ALL=C cat /etc/os-release
env LC_ALL=C systemctl list-units --type=service --all --no-legend --no-pager --plain --full
env LC_ALL=C cat /proc/meminfo
env LC_ALL=C df -B1 --output=source,fstype,size,used,avail,pcent,target
env LC_ALL=C ss --no-header --listening --tcp --udp --numeric
```

Каждая команда оборачивается в snapshot section с маркерами:

```text
__ZORIX_SNAPSHOT_V1_BEGIN__:<section>
...
__ZORIX_SNAPSHOT_V1_END__:<section>
```

Секции идут в стабильном порядке:

```text
hostname
kernel
architecture
os_release
services
meminfo
filesystems
sockets
```

Если одна из команд завершилась с ненулевым exit code, remote script останавливается, а `SubprocessSshCommandRunner` возвращает typed `SshCommandError` для remote command `("sh", "-s")`.

SSH запускается через `subprocess.run(..., shell=False)` с:

```text
-o BatchMode=yes
-o ConnectTimeout=<seconds>
```

Snapshot не кэшируется: каждый вызов `discover()` собирает актуальное состояние через один новый SSH subprocess.

Parser snapshot требует все секции ровно по одному разу. Malformed snapshot приводит к `LinuxOutputError` с коротким сообщением без полного stdout.

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

## Memory Resource

Память host преобразуется в один `Resource`:

- `id`: `linux:memory:<target>`
- `type`: `memory`
- `name`: `System memory`
- `state`: `present`
- `labels`: `{}`
- `metadata`: `host_id`, `total_bytes`, `available_bytes`, `used_bytes`, `free_bytes`, `buffers_bytes`, `cached_bytes`, `swap_total_bytes`, `swap_free_bytes`, `swap_used_bytes`, `usage_percent`

`usage_percent` хранится без символа `%`.

## Filesystem Resource

Каждая постоянная filesystem из `df` преобразуется в `Resource`:

- `id`: `linux:filesystem:<target>:<encoded-mountpoint>`
- `type`: `filesystem`
- `name`: mountpoint, например `/`
- `state`: `mounted`
- `labels`: `{}`
- `metadata`: `host_id`, `source`, `filesystem_type`, `size_bytes`, `used_bytes`, `available_bytes`, `usage_percent`, `mountpoint`

Mountpoint кодируется через `urllib.parse.quote(..., safe="")`.

Псевдо- и временные filesystem types исключаются: например `tmpfs`, `proc`, `sysfs`, `squashfs`, `overlay`.

## Socket Resource

Каждый listening TCP/UDP socket из `ss` преобразуется в `Resource`:

- `id`: `linux:socket:<target>:<protocol>:<encoded-address>:<port>`
- `type`: `socket`
- `name`: например `tcp://0.0.0.0:443`, `udp://*:68`, `tcp://[::]:443`
- `state`: `listening`
- `labels`: `{}`
- `metadata`: `host_id`, `protocol`, `socket_state`, `bind_address`, `port`, `bind_scope`, `address_family`

`bind_scope` может быть `all_interfaces`, `loopback`, `specific_interface` или `unknown`.

Bind на `0.0.0.0` или `::` не означает публичную доступность: adapter не анализирует firewall, NAT, security groups или routing.

Process/PID ownership для sockets пока не обнаруживается.

## Topology

`LinuxAdapter` структурно реализует `TopologyProvider`.

`discover_relations(context)` не выполняет SSH-команды. Он работает только с переданным `TopologyContext` и создаёт relations:

```text
linux:host:<target> --hosts--> linux:service:<target>:<unit>
linux:host:<target> --has_memory--> linux:memory:<target>
linux:host:<target> --mounts--> linux:filesystem:<target>:<encoded-mountpoint>
linux:host:<target> --listens_on--> linux:socket:<target>:<protocol>:<encoded-address>:<port>
```

Связи строятся только для ресурсов текущего target, имеющих matching `metadata["host_id"]`.

## Health evaluation

`LinuxAdapter` структурно реализует `HealthProvider`.

`evaluate_health(context)` не выполняет SSH-команды и не вызывает `discover()`. Evaluation работает только по `Resource`, уже полученным из snapshot scan.

Текущие встроенные правила Linux MVP:

- failed service даёт `CRITICAL linux.service.failed`, если `state`, `active_state` или `sub_state` равны `failed`;
- inactive, dead, exited, activating и deactivating services не считаются ошибкой без expected-state policy;
- filesystem usage `80-89` даёт `WARNING linux.filesystem.usage_high`;
- filesystem usage `>=90` даёт `CRITICAL linux.filesystem.usage_high`;
- available memory `<=20%` даёт `WARNING linux.memory.available_low`;
- available memory `<=10%` даёт `CRITICAL linux.memory.available_low`;
- socket resources в этой итерации не создают findings.

Некорректные metadata отдельного resource не прерывают evaluation: такой resource пропускается. Thresholds пока встроены в Linux MVP и не настраиваются.

CLI:

```bash
export ZORIX_SSH_TARGET=tandem
zorix health --plugins ./examples/plugins/linux
```

## Action planning

`LinuxAdapter` структурно реализует `ActionProvider`.

`plan_action(context, request)` не выполняет SSH, `systemctl`, `subprocess` или изменение состояния. Метод только проверяет, что request относится к Linux service resource текущего target, и возвращает dry-run `ActionPlan`.

Поддерживаемые actions Linux MVP:

- `service.start` -> `linux.systemd.start`, risk `MEDIUM`;
- `service.stop` -> `linux.systemd.stop`, risk `HIGH`;
- `service.restart` -> `linux.systemd.restart`, risk `MEDIUM`.

Все три действия требуют подтверждения перед исполнением.

Resource подходит только если это `linux:service:<target>:<unit>`, `metadata["host_id"]` указывает на текущий host, `metadata["unit"]` непустой, заканчивается на `.service`, не начинается с `-`, не содержит whitespace/control characters и совпадает с `Resource.id`.

CLI dry-run:

```bash
export ZORIX_SSH_TARGET=tandem
zorix action plan \
  service.restart \
  linux:service:tandem:tandem.service \
  --plugins ./examples/plugins/linux
```

## Action execution

`LinuxAdapter` структурно реализует `ActionExecutor` для планов, которые сам же умеет строить.

Поддерживаемые операции исполнения:

- `service.start` -> `systemctl start`;
- `service.stop` -> `systemctl stop`;
- `service.restart` -> `systemctl restart`.

Перед SSH-вызовом executor повторно проверяет план:

- `source` должен быть `linux`;
- `provider` должен совпадать с текущим классом `LinuxAdapter`;
- action и operation должны совпадать с allowlist;
- target resource должен существовать в `ActionContext`;
- resource должен быть Linux service текущего target;
- `metadata["unit"]`, `metadata["ssh_target"]` и `metadata["host_id"]` должны совпадать с resource и adapter;
- unit должен пройти тот же строгий allowlist, что и при planning;
- план должен требовать подтверждения.

Если проверка не пройдена, runner не вызывается.

Execution выполняет один SSH-вызов:

```text
ssh ... <target> sh -s -- <action-token> <unit>
```

Статический POSIX `sh` script передаётся в stdin. Он не формируется из пользовательского ввода и не содержит `sudo`, `eval`, shell interpolation пользовательских команд или произвольных аргументов.

Удалённый script выводит структурированные markers `__ZORIX_SYSTEMD_ACTION_V1_BEGIN__` и `__ZORIX_SYSTEMD_ACTION_V1_END__`. Parser требует полный набор известных ключей, отклоняет дубликаты, неизвестные ключи и content вне markers.

`SUCCESS` возвращается только если `systemctl` завершился с exit code `0` и итоговый `ActiveState` соответствует ожидаемому состоянию. Ошибки SSH преобразуются в `FAILED` результат с коротким сообщением без traceback и без полного stderr в metadata.

Arbitrary shell commands, sudo, action parameters and custom command arguments are not supported.

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

CLI topology:

```bash
export ZORIX_SSH_TARGET=tandem
zorix topology --plugins ./examples/plugins/linux
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
- host, services, memory, persistent filesystems и listening sockets;
- topology не вызывает SSH;
- health evaluation не вызывает SSH;
- action planning не вызывает SSH и не выполняет `systemctl`;
- нет management actions;
- нет action execution;
- нет confirmation prompt;
- нет rollback или audit log;
- нет `journalctl`;
- нет процессов;
- socket не связан с service;
- нет firewall analysis;
- нет настраиваемых health thresholds;
- нет CPU load, disk I/O или SMART;
- нет `sudo`;
- нет нескольких hosts в одном adapter;
- нет Paramiko, async, retries или конфигурационного файла Zorix.
