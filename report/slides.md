---
marp: true
theme: stoilo
paginate: true
size: 16:9
math: katex
---

<!-- _class: title -->
<!-- _paginate: false -->

# Гибкий фреймворк распределённого глубинного обучения в среде добровольных вычислений

Миронов Сергей Дмитриевич
НИУ ВШЭ ФКН ПМИ
2026

<!--
    Название состоит из трёх частей, рассмотрим их по порядку с конца
-->

---

# Добровольные вычисления и BOINC

<div class="lead">
Добровольные вычисления — это парадигма распределённых вычислений, в которой обычные люди безвозмездно предоставляют недоиспользованные ресурсы своих устройств для решения научных задач.
<!-- Добровольные вычисления превращают недоиспользованные устройства участников в узлы распределённой системы, помогающей решать современные научные задачи. -->
</div>

- участники предоставляют ресурсы своих устройств безвозмездно;
- платформа BOINC фактически стала стандартом таких систем;
- BOINC берёт на себя планирование заданий, транспорт данных, клиентское ПО;
- модель хорошо подходит для гетерогенной и географически распределённой среды.

[Официальный сайт BOINC](https://boinc.berkeley.edu/)

<div class="note">
Примеры успешных проектов: <b>SETI@home</b>, <b>Rosetta@home</b>, <b>Folding@home</b>.
</div>

---

# Машинное обучение и BOINC

<div class="lead">
BOINC способен планировать задания, но существующие ML-проекты не предлагают исследователям высокоуровневый интерфейс.
</div>

- в MLC@Home архитектура модели была зафиксирована в C++-коде;
- DistributedDataMining (dDM) требовал ручного экспорта RapidMiner-процессов и адаптации под модель BOINC, включая разбиение вычисления на задания;
- Atre и др. якобы создали систему DDL на базе BOINC с интерфейсом TensorFlow и предложили алгоритм VC-ASGD, но исходный код их системы не опубликован;
- готового способа запускать произвольные гибко настраиваемые ML-вычисления поверх BOINC фактически не существует.

<div class="thesis">
Цель работы — создать открытый и простой в развёртывании фреймворк, который соединит вычислительные возможности BOINC с привычным для ML-инженеров Python-интерфейсом обучения моделей, например, посредством библиотеки PyTorch.
</div>

---

# STOILO
## System for Task Orchestration of Independent Loosely-coupled Operations

<div class="lead">
    Открытый фреймворк для запуска пользовательских Python-задач в добровольной вычислительной сети на базе BOINC.
</div>

- позволяет запускать произвольные Python-функции на устройствах добровольцев;
- предоставляет механизмы настройки среды исполнения: можно использовать сторонние Python-библиотеки любых версий;
- допускает комбинирование отдельных задач в сложные вычислительные сценарии благодаря асинхронности интерфейса;
- сохраняет свободу выбора моделей, алгоритма оптимизации и логики распределения глубинного обучения.

[GitHub-репозиторий STOILO](https://github.com/sermir2003/stoilo)

---

# Обзорная диаграмма STOILO

![Обзорная диаграмма STOILO](../text/figures/stoilo_overall.drawio.svg)

---

# Путь задачи

```python
import stoilo

conn = await stoilo.connect("stoilo.sermir-tech.ru/stoilo:57010")

task = conn.create_task(
    kwargs={'a': 2, 'b': 3},
    func=lambda a, b: a + b
)
task = await task.submit()
await task.result()  # 5
```

1. пользователь создаёт соединение и передаёт Callable-объект с аргументами;
1. библиотека взаимодействует с сервером по gRPC в модели Create/Poll;
1. сервер создаёт BOINC-задание, а BOINC планирует его выполнение, следит за назначениями и собирает результаты;
1. клиент BOINC на устройстве добровольца автоматически скачивает приложение и файлы задания, выполняет работу и возвращает результат.

---

# Репликация и валидация

```python
await conn.create_task(
    kwargs=dict(a=1, b=-3, c=2),
    func=quadratic_roots_harmonic_mean,
    init_valid_func=lambda res: res is None or isinstance(res, float),
    compare_valid_func=lambda x, y: (
        x is None and y is None
        or x is not None and y is not None and abs(x - y) < 1e-6
    ),
    redundancy_options=stoilo.redundancy.CreateOptions(min_quorum=3, max_total_results=5),
).result()
```

- BOINC противодействует злоумышленникам вычислительной избыточностью;
- пользователь задаёт параметры репликации: кворум и различные лимиты;
- валидаторы проверяют результаты и устанавливают их эквивалентность;
- результаты передаются в JSON-формате, что исключает атаки десериализации.

---

# Параллельность и комбинаторы

```python
async def integrate_distributed(conn, f, a, b):
    def worker(x_0, x_n, n, f):
        h = (x_n - x_0) / n
        return h * (.5 * (f(x_0) + f(x_n)) + sum(f(x_0 + j*h) for j in range(1, n)))

    step = (b - a) / 10
    tasks = [
        conn.create_task(
            kwargs={'x_0': a+i*step, 'x_n': a+(i+1)*step, 'n': 1000, 'f': f},
            func=worker,
        ) for i in range(10)
    ]
    return sum(await asyncio.gather(*(t.result() for t in tasks)))
```

- задачи комбинируются стандартными средствами *asyncio*: `gather`, `wait`, `wait_for`, `Condition`, `Semaphore`;
- их выразительности достаточно для построения сложных вычислительных сценариев;
- независимые BOINC-задания выполняются параллельно на разных устройствах.

---

# Окружения исполнения: мотивация

**Модель приложений BOINC**

1. доброволец скачивает BOINC-клиент и подключает его к проекту;
2. клиент самостоятельно запрашивает вычислительные задания;
3. в рамках задания клиент скачивает *приложение* (бинарь) и другие файлы;
4. одно приложение можно использовать во многих задачах, оно кэшируется.

**Проблема Python-окружений**

- нельзя полагаться на наличие Python на устройствах добровольцев;
- поэтому интерпретатор и библиотеки необходимо упаковать в приложение;
- упаковать все комбинации версий в одно приложение невозможно;
- доступ к сети может быть ограничен, поэтому библиотеки нельзя дозагружать.

---

# Окружения исполнения: решение

<div class="thesis">
Отдельное BOINC-приложение для каждого набора зависимостей.
</div>

<div class="runtime-split">

<div class="runtime-left">

<div class="runtime-level">
<div class="runtime-title">Спецификация Python-окружения</div>
<div class="runtime-text">версия Python, состав и версии библиотек</div>
</div>

<div class="runtime-arrow">↓</div>

<div class="runtime-level">
<div class="runtime-title">Вариант среды исполнения</div>
<div class="runtime-code">rt_&lt;flavor&gt;</div>
<div class="runtime-text">конкретный алгоритм идентификации окружения<br>полученный ID используется при создании задач</div>
</div>

<div class="runtime-arrow">↓</div>

<div class="runtime-level">
<div class="runtime-title">Сборка (варианта) среды исполнения</div>
<div class="runtime-code">rt_&lt;flavor&gt;_&lt;version&gt;_&lt;platform&gt;</div>
<div class="runtime-text">бинарный файл для конкретной платформы</div>
</div>

</div>

<div class="runtime-right">

- способ описания среды можно менять при сохранении уникальности flavor;
- для разных платформ можно использовать разные способы сборки;
- обновления сборок можно выпускать независимо друг от друга;
- новые варианты и сборки добавляются без остановки BOINC-сервера.

</div>

</div>

---

# Окружения исполнения: реализация

<div class="build-grid">

<div>

**Спецификация окружения**

<pre><code class="language-json">{
  "python_version": "3.12.3",
  "cloudpickle_version": "3.1.1",
  "requirements": ["numpy==2.2.5"],
  "modules": ["numpy"]
}</code></pre>

</div>

<div>

**Сборка для платформы**

<pre><code class="language-bash">./rt_builder.py \
  --runtime-spec numpy.json \
  --base-python ~/.pyenv/versions/3.12.3 \
  --version 1.0 \
  --platform arm64-apple-darwin</code></pre>

</div>

</div>

- Мы канонизируем JSON и вычисляем хеш SHA-256 для генерации `rt_<flavor>`, но системе важен уникальный идентификатор: формат спецификации можно менять.
- Мы создали кроссплатформенный скрипт сборки: достаточно передать интерпретатор нужной версии; виртуальное окружение, зависимости и бинарь он подготовит сам.
- Сборку следует запускать на целевой ОС: кросс-компиляция Python ненадёжна, а нужную версию интерпретатора легко установить, например, с помощью pyenv.

---

# Окружения исполнения: пример

```python
def solve_linear_system(A, b):
    import numpy as np
    return np.linalg.solve(A, b).tolist()

import numpy as np

A = np.array([[ 3,  1,  2], [ 1,  4,  0], [ 2,  0,  5]], dtype=float)
b = np.array([1, 2, 3], dtype=float)
task = conn.create_task(
    kwargs={'A': A, 'b': b},
    func=solve_linear_system,
    flavor='24a6681344294774',
    init_valid_func=lambda x: isinstance(x, list) and len(x) == 3 and all(isinstance(elem, float) for elem in x),
    compare_valid_func=lambda x, y: all(abs(elem_x - elem_y) < 1e-6 for elem_x, elem_y in zip(x, y)),
)
await task.result()
```

- `flavor` задаёт вариант среды исполнения, в которой есть NumPy;
- результат преобразуется в JSON-сериализуемый список: безопасный формат исключает атаки десериализации и не требует NumPy на сервере.

---

# Инсталляция сервера

<div class="thesis">
    STOILO — развёртываемый продукт, а не централизованный сервис.
</div>

Сервер разворачивает организация, которая способна привлечь ресурсы; например, лаборатория университета может объединить простаивающие компьютеры учебных классов или привлечь добровольцев, пользуясь своим авторитетом.

<div class="thesis">
    Развернуть сервер чрезвычайно легко благодаря созданным средствам.
</div>

- Docker-образ сервера, который при запуске сам дожидается БД, создаёт структуру BOINC-проекта, настраивает права, регистрирует приложения и поднимает веб-интерфейсы и демоны; supervisord автоматически перезапускает процессы при сбоях;
- Docker-имитатор добровольца, который сам подключается к проекту, дожидаясь его доступности если потребуется, и устойчив к перезапускам, сбоям сервера и обрывам сети;
- Docker Compose для локального развёртывания сервера, БД и набор имитаторов для демонстрации и отладки;
- Скрипт автоматической сборки вариантов исполнения для нужных платформ.

---

# Облачная инсталляция сервера

![bg right:58%](../text/figures/wide_setup.jpg)

- сервер STOILO и БД развёрнуты в Яндекс Облаке;
- куплен домен, настроено TLS;
- инсталляция доступна BOINC-клиентам в интернете.

<div class="thesis">
Сервер STOILO легко разворачивается в облаке из предоставленного Docker-образа.
</div>

---

# Участие разнородных узлов

![bg right:58%](../text/figures/three_devices_setup.jpg)

К облачной инсталляции подключены три физических устройства за NAT:

- Windows x86_64 / Intel;
- Linux x86_64 / AMD;
- macOS Arm64 / Apple Silicon.

<div class="thesis">
Сервер выдавал задачи устройствам разных платформ и выбирал подходящие сборки исполнения.
</div>

---

# ML-обёртки: синхронное обучение

<div class="ml-grid">

<div>

<pre><code class="language-python">trainer = SyncDataParallelTrainer(
    conn=stoilo_connection,
    model=cifar10_resnet18,
    loss_function_factory=\
        torch.nn.CrossEntropyLoss,
    loss_function_parameters={},
    optimizer_factory=torch.optim.Adam,
    optimizer_parameters={"lr": 0.001},
)
for epoch_index in range(num_epochs):
    for step_index in range(steps_per_epoch):
        step_loader = DataLoader(
            Subset(dataset, select_indices()),
            batch_size=128,
        )
        metrics = await trainer.train_step(
            epoch_index=epoch_index,
            step_index=step_index,
            train_loader=step_loader,
        )
model = trainer.get_model()</code></pre>

</div>

<div>

1. фиксируется состояние модели;
2. узлы вычисляют частичные градиенты;
3. градиенты усредняются;
4. оптимизатор обновляет параметры.

<pre><code class="language-python">partial_gradients = await asyncio.gather(*[
    gradients_on_worker(state, batch)
    for batch in batches
])
gradient_groups = zip(*partial_gradients)
for param, grads in zip(
    model.parameters(),
    gradient_groups,
):
    weighted = (
        size * grad
        for size, grad in zip(batch_sizes, grads)
    )
    param.grad = sum(weighted) / sum(batch_sizes)
optimizer.step()</code></pre>

</div>

</div>

---

# ML-обёртки: свобода стратегии

<div class="thesis">
    STOILO предоставляет низкоуровневый интерфейс исполнения задач, не ограничивая привычный рабочий процесс ML-инженера.
</div>

```python
trainer = StaleSyncDataParallelTrainer(
    ...
    min_completed_fraction=0.875,
    discard_late_results=True,
)
```

- можно использовать любые модели, оптимизаторы и функции потерь PyTorch;
- пользователь самостоятельно определяет обход датасета и разделение работы;
- интерфейс позволяет разделять работу и агрегировать результаты по произвольной стратегии;
- мы реализовали частично синхронную схему: она ждёт 28 из 32 задач и отбрасывает запоздавшие градиенты;
- поверх интерфейса STOILO можно реализовать и другие алгоритмы обучения.

---


# Обучение модели

![bg right:69% fit](../text/figures/losses.png)

- CIFAR-10;
- ResNet18 без предобучения;
- функция потерь устойчиво снижается;
- accuracy: **79%** и **76%**.

<div class="thesis">
Обе схемы успешно обучают модель.
</div>

---

# Результаты работы

- проанализированы существующие системы распределённого глубокого обучения в среде добровольных вычислений; выявлено отсутствие гибких высокоуровневых инструментов;
- описана и реализована система исполнения произвольных Python-задач поверх BOINC;
- разработана и реализована поддержка произвольных Python-окружений исполнения;
- подготовлены удобные средства развёртывания системы;
- продемонстрирована работа базовых сценариев на трёх разнородных добровольных узлах;
- описаны ML-обёртки и обучена модель на CIFAR-10, что подтвердило состоятельность концепции и работоспособность системы.

<div class="thesis">
Главный результат — BOINC удалось поднять на уровень удобного Python-инструмента для гибких распределённых вычислений.
Писать низкоуровневый код на C++/C больше не нужно. Работа обладает высокой новизной и практической значимостью.
</div>

---

<!-- _class: closing -->
<!-- _paginate: false -->

![bg opacity:.5](../text/figures/windows_participation.jpg)

# Спасибо за внимание

## Пожалуйста, задавайте вопросы
