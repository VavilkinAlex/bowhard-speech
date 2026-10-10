# bowhard-speech (Node.js)

Node-клиент сервисов [Bowhard](https://bowhard.ru): **расшифровка аудио и видео в текст**
и **озвучка текста нейросетью**. Без зависимостей — только встроенный `fetch` (Node 18+).

*Speech-to-text and text-to-speech client for the Bowhard services (Russian speech, SRT subtitles,
word-level timings). Zero dependencies, Node 18+.*

## Установка

```bash
npm install bowhard-speech
```

## Быстрый старт

```js
import { Client } from 'bowhard-speech';

const client = new Client();

// расшифровка: файл → текст, субтитры, тайминги по словам
const job = await client.transcribe('soveschanie.mp3');
await client.wait(job.id);
console.log(await client.text(job.id));            // готовый текст с пунктуацией
await client.save(job.id, 'srt', 'soveschanie.srt'); // субтитры, строки до 42 знаков
const words = await client.words(job.id);          // тайминги каждого слова

// озвучка: текст → mp3
const speech = await client.synthesize('Здравствуйте! Это тестовая фраза.', { voice: 'alena', speed: 1.0 });
await client.wait(speech.id);
await client.save(speech.id, 'mp3', 'speech.mp3');
```

Расшифровка по ссылке (Яндекс.Диск или Dropbox — публичная ссылка):

```js
const job = await client.transcribeLink('https://disk.yandex.ru/d/XXXXXXXX');
await client.wait(job.id);
console.log(await client.text(job.id));
```

## Командная строка

```bash
npx bowhard-speech transcribe soveschanie.mp3 -o protokol.txt --srt protokol.srt
npx bowhard-speech say "Текст для озвучки" -o privet.mp3 --voice alena --speed 1.1
npx bowhard-speech link https://disk.yandex.ru/d/XXXXXXXX
npx bowhard-speech prices
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

- `transcribe()` отправляет файл через `FormData`, `synthesize()` — JSON в `/tts`.
- Сервис привязывает задачи к анонимному идентификатору в подписанной cookie, поэтому
  один клиент — один владелец задач; cookie хранит сам `Client`.
- `wait()` опрашивает `/job/<id>` раз в 3 секунды, `BowhardError` содержит текст ошибки,
  HTTP-статус и тело ответа (`402` — исчерпан бесплатный лимит, цена лежит в `payload`).
- Сетевые сбои повторяются до трёх раз, прежде чем клиент сдаётся.

Для n8n есть готовые workflow: <https://github.com/VavilkinAlex/n8n-bowhard-templates>.

## Лицензия

MIT. Сервис работает на [bowhard.ru](https://bowhard.ru) — расшифровка записей:
<https://bowhard.ru/rasshifrovka>, озвучка: <https://bowhard.ru/ozvuchka>.
