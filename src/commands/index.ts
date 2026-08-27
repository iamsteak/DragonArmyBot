import {
  ChatInputCommandInteraction,
  EmbedBuilder,
  PermissionFlagsBits,
  SlashCommandBuilder,
  TextChannel,
} from 'discord.js';
import { GuildStore } from '../lib/store.js';
import { canModerate, parseDuration, requireGuild, requirePermission } from '../lib/helpers.js';

export type Command = {
  data: { name: string; toJSON: () => unknown };
  execute: (interaction: ChatInputCommandInteraction, store: GuildStore) => Promise<void>;
};

const command = (data: Command['data'], execute: Command['execute']): Command => ({ data, execute });

const help = command(
  new SlashCommandBuilder().setName('help').setDescription('Show the bot command guide'),
  async (interaction) => {
    const embed = new EmbedBuilder()
      .setColor(0x5865f2)
      .setTitle('Dragon Army Bot')
      .setDescription('Moderation, automod, logging, onboarding, and utility tools for your server.')
      .addFields(
        { name: 'Moderation', value: '`/warn`, `/timeout`, `/kick`, `/ban`, `/purge`' },
        { name: 'Server setup', value: '`/config`, `/automod`, `/blockword`, `/custom-command`' },
        { name: 'Utilities', value: '`/ping`, `/server`, `/userinfo`' },
      )
      .setFooter({ text: 'Use Discord’s command autocomplete to explore options.' });
    await interaction.reply({ embeds: [embed] });
  },
);

const ping = command(
  new SlashCommandBuilder().setName('ping').setDescription('Check the bot latency'),
  async (interaction) => {
    await interaction.reply(`Pong. Gateway latency: ${interaction.client.ws.ping}ms.`);
  },
);

const server = command(
  new SlashCommandBuilder().setName('server').setDescription('Show server information'),
  async (interaction) => {
    if (!(await requireGuild(interaction))) return;
    const guild = interaction.guild!;
    const embed = new EmbedBuilder()
      .setColor(0x2b2d31)
      .setTitle(guild.name)
      .setThumbnail(guild.iconURL({ size: 256 }) ?? '')
      .addFields(
        { name: 'Members', value: `${guild.memberCount}`, inline: true },
        { name: 'Channels', value: `${guild.channels.cache.size}`, inline: true },
        { name: 'Created', value: `<t:${Math.floor(guild.createdTimestamp / 1000)}:D>`, inline: true },
      );
    await interaction.reply({ embeds: [embed] });
  },
);

const userinfo = command(
  new SlashCommandBuilder()
    .setName('userinfo')
    .setDescription('Show information about a member')
    .addUserOption((option) => option.setName('user').setDescription('Member to inspect').setRequired(false)),
  async (interaction) => {
    if (!(await requireGuild(interaction))) return;
    const user = interaction.options.getUser('user') ?? interaction.user;
    const member = await interaction.guild!.members.fetch(user.id);
    const embed = new EmbedBuilder()
      .setColor(0x5865f2)
      .setTitle(user.tag)
      .setThumbnail(user.displayAvatarURL({ size: 256 }))
      .addFields(
        { name: 'Account', value: `<@${user.id}>`, inline: true },
        { name: 'Joined server', value: member.joinedTimestamp ? `<t:${Math.floor(member.joinedTimestamp / 1000)}:R>` : 'Unknown', inline: true },
        { name: 'Roles', value: member.roles.cache.filter((role) => role.id !== interaction.guild!.id).map((role) => role.toString()).join(', ') || 'None' },
      );
    await interaction.reply({ embeds: [embed] });
  },
);

