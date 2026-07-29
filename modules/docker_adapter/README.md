# Docker Adapter

`modules/docker_adapter` содержит read-only адаптер Zorix для локального Docker Engine.

Адаптер реализует базовый контракт `Adapter` и структурно реализует capability `TopologyProvider`: он предоставляет метод `discover_relations(context)`, но не наследует `TopologyProvider` явно.

## Роль

Docker Adapter отвечает за две операции:

- inventory discovery: обнаружение Docker containers, images и networks как `Resource`;
- topology discovery: построение связей между уже обнаруженными Docker resources.

Адаптер не управляет Docker, не изменяет контейнеры, образы или сети, не читает конфигурационные файлы и не форматирует вывод для CLI.

## Read-only команды

Адаптер выполняет только следующие Docker CLI команды:

```bash
docker container ls --all --quiet --no-trunc
docker container inspect <container-id>...
docker image ls --all --quiet --no-trunc
docker image inspect <image-id>...
docker network ls --quiet --no-trunc
docker network inspect <network-id>...
```

Команды запускаются без shell. Аргументы формируются только из фиксированных подкоманд, ID из Docker inventory и namespaced `Resource.id` из `TopologyContext`.

## Resource mapping

`discover()` возвращает ресурсы в фиксированном порядке:

1. containers;
2. images;
3. networks.

Внутри каждой категории сохраняется порядок `docker inspect`.

### Container Resource

- `id`: `docker:container:<full Docker ID>`
- `type`: `container`
- `name`: Docker `Name` без одного начального `/`, fallback - первые 12 символов ID
- `state`: `State.Status`, fallback - `unknown`
- `labels`: строковые пары из `Config.Labels`
- `metadata`: `docker_id`, `image`, `image_id`, `created`, `hostname`, `health`, `restart_policy`, `networks`

### Image Resource

- `id`: `docker:image:<full image ID>`
- `type`: `image`
- `name`: первый валидный `RepoTags`, кроме `<none>:<none>`, fallback - short image ID
- `state`: `present`
- `labels`: строковые пары из `Config.Labels`
- `metadata`: `docker_id`, `created`, `architecture`, `os`, `variant`, `size_bytes`, `repo_tags`, `repo_digests`

`present` означает, что образ есть в локальном Docker Engine. Это не runtime-состояние.

### Network Resource

- `id`: `docker:network:<full network ID>`
- `type`: `network`
- `name`: Docker `Name`, fallback - первые 12 символов ID
- `state`: `present`
- `labels`: строковые пары из верхнего поля `Labels`
- `metadata`: `docker_id`, `driver`, `scope`, `created`, `internal`, `attachable`, `ingress`, `ipv6`, `ipam_driver`, `subnets`, `gateways`

`present` означает, что сеть зарегистрирована в Docker Engine.

## Topology mapping

`discover_relations(context)` работает только с ресурсами:

- `resource.type == "container"`;
- `resource.id` начинается с `docker:container:`.

Метод не вызывает `container ls`. Он получает Docker IDs из `TopologyContext`, выполняет новый `docker container inspect <id>...` и возвращает только `ResourceRelation`.

### uses_image

Связь создается из контейнера к образу:

```text
docker:container:<container-id> --uses_image--> docker:image:<image-id>
```

Источник:

- container `Id`;
- container `Image`;
- optional metadata `reference` из `Config.Image`.

Связь создается только если container и image уже есть в `TopologyContext`.

### connected_to

Связь создается из контейнера к сети:

```text
docker:container:<container-id> --connected_to--> docker:network:<network-id>
```

Источник:

- container `Id`;
- `NetworkSettings.Networks[*].NetworkID`;
- optional metadata `network_name`, `ipv4_address`, `ipv6_address`, `mac_address`.

Связь создается только если container и network уже есть в `TopologyContext`.

## Порядок relations

Порядок связей фиксирован:

1. порядок Docker container resources в `TopologyContext`;
2. для каждого контейнера сначала `uses_image`;
3. затем `connected_to` в порядке `NetworkSettings.Networks`.

Дубликаты relations удаляются по `relation.identity`; первое появление сохраняется. `metadata` не участвует в identity.

## Drift между scan и topology

Docker Engine может измениться между `runtime.scan()` и `runtime.build_topology(...)`.

Правила текущей версии:

- relation создается только при наличии обоих endpoint в `TopologyContext`;
- новые Docker objects, которых не было в scan result, игнорируются;
- исчезнувший контейнер может отсутствовать в повторном inspect output;
- отсутствие inspect item само по себе не считается ошибкой;
- malformed inspect JSON остается `DockerOutputError`.

Адаптер не хранит скрытый mutable cache между `discover()` и `discover_relations()`. Поэтому topology step выполняет повторный `docker container inspect`. Возможная будущая оптимизация - immutable discovery snapshot.

## Пример Python API

```python
from zorix_runtime import ZorixRuntime

runtime = ZorixRuntime()
runtime.load_plugins("./examples/plugins/docker")

scan_result = runtime.scan()
topology_result = runtime.build_topology(scan_result.resources)

for relation in topology_result.graph.relations():
    print(relation.source_id, relation.type, relation.target_id)
```

CLI `scan` отображает найденные `Resource`, но пока не отображает `Relation`. Команды `graph` в этой итерации нет.

## Использование через PluginLoader

Пример плагина находится в:

```text
examples/plugins/docker
```

Плагин экспортирует:

```python
Adapter = DockerAdapter
```

Он не дублирует реализацию адаптера.

## Ограничения

В текущей версии не поддерживаются:

- Docker volumes;
- mounts topology;
- published ports как отдельные ресурсы;
- Docker Compose topology;
- Docker Swarm;
- Kubernetes;
- logs;
- metrics;
- retries;
- async или parallel inspect;
- chunking больших inspect-запросов;
- cache;
- remote Docker context configuration;
- Docker SDK или Engine API;
- CLI graph;
- renderer для relations;
- persistence.

Возможные будущие улучшения: inspect chunking, immutable inventory snapshot, Docker engine identity, Docker context support, volume resources, mount relations, published port resources и Compose service topology.
