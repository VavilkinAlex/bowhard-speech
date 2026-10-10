"""Клиент сервисов Bowhard: расшифровка аудио и видео в текст и озвучка текста.

Работает на стандартной библиотеке Python (без зависимостей).

    from bowhard_speech import Client

    client = Client()

    # расшифровка: файл → текст, субтитры, тайминги по словам
    job = client.transcribe("soveschanie.mp3")
    client.wait(job.id)
    print(client.text(job.id))
    open("soveschanie.srt", "w", encoding="utf-8").write(client.srt(job.id))

    # озвучка: текст → mp3
    job = client.synthesize("Здравствуйте! Это тестовая фраза.", voice="alena")
    client.wait(job.id)
    open("speech.mp3", "wb").write(client.audio(job.id))

Бесплатные лимиты сервиса: 15 минут расшифровки и 5 000 знаков озвучки в сутки
на один адрес. Дальше — по цене из ``client.prices()``.
"""
from __future__ import annotations

import json
import mimetypes
import os
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from http.cookiejar import CookieJar
from typing import Any, Callable, Dict, List, Optional

__all__ = ["Client", "Job", "BowhardError", "DEFAULT_BASE_URL"]
__version__ = "0.1.0"

DEFAULT_BASE_URL = "https://bowhard.ru/api/tools"
USER_AGENT = f"bowhard-speech/{__version__} (+https://bowhard.ru)"


