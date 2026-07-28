# Docker Adapter

`modules/docker_adapter` содержит первый read-only адаптер Zorix для обнаружения Docker-контейнеров.

Адаптер преобразует контейнеры, доступные через локальную команду `docker`, в существующие объекты `Resource` из Core Model. Он не создает отдельный тип ресурса для Docker и не изменяет контракт `Adapter`.

## Назначение

Docker Adapter отвечает только за обнаружение контейнеров.

Он не запускает, не останавливает, не изменяет и не удаляет контейнеры. Адаптер не знает о CLI, `ConsoleRenderer`, `Registry`, `ScanEngine` и `PluginLoader`. Эти компоненты остаются на своих уровнях архитектуры.

## Почему Docker CLI

В этой итерации используется установленная команда `docker`, а не Docker SDK for Python и не прямое обращение к Docker Engine API.

Такой подход оставляет модуль без внешних Python-зависимостей и сохраняет простую границу: адаптер выполняет только разрешенные read-only команды Docker CLI.

## Команды

Адаптер выполняет только две команды:

```bash
docker container ls --all --quiet --no-trunc
docker container inspect <container-id>...
```

Идентификаторы контейнеров поступают только из результата `docker container ls`. Адаптер не принимает произвольные Docker-команды из CLI, плагинов или `Resource`.

## Обнаруживаемые ресурсы

Поддерживаются running и stopped containers.

Каждый контейнер преобразуется в `Resource`:

- `id`: `docker:container:<full Docker ID>`
- `type`: `container`
- `name`: Docker `Name` без начального `/`, либо первые 12 символов ID
- `state`: `State.Status`, либо `unknown`
- `labels`: строковые пары из `Config.Labels`
- `metadata`: ограниченный набор простых строковых значений

## Metadata

В `metadata` могут попадать только доступные и непустые значения:

- `docker_id`
- `image`
- `image_id`
- `created`
- `hostname`
- `health`
- `restart_policy`
- `networks`

Docker-структуры `Config`, `HostConfig`, `State` и `NetworkSettings` целиком не сохраняются.

`networks` содержит имена сетей, отсортированные и объединенные через запятую. Сети пока не являются отдельными `Resource`.

## Ошибки

Все ошибки адаптера наследуются от `DockerAdapterError`.

Основные типы ошибок:

- `DockerExecutableNotFoundError`: команда Docker CLI не найдена.
- `DockerCommandError`: Docker CLI вернул ненулевой exit code.
- `DockerCommandTimeoutError`: команда Docker CLI превысила timeout.
- `DockerOutputError`: Docker CLI вернул некорректный или небезопасный для разбора вывод.

Адаптер не печатает stdout, stderr или traceback. Обработка пользовательского вывода остается ответственностью верхних слоев.

## Использование через PluginLoader

Пример официального плагина находится в:

```text
examples/plugins/docker
```

Запуск через CLI после editable install:

```bash
zorix scan --plugins ./examples/plugins/docker
```

При работающем Docker Engine результатом будет `SUCCESS` и список найденных контейнеров.

Если контейнеров нет, результатом будет `SUCCESS` и `Resources: 0`.

Если Docker CLI отсутствует или Docker daemon недоступен, CLI вернет execution error без Python traceback.

## Ручная smoke-проверка

```bash
docker version
zorix scan --plugins ./examples/plugins/docker
```

Эта проверка не входит в обязательные unit-тесты, потому что зависит от локального Docker Engine.

## Ограничения

В текущей итерации адаптер не поддерживает:

- Docker images как отдельные ресурсы;
- Docker networks как отдельные ресурсы;
- Docker volumes;
- Docker Compose topology;
- Docker Swarm;
- Kubernetes;
- метрики контейнеров;
- удаленный Docker host;
- изменение состояния контейнеров.

Один вызов `docker container inspect` для всех найденных контейнеров допустим для первой версии. Разбиение на batches можно рассмотреть позже для окружений с очень большим числом контейнеров.
