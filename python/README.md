# bowhard-speech

Python-клиент сервисов [Bowhard](https://bowhard.ru): **расшифровка аудио и видео в текст**
и **озвучка текста нейросетью**. Без зависимостей — только стандартная библиотека.

*Speech-to-text and text-to-speech client for the Bowhard services (Russian speech, SRT subtitles,
word-level timings). Pure standard library, no dependencies.*

## Установка

```bash
pip install bowhard-speech
```

## Быстрый старт

```python
from bowhard_speech import Client

client = Client()

# расшифровка: файл → текст, субтитры, тайминги по словам
job = client.transcribe("soveschanie.mp3")
client.wait(job.id)
print(client.text(job.id))                     # готовый текст с пунктуацией
client.save(job.id, "srt", "soveschanie.srt")  # субтитры, строки до 42 знаков
words = client.words(job.id)                   # тайминги каждого слова

# озвучка: текст → mp3
job = client.synthesize("Здравствуйте! Это тестовая фраза.", voice="alena", speed=1.0)
client.wait(job.id)
client.save(job.id, "mp3", "speech.mp3")
```

Расшифровка по ссылке (Яндекс.Диск или Dropbox — публичная ссылка):

```python
job = client.transcribe_link("https://disk.yandex.ru/d/XXXXXXXX")
client.wait(job.id)
print(client.text(job.id))
```

## Командная строка

```bash
bowhard-speech transcribe soveschanie.mp3 -o protokol.txt --srt protokol.srt
bowhard-speech say "Текст для озвучки" -o privet.mp3 --voice alena --speed 1.1
bowhard-speech link https://disk.yandex.ru/d/XXXXXXXX -o protokol.txt
bowhard-speech prices --voices
```

## Что умеет сервис

| | расшифровка | озвучка |
| --- | --- | --- |
| вход | mp3, wav, ogg/opus, m4a — файлом или по ссылке | текст до 100 000 знаков |
| выход | текст, `.srt`, `.json` с таймингами слов | mp3 |
| бесплатно | 15 минут в сутки | 5 000 знаков в сутки |
| цена | 25 ₽ за час записи | 3,9 ₽ за 1 000 знаков |

Результаты задач хранятся 24 часа. Запись на час — это примерно 8–10 тысяч слов,
ручной протокол такого совещания занимает 20–40 минут работы секретаря.

## Как это устроено

- `Client.transcribe()` отправляет файл `multipart/form-data` в `/stt`, `Client.synthesize()` —
  JSON в `/tts`.
- Сервис привязывает задачи к анонимному идентификатору в подписанной cookie, поэтому
  один клиент — один владелец задач; cookie хранит `http.cookiejar` внутри `Client`.
- `Client.wait()` опрашивает `/job/<id>` раз в 3 секунды, `BowhardError` содержит текст ошибки,
  HTTP-статус и тело ответа (например, `402` — исчерпан бесплатный лимит, с ценой в `payload`).

## Лицензия

MIT. Сервис работает на [bowhard.ru](https://bowhard.ru) — расшифровка записей:
<https://bowhard.ru/rasshifrovka>, озвучка: <https://bowhard.ru/ozvuchka>.
