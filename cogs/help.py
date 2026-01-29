import discord
from discord.ext import commands

class CustomHelp(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        prefix = self.context.clean_prefix
        embed = discord.Embed(
            title="🛠️ Squadron Bot Help Menu",
            description=f"Use `{prefix}help [command]` for more details.",
            color=discord.Color.blue()
        )

        management = (
            f"`{prefix}create [name]` - Create a new private squadron\n"
            f"`{prefix}rename [name]` - Rename current squadron\n"
            f"`{prefix}transferowner [@user]` - Give ownership\n"
            f"`{prefix}showlist` - View members and settings"
        )
        embed.add_field(name="👥 Squadron Management", value=management, inline=False)

        access = (
            f"`{prefix}allow [@user]` - Grant access\n"
            f"`{prefix}deny [@user]` - Remove access\n"
            f"`{prefix}hide` / `{prefix}unhide` - Toggle visibility"
        )
        embed.add_field(name="🔒 Access Control", value=access, inline=False)

        settings = (
            f"`{prefix}eventson` / `{prefix}eventsoff` - Toggle unhiding\n"
            f"`{prefix}squadonly [on/off]` - Force hidden\n"
            f"`{prefix}clearactive` - Reset stuck status"
        )
        embed.add_field(name="⚙️ Event Settings", value=settings, inline=False)

        embed.set_footer(text="Developed for ERPG Squadron Management")
        await self.get_destination().send(embed=embed)

    # This runs for ?help [command]
    async def send_command_help(self, command):
        embed = discord.Embed(
            title=f"Help: {command.name}",
            description=command.help or "No description provided.",
            color=discord.Color.blue()
        )
        
        # Show usage/aliases if they exist
        if command.usage:
            embed.add_field(name="Usage", value=f"`?{command.name} {command.usage}`")
        if command.aliases:
            embed.add_field(name="Aliases", value=", ".join(command.aliases))

        await self.get_destination().send(embed=embed)

    # This handles errors (e.g., ?help non_existent_command)
    async def send_error_message(self, error):
        await self.get_destination().send(f"❌ {error}")

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._original_help_command = bot.help_command
        bot.help_command = CustomHelp()
        bot.help_command.cog = self

    def cog_unload(self):
        # Restore the original help command when the cog is unloaded
        self.bot.help_command = self._original_help_command

async def setup(bot):
    await bot.add_cog(HelpCog(bot))