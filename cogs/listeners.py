import discord
from discord.ext import commands

class GlobalListeners(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        # 1. Ignore own bot messages to prevent loops
        if message.author == self.bot.user:
            return

        # 2. Forward to Event Tracker (cogs/events.py)
        event_cog = self.bot.get_cog("EventTracker")
        if event_cog:
            await event_cog.check_rpg_events(message)

        # Inside GlobalListeners on_message
        trade_cog = self.bot.get_cog("Trades") # 'Trades' is the class name in check_trades.py
        if trade_cog:
            await trade_cog.process_trade_logic(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        # Buttons on Epic RPG messages update the message rather than sending a new one
        event_cog = self.bot.get_cog("EventTracker")
        if event_cog:
            await event_cog.check_rpg_events(after)
            
        trade_cog = self.bot.get_cog("Trades")
        if trade_cog:
            await trade_cog.process_trade_logic(after)

async def setup(bot):
    await bot.add_cog(GlobalListeners(bot))