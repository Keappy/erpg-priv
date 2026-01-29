import discord
from discord.ext import commands

class ConfigView(discord.ui.View):
    def __init__(self, bot, squad_data):
        super().__init__(timeout=60)
        self.bot = bot
        self.data = squad_data

    @discord.ui.select(
        placeholder="Choose an event to configure...",
        options=[
            discord.SelectOption(label="Arena", value="arena", emoji="<:epicrpgarena:697563611698298922>"),
            discord.SelectOption(label="Coin Rain", value="catch", emoji="<:coin:557642215284015124>"),
            discord.SelectOption(label="Lure", value="lure", emoji="<:normiefish:697940429999439872>"),
            discord.SelectOption(label="Rare Hunt", value="pickaxe", emoji="<:shinypickaxe:1357664482884845628>"),
            discord.SelectOption(label="Legendary Boss", value="boss", emoji="<:memedragon:547517937314037789>"),
            discord.SelectOption(label="Lootbox", value="summon", emoji="<:EdgyLootbox:578728161550925834>"),
            discord.SelectOption(label="Epic Tree", value="cut", emoji="<:woodenlog:770880739926999070>"),
            discord.SelectOption(label="Pack", value="pack", emoji="<:box:1100581772808429700>"),
            discord.SelectOption(label="Ohmmm", value="ohmmm", emoji="<:energy:1084593332312887396>"),
            discord.SelectOption(label="Lucky Rewards", value="lucky rewards", emoji="<:idlons:1086449232967372910>"),
            discord.SelectOption(label="Miniboss", value="miniboss", emoji="🗡️"),
        ]
    )
    async def select_callback(self, interaction, select):
        event_key = select.values[0]
        await interaction.response.send_message(
            f"Please send the new message for the **{event_key}** event (or type `abort` to cancel):",
            ephemeral=True
        )

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            msg = await self.bot.wait_for("message", check=check, timeout=30.0)
            if msg.content.lower() == "abort":
                return await msg.reply("❌ Cancelled.")
            
            # Update Data
            self.data["server_configs"]["global"]["event_configs"][event_key]["msg"] = msg.content
            self.bot.save_data()
            await msg.reply(f"✅ Updated {event_key} message to: `{msg.content}`")
        except Exception as e:
            await interaction.followup.send("⚠️ Timed out or error occurred.", ephemeral=True)

class GlobalSettings(commands.Cog):
    def __init__(self, bot, squad_data, save_func):
        self.bot = bot
        self.data = squad_data
        self.save_data = save_func

    @commands.command(name="config")
    @commands.has_permissions(administrator=True)
    async def server_settings(self, ctx):
        """Opens the global event configuration menu."""
        embed = discord.Embed(
            title="⚙️ Global Event Settings",
            description="Manage your squadron event pings and messages below.",
            color=discord.Color.green()
        )
        
        configs = self.data["server_configs"]["global"].get("event_configs", {})
        for event, details in configs.items():
            role_mention = f"<@&{details['role']}>"
            embed.add_field(
                name=event.upper(), 
                value=f"**Role:** {role_mention}\n**Message:** {details['msg']}", 
                inline=True
            )

        await ctx.send(embed=embed, view=ConfigView(self.bot, self.data))

async def setup(bot):
    await bot.add_cog(GlobalSettings(bot, bot.squad_data, bot.save_data))