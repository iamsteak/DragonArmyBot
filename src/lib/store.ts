import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

export type GuildConfig = {
  logChannelId?: string;
  welcomeChannelId?: string;
  welcomeMessage?: string;
  autoModEnabled: boolean;
  blockedWords: string[];
  customCommands: Record<string, string>;
  reactionRoles: Record<string, string>;
};

type StoreData = { guilds: Record<string, GuildConfig> };

const defaults = (): GuildConfig => ({
  autoModEnabled: false,
  blockedWords: [],
  customCommands: {},
  reactionRoles: {},
});

export class GuildStore {
  private data: StoreData = { guilds: {} };
  private loaded = false;

  constructor(private readonly filePath: string) {}

  async load(): Promise<void> {
    if (this.loaded) return;
    await mkdir(path.dirname(this.filePath), { recursive: true });
    try {
      const raw = await readFile(this.filePath, 'utf8');
      this.data = JSON.parse(raw) as StoreData;
    } catch (error: unknown) {
      const code = error && typeof error === 'object' && 'code' in error ? error.code : undefined;
      if (code !== 'ENOENT') throw error;
      await this.persist();
    }
    this.loaded = true;
  }

  get(guildId: string): GuildConfig {
    const current = this.data.guilds[guildId];
    if (current) return current;
    const created = defaults();
    this.data.guilds[guildId] = created;
    return created;
  }

  async update(guildId: string, patch: Partial<GuildConfig>): Promise<GuildConfig> {
    await this.load();
    const next = { ...this.get(guildId), ...patch };
    this.data.guilds[guildId] = next;
    await this.persist();
    return next;
  }

  async reset(guildId: string): Promise<void> {
    await this.load();
    delete this.data.guilds[guildId];
    await this.persist();
  }

  async persist(): Promise<void> {
    await mkdir(path.dirname(this.filePath), { recursive: true });
    await writeFile(this.filePath, `${JSON.stringify(this.data, null, 2)}\n`, 'utf8');
  }
}
