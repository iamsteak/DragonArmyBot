import {
  ChatInputCommandInteraction,
  GuildMember,
  PermissionsBitField,
  User,
} from 'discord.js';

export function isGuildMember(value: GuildMember | User): value is GuildMember {
  return value instanceof GuildMember;
}

export async function requireGuild(interaction: ChatInputCommandInteraction): Promise<boolean> {
  if (!interaction.guild) {
    await interaction.reply({ content: 'This command can only be used inside a server.', ephemeral: true });
    return false;
  }
  return true;
}

export async function requirePermission(
  interaction: ChatInputCommandInteraction,
  permission: bigint,
): Promise<boolean> {
  if (!interaction.guild || !interaction.member) return false;
  const rawPermissions = 'permissions' in interaction.member ? interaction.member.permissions : undefined;
  const permissions = typeof rawPermissions === 'string'
    ? new PermissionsBitField(BigInt(rawPermissions))
    : rawPermissions
      ? new PermissionsBitField(rawPermissions)
      : undefined;
  if (!permissions || !permissions.has(permission)) {
    await interaction.reply({ content: 'You do not have permission to use this command.', ephemeral: true });
    return false;
  }
  return true;
}

export function canModerate(actor: GuildMember, target: GuildMember): boolean {
  return actor.id !== target.id && target.id !== actor.guild.ownerId && actor.roles.highest.comparePositionTo(target.roles.highest) > 0;
}

export function formatDuration(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.floor(hours / 24)}d`;
}

export function parseDuration(input: string): number | null {
  const match = /^(\d+)(s|m|h|d|w)$/i.exec(input.trim());
  if (!match) return null;
  const amount = Number(match[1]);
  const unit = match[2]?.toLowerCase();
  if (!unit) return null;
  const multipliers: Record<string, number> = { s: 1000, m: 60_000, h: 3_600_000, d: 86_400_000, w: 604_800_000 };
  const multiplier = multipliers[unit];
  if (!multiplier) return null;
  const result = amount * multiplier;
  return result > 0 && result <= 28 * 86_400_000 ? result : null;
}

export function hasManageGuild(interaction: ChatInputCommandInteraction): boolean {
  if (!interaction.member) return false;
  const rawPermissions = 'permissions' in interaction.member ? interaction.member.permissions : undefined;
  const permissions = typeof rawPermissions === 'string'
    ? new PermissionsBitField(BigInt(rawPermissions))
    : rawPermissions
      ? new PermissionsBitField(rawPermissions)
      : undefined;
  return permissions?.has('ManageGuild') ?? false;
}
