"""Командная строка: bowhard-speech transcribe <файл> | say "<текст>" | link <url> | job <id>."""
from __future__ import annotations

import argparse
import sys

from .client import BowhardError, Client


def _progress(job) -> None:
    print(f"  {job.status} · {job.stage}", file=sys.stderr)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="bowhard-speech",
        description="Расшифровка аудио и видео в текст и озвучка текста через сервисы Bowhard (bowhard.ru)",
    )
    parser.add_argument("--base-url", default=None, help="адрес API, по умолчанию https://bowhard.ru/api/tools")
    sub = parser.add_subparsers(dest="command", required=True)

    transcribe = sub.add_parser("transcribe", help="расшифровать файл")
    transcribe.add_argument("file")
    transcribe.add_argument("-o", "--out", default=None, help="куда сохранить текст (по умолчанию — на экран)")
    transcribe.add_argument("--srt", default=None, help="сохранить субтитры SRT")
    transcribe.add_argument("--json", dest="json_path", default=None, help="сохранить тайминги слов")

    link = sub.add_parser("link", help="расшифровать по ссылке Яндекс.Диска или Dropbox")
    link.add_argument("url")
    link.add_argument("-o", "--out", default=None)

    say = sub.add_parser("say", help="озвучить текст")
    say.add_argument("text")
    say.add_argument("-o", "--out", default="speech.mp3")
    say.add_argument("--voice", default="alena")
    say.add_argument("--speed", type=float, default=1.0)

    job_cmd = sub.add_parser("job", help="состояние задачи")
    job_cmd.add_argument("id")

    prices = sub.add_parser("prices", help="цены и бесплатные лимиты")
    prices.add_argument("--voices", action="store_true", help="ещё и список голосов")

    args = parser.parse_args(argv)
    client = Client(base_url=args.base_url) if args.base_url else Client()

    try:
        if args.command == "prices":
            print(f"расшифровка: {client.prices()}")
            if args.voices:
                for voice in client.voices():
                    print(f"  {voice.get('id')}: {voice.get('title') or voice.get('name')}")
            return 0

        if args.command == "transcribe":
            job = client.transcribe(args.file)
        elif args.command == "link":
            job = client.transcribe_link(args.url)
        elif args.command == "say":
            job = client.synthesize(args.text, voice=args.voice, speed=args.speed)
        else:
            job = client.job(args.id)
            print(job.raw)
            return 0

        print(f"задача {job.id} принята ({job.status})", file=sys.stderr)
        job = client.wait(job.id, on_progress=_progress)

        if args.command == "say":
            path = client.save(job.id, "mp3", args.out)
            print(path)
            return 0

        text = client.text(job.id)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as handle:
                handle.write(text)
            print(args.out)
        else:
            print(text)
        if getattr(args, "srt", None):
            client.save(job.id, "srt", args.srt)
            print(args.srt, file=sys.stderr)
        if getattr(args, "json_path", None):
            client.save(job.id, "json", args.json_path)
            print(args.json_path, file=sys.stderr)
        return 0
    except BowhardError as error:
        print(f"ошибка: {error}", file=sys.stderr)
        if error.status == 402:
            print(f"нужна оплата: {error.payload}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