const warn = command(
  new SlashCommandBuilder()
    .setName('warn')
    .setDescription('Warn a member and record the action in the audit channel')
    .setDefaultMemberPermissions(PermissionFlagsBits.ModerateMembers)
    .addUserOption((option) => option.setName('user').setDescription('Member to warn').setRequired(true))
    .addStringOption((option) => option.setName('reason').setDescription('Reason for the warning').setRequired(true)),
  async (interaction, store) => {
    if (!(await requireGuild(interaction)) || !(await requirePermission(interaction, PermissionFlagsBits.ModerateMembers))) return;
    const user = interaction.options.getUser('user', true);
    const reason = interaction.options.getString('reason', true);
    const config = store.get(interaction.guild!.id);
    await interaction.reply({ content: `Warned ${user} for: ${reason}` });
    if (config.logChannelId) {
      const channel = await interaction.guild!.channels.fetch(config.logChannelId).catch(() => null);
      if (channel?.isTextBased()) await channel.send(`⚠️ **Warning** — ${user.tag} was warned by ${interaction.user.tag}. Reason: ${reason}`);
    }
  },
);

const timeout = command(
  new SlashCommandBuilder()
    .setName('timeout')
    .setDescription('Temporarily timeout a member')
    .setDefaultMemberPermissions(PermissionFlagsBits.ModerateMembers)
    .addUserOption((option) => option.setName('user').setDescription('Member to timeout').setRequired(true))
    .addStringOption((option) => option.setName('duration').setDescription('For example: 10m, 2h, or 1d').setRequired(true))
    .addStringOption((option) => option.setName('reason').setDescription('Reason').setRequired(false)),
  async (interaction) => {
    if (!(await requireGuild(interaction)) || !(await requirePermission(interaction, PermissionFlagsBits.ModerateMembers))) return;
    const target = await interaction.guild!.members.fetch(interaction.options.getUser('user', true).id).catch(() => null);
    const duration = parseDuration(interaction.options.getString('duration', true));
    const reason = interaction.options.getString('reason') ?? 'No reason provided';
    if (!target || !duration) {
      await interaction.reply({ content: 'I could not find that member or the duration is invalid. Use a value like `10m` or `2h` (maximum 28 days).', ephemeral: true });
      return;
    }
    const actor = await interaction.guild!.members.fetch(interaction.user.id);
    if (!canModerate(actor, target)) {
      await interaction.reply({ content: 'That member has an equal or higher role than you, so I will not moderate them.', ephemeral: true });
      return;
    }
    await target.timeout(duration, reason);
    await interaction.reply(`Timed out ${target} for ${interaction.options.getString('duration', true)}. Reason: ${reason}`);
  },
);

const kick = command(
  new SlashCommandBuilder()
    .setName('kick')
    .setDescription('Kick a member')
    .setDefaultMemberPermissions(PermissionFlagsBits.KickMembers)
    .addUserOption((option) => option.setName('user').setDescription('Member to kick').setRequired(true))
    .addStringOption((option) => option.setName('reason').setDescription('Reason').setRequired(false)),
  async (interaction) => {
    if (!(await requireGuild(interaction)) || !(await requirePermission(interaction, PermissionFlagsBits.KickMembers))) return;
    const target = await interaction.guild!.members.fetch(interaction.options.getUser('user', true).id).catch(() => null);
    if (!target) {
      await interaction.reply({ content: 'That member is not in this server.', ephemeral: true });
      return;
    }
    const actor = await interaction.guild!.members.fetch(interaction.user.id);
    if (!canModerate(actor, target)) {
      await interaction.reply({ content: 'That member has an equal or higher role than you.', ephemeral: true });
      return;
    }
    const reason = interaction.options.getString('reason') ?? 'No reason provided';
    await target.kick(reason);
    await interaction.reply(`Kicked **${target.user.tag}**. Reason: ${reason}`);
  },
);

const ban = command(
  new SlashCommandBuilder()
    .setName('ban')
    .setDescription('Ban a member')
    .setDefaultMemberPermissions(PermissionFlagsBits.BanMembers)
    .addUserOption((option) => option.setName('user').setDescription('Member to ban').setRequired(true))
    .addStringOption((option) => option.setName('reason').setDescription('Reason').setRequired(false)),
  async (interaction) => {
    if (!(await requireGuild(interaction)) || !(await requirePermission(interaction, PermissionFlagsBits.BanMembers))) return;
    const target = await interaction.guild!.members.fetch(interaction.options.getUser('user', true).id).catch(() => null);
    if (!target) {
      await interaction.reply({ content: 'That member is not in this server.', ephemeral: true });
      return;
    }
    const actor = await interaction.guild!.members.fetch(interaction.user.id);
    if (!canModerate(actor, target)) {
      await interaction.reply({ content: 'That member has an equal or higher role than you.', ephemeral: true });
      return;
    }
    const reason = interaction.options.getString('reason') ?? 'No reason provided';
    await target.ban({ reason });
    await interaction.reply(`Banned **${target.user.tag}**. Reason: ${reason}`);
  },
);

