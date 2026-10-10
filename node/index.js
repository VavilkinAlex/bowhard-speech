/**
 * Клиент сервисов Bowhard: расшифровка аудио и видео в текст и озвучка текста.
 *
 *   import { Client } from 'bowhard-speech';
 *
 *   const client = new Client();
 *
 *   const job = await client.transcribe('soveschanie.mp3');
 *   await client.wait(job.id);
 *   console.log(await client.text(job.id));
 *   await client.save(job.id, 'srt', 'soveschanie.srt');
 *
 *   const speech = await client.synthesize('Здравствуйте! Это тестовая фраза.', { voice: 'alena' });
 *   await client.wait(speech.id);
 *   await client.save(speech.id, 'mp3', 'speech.mp3');
 *
 * Бесплатные лимиты: 15 минут расшифровки и 5 000 знаков озвучки в сутки на адрес.
 * Дальше — по цене из client.prices(). Результаты задач живут 24 часа.
 */
import { readFile, writeFile } from 'node:fs/promises';
import { basename } from 'node:path';

export const DEFAULT_BASE_URL = 'https://bowhard.ru/api/tools';
const VERSION = '0.1.0';
const USER_AGENT = `bowhard-speech/${VERSION} (+https://bowhard.ru)`;

export class BowhardError extends Error {
  constructor(message, status = null, payload = {}) {
    super(message);
    this.name = 'BowhardError';
    this.status = status;
    this.payload = payload;
  }
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export class Client {
  /**
   * @param {{baseUrl?: string, timeout?: number}} [options]
   * Сервис привязывает задачи к анонимному идентификатору в подписанной cookie,
   * поэтому один экземпляр Client — один владелец задач.
   */
  constructor(options = {}) {
    this.baseUrl = (options.baseUrl || DEFAULT_BASE_URL).replace(/\/+$/, '');
    this.timeout = options.timeout ?? 120000;
    this.cookies = new Map();
  }

  async #request(path, init = {}) {
    const headers = new Headers(init.headers || {});
    headers.set('user-agent', USER_AGENT);
    headers.set('accept', 'application/json');
    if (this.cookies.size) {
      headers.set('cookie', [...this.cookies].map(([k, v]) => `${k}=${v}`).join('; '));
    }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeout);
    let response;
    let lastError = null;
    for (let attempt = 0; attempt < 3; attempt += 1) {
      try {
        response = await fetch(`${this.baseUrl}${path}`, { ...init, headers, signal: controller.signal });
        lastError = null;
        break;
      } catch (error) {
        lastError = error;
        if (attempt < 2) await sleep(500 * (attempt + 1));
      }
    }
    clearTimeout(timer);
    if (!response) {
      const reason = lastError?.cause?.message || lastError?.message || 'неизвестная причина';
      throw new BowhardError(`сеть недоступна: ${reason}`);
    }
    const setCookies = response.headers.getSetCookie?.() || [];
    for (const line of setCookies) {
      const [pair] = line.split(';');
      const index = pair.indexOf('=');
      if (index > 0) this.cookies.set(pair.slice(0, index).trim(), pair.slice(index + 1).trim());
    }
    if (!response.ok) {
      const raw = await response.text();
      let payload = {};
      try {
        payload = JSON.parse(raw);
      } catch {
        payload = { error: raw.slice(0, 300) };
      }
      throw new BowhardError(payload.error || `HTTP ${response.status}`, response.status, payload);
    }
    return response;
  }

  #job(payload) {
    return {
      id: payload.id || payload.jobId || '',
      kind: payload.kind || '',
      status: payload.status || '',
      stage: payload.stage || '',
      error: payload.error || null,
      name: payload.name || null,
      durationSec: payload.durationSec ?? null,
      chars: payload.chars ?? null,
      voice: payload.voice ?? null,
      costRub: payload.costRub ?? null,
      free: Boolean(payload.free),
      files: payload.files || [],
      raw: payload,
    };
  }

  /** Цены, бесплатные лимиты и остаток бесплатных минут. */
  async prices() {
    return (await this.#request('/prices')).json();
  }

  /** Список голосов для озвучки. */
  async voices() {
    const payload = await (await this.#request('/voices')).json();
    return payload.voices || payload;
  }

  /** Расшифровать локальный файл (mp3, wav, ogg/opus, m4a; до 150 МБ). */
  async transcribe(filePath) {
    const data = await readFile(filePath);
    const form = new FormData();
    form.append('file', new Blob([data]), basename(filePath));
    const response = await this.#request('/stt', { method: 'POST', body: form });
    return this.#job(await response.json());
  }

  /** Расшифровать запись по публичной ссылке Яндекс.Диска или Dropbox. */
  async transcribeLink(url) {
    const response = await this.#request('/link', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    return this.#job(await response.json());
  }

  /** Озвучить текст (до 100 000 знаков), скорость 0.5–2.0. */
  async synthesize(text, options = {}) {
    const response = await this.#request('/tts', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ text, voice: options.voice || 'alena', speed: options.speed ?? 1.0 }),
    });
    return this.#job(await response.json());
  }

  /** Состояние задачи. */
  async job(jobId) {
    return this.#job(await (await this.#request(`/job/${jobId}`)).json());
  }

  /** Дождаться завершения задачи. */
  async wait(jobId, options = {}) {
    const timeout = options.timeout ?? 3600000;
    const interval = options.interval ?? 3000;
    const deadline = Date.now() + timeout;
    let job = await this.job(jobId);
    while (job.status !== 'done' && !['error', 'failed'].includes(job.status)) {
      if (Date.now() > deadline) throw new BowhardError(`задача ${jobId} не завершилась за ${timeout} мс`);
      options.onProgress?.(job);
      await sleep(interval);
      job = await this.job(jobId);
    }
    if (job.status !== 'done') throw new BowhardError(job.error || 'задача завершилась с ошибкой', null, job.raw);
    return job;
  }

  /** Байты результата: txt | srt | json | mp3. */
  async file(jobId, kind) {
    const response = await this.#request(`/job/${jobId}/file/${kind}`);
    return Buffer.from(await response.arrayBuffer());
  }

  /** Готовый текст расшифровки. */
  async text(jobId) {
    return (await this.file(jobId, 'txt')).toString('utf8');
  }

  /** Субтитры SRT. */
  async srt(jobId) {
    return (await this.file(jobId, 'srt')).toString('utf8');
  }

  /** Тайминги слов (JSON). */
  async words(jobId) {
    return JSON.parse((await this.file(jobId, 'json')).toString('utf8'));
  }

  /** MP3 с озвучкой. */
  async audio(jobId) {
    return this.file(jobId, 'mp3');
  }

  /** Сохранить результат в файл. */
  async save(jobId, kind, destination) {
    await writeFile(destination, await this.file(jobId, kind));
    return destination;
  }
}

export default Client;