class BowhardError(RuntimeError):
    """Ошибка сервиса: сеть, лимит, платный тариф или внутренний сбой."""

    def __init__(self, message: str, status: Optional[int] = None, payload: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status = status
        self.payload = payload or {}


@dataclass
class Job:
    """Задача сервиса: расшифровка (kind='stt') или озвучка (kind='tts')."""

    id: str
    kind: str
    status: str
    stage: str = ""
    error: Optional[str] = None
    name: Optional[str] = None
    duration_sec: Optional[float] = None
    chars: Optional[int] = None
    voice: Optional[str] = None
    cost_rub: Optional[float] = None
    free: bool = False
    files: List[Dict[str, str]] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def done(self) -> bool:
        return self.status == "done"

    @property
    def failed(self) -> bool:
        return self.status in ("error", "failed")

    def __str__(self) -> str:  # pragma: no cover - удобство в консоли
        tail = f" — {self.error}" if self.error else ""
        return f"<Job {self.id[:8]} {self.kind} {self.status} {self.stage}{tail}>"


class Client:
    """Клиент HTTP API Bowhard.

    Cookie-сессия сохраняется внутри клиента: сервис привязывает задачи к анонимному
    идентификатору в подписанной cookie, поэтому один экземпляр ``Client`` — один владелец задач.
    """

    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    # ---------- служебное

    def _request(self, path: str, data: Optional[bytes] = None, content_type: Optional[str] = None) -> bytes:
        url = f"{self.base_url}{path}"
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        if content_type:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(url, data=data, headers=headers)
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            body = error.read()
            payload: Dict[str, Any] = {}
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception:  # noqa: BLE001
                payload = {"error": body.decode("utf-8", "replace")[:300]}
            raise BowhardError(payload.get("error") or f"HTTP {error.code}", error.code, payload) from None
        except urllib.error.URLError as error:
            raise BowhardError(f"сеть недоступна: {error.reason}") from None

    @staticmethod
    def _multipart(field_name: str, filename: str, content: bytes, extra: Optional[Dict[str, str]] = None):
        boundary = uuid.uuid4().hex
        chunks: List[bytes] = []
        for key, value in (extra or {}).items():
            chunks.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode("utf-8")
            )
        guessed = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        chunks.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{field_name}"; '
            f'filename="{os.path.basename(filename)}"\r\nContent-Type: {guessed}\r\n\r\n'.encode("utf-8")
        )
        chunks.append(content)
        chunks.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
        return b"".join(chunks), f"multipart/form-data; boundary={boundary}"

    @staticmethod
    def _job(payload: Dict[str, Any]) -> Job:
        return Job(
            id=payload.get("id") or payload.get("jobId", ""),
            kind=payload.get("kind", ""),
            status=payload.get("status", ""),
            stage=payload.get("stage", ""),
            error=payload.get("error"),
            name=payload.get("name"),
            duration_sec=payload.get("durationSec"),
            chars=payload.get("chars"),
            voice=payload.get("voice"),
            cost_rub=payload.get("costRub"),
            free=bool(payload.get("free")),
            files=payload.get("files") or [],
            raw=payload,
        )

    # ---------- справка

    def prices(self) -> Dict[str, Any]:
        """Цены, бесплатные лимиты и остаток бесплатных минут у текущего клиента."""
        return json.loads(self._request("/prices").decode("utf-8"))

    def voices(self) -> List[Dict[str, str]]:
        """Список голосов для озвучки."""
        payload = json.loads(self._request("/voices").decode("utf-8"))
        return payload.get("voices") or payload

    # ---------- задачи

    def transcribe(self, path: str) -> Job:
        """Расшифровать локальный файл (mp3, wav, ogg/opus, m4a и другие, до 150 МБ)."""
        with open(path, "rb") as handle:
            content = handle.read()
        body, content_type = self._multipart("file", os.path.basename(path), content)
        return self._job(json.loads(self._request("/stt", body, content_type).decode("utf-8")))

    def transcribe_link(self, url: str) -> Job:
        """Расшифровать запись по публичной ссылке Яндекс.Диска или Dropbox."""
        body = json.dumps({"url": url}).encode("utf-8")
        return self._job(json.loads(self._request("/link", body, "application/json").decode("utf-8")))

    def synthesize(self, text: str, voice: str = "alena", speed: float = 1.0) -> Job:
        """Озвучить текст (до 100 000 знаков), скорость 0.5–2.0."""
        body = json.dumps({"text": text, "voice": voice, "speed": speed}).encode("utf-8")
        return self._job(json.loads(self._request("/tts", body, "application/json").decode("utf-8")))

    def job(self, job_id: str) -> Job:
        """Текущее состояние задачи."""
        return self._job(json.loads(self._request(f"/job/{job_id}").decode("utf-8")))

    def wait(
        self,
        job_id: str,
        timeout: float = 3600.0,
        interval: float = 3.0,
        on_progress: Optional[Callable[[Job], None]] = None,
    ) -> Job:
        """Дождаться завершения задачи. Раз в ``interval`` секунд — опрос состояния."""
        deadline = time.time() + timeout
        job = self.job(job_id)
        while not (job.done or job.failed):
            if time.time() > deadline:
                raise BowhardError(f"задача {job_id} не завершилась за {timeout:.0f} с")
            if on_progress:
                on_progress(job)
            time.sleep(interval)
            job = self.job(job_id)
        if job.failed:
            raise BowhardError(job.error or "задача завершилась с ошибкой", payload=job.raw)
        return job

    # ---------- результаты

    def file(self, job_id: str, kind: str) -> bytes:
        """Байты результата: txt | srt | json | mp3."""
        return self._request(f"/job/{job_id}/file/{kind}")

    def text(self, job_id: str) -> str:
        """Готовый текст расшифровки с пунктуацией и заглавными буквами."""
        return self.file(job_id, "txt").decode("utf-8")

    def srt(self, job_id: str) -> str:
        """Субтитры SRT (строки не длиннее 42 знаков)."""
        return self.file(job_id, "srt").decode("utf-8")

    def words(self, job_id: str) -> Dict[str, Any]:
        """Тайминги: JSON с массивом слов и временем начала/конца."""
        return json.loads(self.file(job_id, "json").decode("utf-8"))

    def audio(self, job_id: str) -> bytes:
        """MP3 с озвучкой."""
        return self.file(job_id, "mp3")

    def save(self, job_id: str, kind: str, destination: str) -> str:
        """Сохранить результат в файл и вернуть путь."""
        with open(destination, "wb") as handle:
            handle.write(self.file(job_id, kind))
        return destination
