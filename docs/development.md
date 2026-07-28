# Development

Этот документ описывает минимальный локальный сценарий разработки Python-модулей Zorix.

## Создание окружения

```bash
python3 -m venv .venv
```

## Активация окружения

```bash
source .venv/bin/activate
```

## Обновление pip

```bash
python -m pip install --upgrade pip
```

## Editable installation

```bash
python -m pip install -e .
```

После этого публичные Python-пакеты Zorix импортируются без ручного изменения `sys.path`.

## Запуск тестов

```bash
python -m unittest discover
```

## Деактивация окружения

```bash
deactivate
```
