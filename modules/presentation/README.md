# Presentation Layer

`modules/presentation` содержит независимый слой представления результатов сканирования Zorix.

Presentation Layer получает уже сформированный `ScanResult` и возвращает готовый текст для терминала. Он не запускает сканирование, не загружает плагины, не регистрирует адаптеры и не разбирает аргументы командной строки.

## Почему renderer не печатает напрямую

`ConsoleRenderer` возвращает строку, но не вызывает `print()`.

Это сохраняет разделение ответственности: renderer отвечает только за форматирование, а будущий CLI или другой вызывающий слой решает, куда отправить текст.

## Отличие от CLI

CLI будет отвечать за аргументы командной строки, коды выхода, ввод-вывод и пользовательские команды.

Presentation Layer отвечает только за преобразование `ScanResult` в текст.

## Текстовый формат

Успешный результат:

```text
Status: SUCCESS
Adapters: 1
Resources: 2

Resources:
- Service: api
- Container: nginx
```

Частичный результат:

```text
Status: PARTIAL
Adapters: 2
Resources: 1
Errors: 1

Resources:
- Service: api

Errors:
- example.adapters.BrokenAdapter: RuntimeError: connection failed
```

Неуспешный результат:

```text
Status: FAILED
Adapters: 2
Resources: 0
Errors: 2

Errors:
- example.FirstAdapter: RuntimeError: first failure
- example.SecondAdapter: ValueError: second failure
```

## Fallback для неизвестных ресурсов

Для типа ресурса renderer использует:

1. непустое поле `kind`, если оно есть;
2. поле `type` для базового `Resource`;
3. имя класса ресурса.

Для отображаемого имени renderer использует первое непустое значение:

1. `name`;
2. `id`;
3. `identifier`.

Если этих полей нет, для dataclass формируется компактная строка публичных полей в порядке объявления. Для неизвестных объектов используется строковое представление, если оно информативно, иначе имя класса.

## Пример использования

```python
from zorix_presentation import ConsoleRenderer

renderer = ConsoleRenderer()
text = renderer.render(result, adapter_count=len(runtime.adapters()))
print(text, end="")
```

`print()` находится снаружи renderer.
