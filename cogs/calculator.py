import discord
from discord.ext import commands
import re
from math import floor
import asyncio

class Calculator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Precise trade rates from image_7b9460.png [Fish, Apple, Ruby] costs in logs
        self.rates = {
            1: [1, 1, 450], 2: [1, 1, 450], 3: [1, 3, 450],
            4: [2, 4, 450], 5: [2, 4, 450], 6: [3, 15, 675],
            7: [3, 15, 675], 8: [3, 8, 675], 9: [2, 12, 850],
            10: [3, 12, 500], 11: [3, 8, 500], 12: [3, 8, 350],
            13: [3, 8, 350], 14: [3, 8, 350], 15: [3, 8, 350],
            "TOP": [2, 4, 250]
        }

    def get_growth_factor(self, area):
        """Calculates total value multiplier based on guide milestones."""
        m = 1.0
        if area >= 3: m *= 2.0      # Area 3 Fish milestone (x2)
        if area >= 5: m *= 3.75     # Area 5 Apple milestone (x3.75)
        if area >= 8: m *= 1.5      # Area 8 Apple milestone (x1.5)
        if area >= 9: m *= 1.5      # Area 9 Fish milestone (x1.5)
        return m

    def dismantle_all(self, inv):
        """Standard EPIC RPG dismantle math."""
        total_epic = (inv.get('epic log', 0) + (inv.get('super log', 0) * 8) + 
                     (inv.get('mega log', 0) * 64) + (inv.get('hyper log', 0) * 512) + 
                     (inv.get('ultra log', 0) * 4096))
        wood = inv.get('wooden log', 0) + (total_epic * 20)
        
        total_golden = inv.get('golden fish', 0) + (inv.get('epic fish', 0) * 80)
        fish = inv.get('normie fish', 0) + (total_golden * 12)
        
        apple = inv.get('apple', 0) + (inv.get('banana', 0) * 12)
        return wood, fish, apple

    async def process_calculator_logic(self, message):
        content = message.content.lower()
        match = re.search(r"rpg\s+i\s+(\d+)", content)
        if not match: return
        
        current_area = int(match.group(1))
        inv = await self.scrape_inventory(message) # Uses your existing scraper
        if not inv: return

        w, f, a = self.dismantle_all(inv)
        r = inv.get('ruby', 0)

        # 1. Convert current inventory to Area 1 "Base Log" value
        curr_rates = self.rates.get(current_area, self.rates[15])
        curr_mult = self.get_growth_factor(current_area)
        
        total_logs_now = w + (f * curr_rates[0]) + (a * curr_rates[1]) + (r * curr_rates[2])
        base_logs_a1 = total_logs_now / curr_mult

        # 2. Project to target areas to match Army Helper and RPG Guide bots
        def get_target(target_area):
            t_mult = self.get_growth_factor(target_area)
            t_rates = self.rates.get(target_area, self.rates[15])
            logs = base_logs_a1 * t_mult
            return floor(logs), floor(logs / t_rates[1]), floor(logs / t_rates[2])

        # Match results from image_7b8cb7.png
        a10_logs, _, _ = get_target(10)
        _, a11_apples, _ = get_target(11)
        _, _, a12_rubies = get_target(12)

        # 3. UI Formatting
        embed = discord.Embed(
            title=f"{message.author.name} — material calculator (current area {current_area})",
            description="Assuming you dismantle all the materials and follow the trade rate",
            color=0x2f3136
        )
        
        # Using [A10+] formatting to match Army Helper
        res = (
            f"🪵 **[A10+]** : {a10_logs:,}\n"
            f"🍎 **[A11+]** : {a11_apples:,}\n"
            f"💎 **[A12+]** : {a12_rubies:,}"
        )
        embed.add_field(name="Materials", value=res, inline=False)
        
        await message.channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Calculator(bot))