# bowhard-speech

Client libraries for the [Bowhard](https://bowhard.ru) speech services:

* **speech-to-text** — audio and video to text, subtitles (SRT) and word-level timings ([docs](https://bowhard.ru/rasshifrovka));
* **text-to-speech** — text to MP3 with a choice of Russian voices ([docs](https://bowhard.ru/ozvuchka)).

Both clients are zero-dependency: they speak to the public HTTP API described at <https://bowhard.ru/api>.
No API key is needed — the service identifies a client by a signed cookie it hands out on the first request.

```
python/   Python client (3.9+), console script `bowhard-speech`
node/     Node client (18+), bin `bowhard-speech`
```

## Install

Python — from the release artifact:

```bash
pip install https://github.com/VavilkinAlex/bowhard-speech/releases/download/v0.1.0/bowhard_speech-0.1.0-py3-none-any.whl
```

Node — either from the tarball in the release, or from GitHub Packages:

```bash
npm install https://github.com/VavilkinAlex/bowhard-speech/releases/download/v0.1.0/bowhard-speech-0.1.0.tgz
npm install @vavilkinalex/bowhard-speech --registry=https://npm.pkg.github.com
```

## Quick start (Python)

```python
from bowhard_speech import Client

c = Client()                       # https://bowhard.ru/api/tools
job = c.transcribe("meeting.ogg")  # upload + wait
print(job.text)
job.save_srt("meeting.srt")

tts = c.synthesize("Проверка озвучки", voice="alena")
tts.save("voice.mp3")
```

## Quick start (Node)

```js
import { Client } from './node/index.js';

const c = new Client();
const job = await c.transcribe('meeting.ogg');
console.log(job.text);
await job.saveSrt('meeting.srt');

const tts = await c.synthesize('Проверка озвучки', { voice: 'alena' });
await tts.save('voice.mp3');
```

## What the API returns

| method | result |
| --- | --- |
| `transcribe(file)` / `transcribeLink(url)` | `txt`, `srt`, `json` with word timings |
| `synthesize(text, {voice, speed})` | MP3 (speed is clamped to 0.5–2.0) |
| `prices()`, `voices()` | current prices and the voice list |

Free daily allowance: 15 minutes of recognition and 5 000 characters of synthesis, then 25 ₽ per hour
and 3.9 ₽ per 1 000 characters. See <https://bowhard.ru/api> for limits, storage and the raw HTTP contract.

## License

MIT
