import { mkdtemp, readFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { parseDuration } from './helpers.js';
import { GuildStore } from './store.js';

describe('parseDuration', () => {
  it('parses supported units', () => {
    expect(parseDuration('10m')).toBe(600_000);
    expect(parseDuration('2h')).toBe(7_200_000);
    expect(parseDuration('1d')).toBe(86_400_000);
  });

  it('rejects malformed and overlong durations', () => {
    expect(parseDuration('forever')).toBeNull();
    expect(parseDuration('29d')).toBeNull();
  });
});

describe('GuildStore', () => {
  it('creates defaults and persists updates', async () => {
    const directory = await mkdtemp(path.join(os.tmpdir(), 'dragon-army-'));
    const filePath = path.join(directory, 'config.json');
    const store = new GuildStore(filePath);
    await store.load();
    expect(store.get('guild-1').prefix).toBe('!');
    await store.update('guild-1', { autoModEnabled: true, blockedWords: ['spam'] });
    const raw = JSON.parse(await readFile(filePath, 'utf8')) as { guilds: Record<string, { autoModEnabled: boolean }> };
    expect(raw.guilds['guild-1']?.autoModEnabled).toBe(true);
  });
});
