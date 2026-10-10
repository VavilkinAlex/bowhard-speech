#!/usr/bin/env node
/**
 * Командная строка: bowhard-speech transcribe <файл> | say "<текст>" | link <url> | job <id> | prices
 */
import { Client, BowhardError } from '../index.js';

const [, , command, ...rest] = process.argv;

function flag(name, fallback = null) {
  const index = rest.indexOf(name);
  return index >= 0 ? rest[index + 1] : fallback;
}

function positional() {
  return rest.filter((value, index) => !value.startsWith('--') && !(index > 0 && rest[index - 1].startsWith('--')));
}

const client = new Client({ baseUrl: flag('--base-url') || undefined });

try {
  if (command === 'transcribe') {
    const file = positional()[0];
    if (!file) throw new Error('нужен файл: bowhard-speech transcribe <файл>');
    const job = await client.transcribe(file);
    process.stderr.write(`задача ${job.id} принята (${job.status})\n`);
    await client.wait(job.id, { onProgress: (j) => process.stderr.write(`  ${j.status} · ${j.stage}\n`) });
    const out = flag('--out', '-o');
    const text = await client.text(job.id);
    if (out) {
      await client.save(job.id, 'txt', out);
      console.log(out);
    } else {
      console.log(text);
    }
    const srt = flag('--srt');
    if (srt) await client.save(job.id, 'srt', srt);
  } else if (command === 'link') {
    const url = positional()[0];
    if (!url) throw new Error('нужна ссылка: bowhard-speech link <url>');
    const job = await client.transcribeLink(url);
    await client.wait(job.id);
    console.log(await client.text(job.id));
  } else if (command === 'say') {
    const text = positional()[0];
    if (!text) throw new Error('нужен текст: bowhard-speech say "<текст>"');
    const job = await client.synthesize(text, { voice: flag('--voice', 'alena'), speed: Number(flag('--speed', 1)) });
    await client.wait(job.id);
    console.log(await client.save(job.id, 'mp3', flag('--out', '-o') || 'speech.mp3'));
  } else if (command === 'job') {
    const id = positional()[0];
    console.log(JSON.stringify(await client.job(id), null, 2));
  } else if (command === 'prices') {
    console.log(JSON.stringify(await client.prices(), null, 2));
  } else {
    console.log('Команды: transcribe <файл> [-o текст] [--srt файл] | link <url> | say "<текст>" [-o mp3] [--voice] [--speed] | job <id> | prices');
    process.exit(command ? 1 : 0);
  }
} catch (error) {
  if (error instanceof BowhardError) {
    process.stderr.write(`ошибка: ${error.message}\n`);
    if (error.status === 402) process.stderr.write(`нужна оплата: ${JSON.stringify(error.payload)}\n`);
    process.exit(1);
  }
  process.stderr.write(`ошибка: ${error.message}\n`);
  process.exit(1);
}