const purge = command(
  new SlashCommandBuilder()
    .setName('purge')
    .setDescription('Delete recent messages from this channel')
    .setDefaultMemberPermissions(PermissionFlagsBits.ManageMessages)
    .addIntegerOption((option) => option.setName('amount').setDescription('Number of messages, from 1 to 100').setMinValue(1).setMaxValue(100).setRequired(true)),
  async (interaction) => {
    if (!(await requireGuild(interaction)) || !(await requirePermission(interaction, PermissionFlagsBits.ManageMessages))) return;
    if (!interaction.channel?.isTextBased() || !('bulkDelete' in interaction.channel)) {
      await interaction.reply({ content: 'This command only works in a standard text channel.', ephemeral: true });
      return;
    }
    await interaction.deferReply({ ephemeral: true });
    const amount = interaction.options.getInteger('amount', true);
    const deleted = await (interaction.channel as TextChannel).bulkDelete(amount, true);
    await interaction.editReply(`Deleted ${deleted.size} message(s).`);
  },
);

const config = command(
  new SlashCommandBuilder()
    .setName('config')
    .setDescription('Configure the bot for this server')
    .setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addSubcommand((sub) => sub.setName('view').setDescription('View current configuration'))
    .addSubcommand((sub) => sub.setName('log-channel').setDescription('Set the moderation log channel').addChannelOption((option) => option.setName('channel').setDescription('Text channel').setRequired(true)))
    .addSubcommand((sub) => sub.setName('welcome').setDescription('Set the welcome channel and message').addChannelOption((option) => option.setName('channel').setDescription('Text channel').setRequired(true)).addStringOption((option) => option.setName('message').setDescription('Use {user} and {server} placeholders').setRequired(true)))
    .addSubcommand((sub) => sub.setName('reset').setDescription('Reset this server configuration')),
  async (interaction, store) => {
    if (!(await requireGuild(interaction)) || !(await requirePermission(interaction, PermissionFlagsBits.ManageGuild))) return;
    const subcommand = interaction.options.getSubcommand();
    const guildId = interaction.guild!.id;
    if (subcommand === 'view') {
      const current = store.get(guildId);
      await interaction.reply({ content: `Prefix: \`${current.prefix}\`\nLog channel: ${current.logChannelId ? `<#${current.logChannelId}>` : 'not set'}\nWelcome channel: ${current.welcomeChannelId ? `<#${current.welcomeChannelId}>` : 'not set'}\nAutomod: ${current.autoModEnabled ? 'enabled' : 'disabled'}\nBlocked words: ${current.blockedWords.length}`, ephemeral: true });
    } else if (subcommand === 'log-channel') {
      const channel = interaction.options.getChannel('channel', true);
      await store.update(guildId, { logChannelId: channel.id });
      await interaction.reply(`Moderation logs will be sent to ${channel}.`);
    } else if (subcommand === 'welcome') {
      const channel = interaction.options.getChannel('channel', true);
      const message = interaction.options.getString('message', true);
      await store.update(guildId, { welcomeChannelId: channel.id, welcomeMessage: message });
      await interaction.reply(`Welcome messages will be sent to ${channel}.`);
    } else {
      await store.reset(guildId);
      await interaction.reply('Server configuration reset.');
    }
  },
);

const automod = command(
  new SlashCommandBuilder()
    .setName('automod')
    .setDescription('Enable or disable blocked-word automod')
    .setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addBooleanOption((option) => option.setName('enabled').setDescription('Whether automod should be enabled').setRequired(true)),
  async (interaction, store) => {
    if (!(await requireGuild(interaction)) || !(await requirePermission(interaction, PermissionFlagsBits.ManageGuild))) return;
    const enabled = interaction.options.getBoolean('enabled', true);
    await store.update(interaction.guild!.id, { autoModEnabled: enabled });
    await interaction.reply(`Blocked-word automod is now **${enabled ? 'enabled' : 'disabled'}**.`);
  },
);

const blockword = command(
  new SlashCommandBuilder()
    .setName('blockword')
    .setDescription('Add or remove a blocked word')
    .setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addSubcommand((sub) => sub.setName('add').setDescription('Add a blocked word').addStringOption((option) => option.setName('word').setDescription('Word or phrase').setRequired(true)))
    .addSubcommand((sub) => sub.setName('remove').setDescription('Remove a blocked word').addStringOption((option) => option.setName('word').setDescription('Word or phrase').setRequired(true)))
    .addSubcommand((sub) => sub.setName('list').setDescription('List blocked words')),
  async (interaction, store) => {
    if (!(await requireGuild(interaction)) || !(await requirePermission(interaction, PermissionFlagsBits.ManageGuild))) return;
    const config = store.get(interaction.guild!.id);
    const subcommand = interaction.options.getSubcommand();
    if (subcommand === 'list') {
      await interaction.reply({ content: config.blockedWords.length ? config.blockedWords.map((word) => `• ${word}`).join('\n') : 'No blocked words configured.', ephemeral: true });
      return;
    }
    const word = interaction.options.getString('word', true).trim().toLowerCase();
    const words = new Set(config.blockedWords);
    if (subcommand === 'add') words.add(word); else words.delete(word);
    await store.update(interaction.guild!.id, { blockedWords: [...words] });
    await interaction.reply(`Blocked word list updated. Current count: ${words.size}.`);
  },
);

const customCommand = command(
  new SlashCommandBuilder()
    .setName('custom-command')
    .setDescription('Create, remove, or list simple server custom commands')
    .setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addSubcommand((sub) => sub.setName('set').setDescription('Set a custom command response').addStringOption((option) => option.setName('name').setDescription('Command name').setRequired(true)).addStringOption((option) => option.setName('response').setDescription('Response text').setRequired(true)))
    .addSubcommand((sub) => sub.setName('remove').setDescription('Remove a custom command').addStringOption((option) => option.setName('name').setDescription('Command name').setRequired(true)))
    .addSubcommand((sub) => sub.setName('list').setDescription('List custom commands')),
  async (interaction, store) => {
    if (!(await requireGuild(interaction)) || !(await requirePermission(interaction, PermissionFlagsBits.ManageGuild))) return;
    const config = store.get(interaction.guild!.id);
    const subcommand = interaction.options.getSubcommand();
    if (subcommand === 'list') {
      const names = Object.keys(config.customCommands);
      await interaction.reply({ content: names.length ? names.map((name) => `• \`/${name}\``).join('\n') : 'No custom commands configured.', ephemeral: true });
      return;
    }
    const name = interaction.options.getString('name', true).toLowerCase().replace(/[^a-z0-9-]/g, '-').slice(0, 32);
    const customCommands = { ...config.customCommands };
    if (subcommand === 'set') customCommands[name] = interaction.options.getString('response', true).slice(0, 2000);
    else delete customCommands[name];
    await store.update(interaction.guild!.id, { customCommands });
    await interaction.reply(`Custom command \`/${name}\` ${subcommand === 'set' ? 'saved' : 'removed'}.`);
  },
);

const custom = command(
  new SlashCommandBuilder()
    .setName('custom')
    .setDescription('Run a configured custom server command')
    .addStringOption((option) => option.setName('name').setDescription('Custom command name').setRequired(true)),
  async (interaction, store) => {
    if (!(await requireGuild(interaction))) return;
    const name = interaction.options.getString('name', true).toLowerCase();
    const response = store.get(interaction.guild!.id).customCommands[name];
    if (!response) {
      await interaction.reply({ content: `No custom command named \`${name}\` exists.`, ephemeral: true });
      return;
    }
    await interaction.reply(response.replaceAll('{user}', interaction.user.toString()).replaceAll('{server}', interaction.guild!.name));
  },
);

export const commands: Command[] = [help, ping, server, userinfo, warn, timeout, kick, ban, purge, config, automod, blockword, customCommand, custom];
