import 'dotenv/config';
import { z } from 'zod';

const envSchema = z.object({
  DISCORD_TOKEN: z.string().min(1).optional(),
  BOT_TOKEN: z.string().min(1).optional(),
  DISCORD_CLIENT_ID: z.string().min(1).optional(),
  CLIENT_ID: z.string().min(1).optional(),
  DISCORD_GUILD_ID: z.string().optional(),
  DATA_FILE: z.string().default('./data/config.json'),
  LOG_LEVEL: z.enum(['debug', 'info', 'warn', 'error']).default('info'),
});

const parsed = envSchema.parse({
  DISCORD_TOKEN: process.env.DISCORD_TOKEN,
  BOT_TOKEN: process.env.BOT_TOKEN,
  DISCORD_CLIENT_ID: process.env.DISCORD_CLIENT_ID,
  CLIENT_ID: process.env.CLIENT_ID,
  DISCORD_GUILD_ID: process.env.DISCORD_GUILD_ID,
  DATA_FILE: process.env.DATA_FILE,
  LOG_LEVEL: process.env.LOG_LEVEL,
});

const token = parsed.DISCORD_TOKEN ?? parsed.BOT_TOKEN;
if (!token) throw new Error('Missing DISCORD_TOKEN (or Wispbyte-compatible BOT_TOKEN).');

export const env = {
  ...parsed,
  DISCORD_TOKEN: token,
  DISCORD_CLIENT_ID: parsed.DISCORD_CLIENT_ID ?? parsed.CLIENT_ID,
};
