import discord
from discord.ext import commands
import re
import time

class Trades(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_sessions = {}

        self.trade_ids = {
            "fish": "a", "apple": "c", "ruby": "e",
            "log_to_fish": "b", "log_to_apple": "d", "log_to_ruby": "f",
        }
        
        self.id_to_material = {
            "a": "fish", "b": "log", "c": "apple", 
            "d": "log", "e": "ruby", "f": "log"
        }

        self.base_guides = {
            3: {"dismantle": ["epic log", "super log", "mega log", "hyper log", "ultra log", "banana"], "trades": ["apple to log", "log to fish"]},
            5: {"dismantle": ["golden fish", "epic fish", "epic log", "super log", "mega log", "hyper log", "ultra log"], "trades": ["ruby to log", "fish to log", "log to apple"]},
            7: {"dismantle": ["banana"], "trades": ["apple to log"]},
            8: {"dismantle": ["golden fish", "epic fish", "epic log", "super log", "mega log", "hyper log", "ultra log"], "trades": ["ruby to log", "fish to log", "log to apple"]},
            9: {"dismantle": ["banana"], "trades": ["ruby to log", "apple to log", "log to fish"]},
            10: {"dismantle": ["banana"], "trades": ["apple to log"]},
            11: {"dismantle": [], "trades": ["ruby to log"]},
            15: {"dismantle": [], "trades": []}
        }
        self.area_map = {1: 3, 2: 3, 4: 5, 6: 7, 12: 11, 13: 11, 14: 11}

    async def process_trade_logic(self, message):
        content = message.content.lower()
        
        # 1. Start Session (User Trigger)
        if content.startswith("rpg p tr"):
            self.active_sessions[message.author.id] = {
                "name": str(message.author.name).lower(),
                "last_active": time.time(),
                "todo_list": [],
                "trade_list": [],
                "area": None,
                "current_target": None
            }
            return

        # 2. Epic RPG Bot Response Handler
        if message.author.id == 555955826880413696:
            target_session = None
            target_uid = None

            # Find session by embed author name
            if message.embeds:
                auth = str(message.embeds[0].author.name).lower() if message.embeds[0].author else ""
                for uid, sess in self.active_sessions.items():
                    if sess["name"] in auth:
                        target_session = sess
                        target_uid = uid
                        break
            
            # If it's text (dismantle), find the most recently active session
            if not target_session:
                for uid, sess in self.active_sessions.items():
                    target_session = sess
                    target_uid = uid
                    break

            # SAFETY: If no active session found for this message, stop
            if not target_session or not target_uid:
                return

            # --- PROCESS RESPONSES ---
            
            # Dismantle Success
            if "successfully crafted" in content:
                await self.send_next_command(message.channel, target_uid)

            # Embed Handlers
            if message.embeds:
                embed = message.embeds[0]
                desc = str(embed.description).lower() if embed.description else ""
                auth_name = str(embed.author.name).lower() if embed.author else ""

                # A. Trade Result Verification
                if "our trade is done then" in desc:
                    field_text = " ".join([f.value for f in embed.fields]).lower()
                    target_mat = target_session.get("current_target")
                    
                    # If target material didn't get traded, re-add it to start of list
                    if target_mat and target_mat not in field_text:
                        trade_id = self.trade_ids.get(target_mat) or target_mat
                        target_session["trade_list"].insert(0, trade_id)
                    
                    target_session["current_target"] = None
                    await self.send_next_command(message.channel, target_uid)

                # B. Inventory Refresh (Adds items to list based on what's there)
                elif "inventory" in auth_name:
                    await self.refresh_tasks(target_uid, embed)
                    await self.send_next_command(message.channel, target_uid)

                # C. Profile Area Detection
                elif "profile" in auth_name:
                    all_text = " ".join([f.value for f in embed.fields])
                    max_area = self.extract_max_area(all_text)
                    if max_area:
                        target_session["area"] = self.area_map.get(max_area, max_area)
                        await message.channel.send(f"✅ **Area {max_area} detected.** Please run `rpg i`!")

    async def refresh_tasks(self, uid, embed):
        session = self.active_sessions[uid]
        guide = self.base_guides.get(session.get("area", 15))
        inv_text = " ".join([f.value for f in embed.fields]).lower()

        # Update Dismantle List: only items that actually have quantity > 0
        session["todo_list"] = [i for i in reversed(guide["dismantle"]) 
                               if re.search(rf"\*\*{re.escape(i)}\*\*:\s*([1-9][\d,]*)", inv_text)]
        
        # Update Trade List: only materials that actually exist in inv
        trades = []
        for t_str in guide["trades"]:
            parts = t_str.split(" to ")
            source = "wooden log" if parts[0] == "log" else ("normie fish" if parts[0] == "fish" else parts[0])
            if re.search(rf"\*\*{re.escape(source)}\*\*:\s*([1-9][\d,]*)", inv_text):
                key = f"log_to_{parts[1]}" if parts[0] == "log" else parts[0]
                trades.append(self.trade_ids.get(key))
        session["trade_list"] = trades

    async def send_next_command(self, channel, uid):
        session = self.active_sessions.get(uid)
        if not session or session["area"] is None:
            return

        # 1. Try Dismantle
        if session["todo_list"]:
            item = session["todo_list"].pop(0)
            return await channel.send(f"```rpg dismantle {item} all```")

        # 2. Try Trade
        if session["trade_list"]:
            tid = session["trade_list"].pop(0)
            session["current_target"] = self.id_to_material.get(tid, tid)
            return await channel.send(f"```rpg trade {tid} all```")

        # 3. All items cleared
        await channel.send(f"✅ **Optimized!** All tasks for Area {session['area']} finished.")
        del self.active_sessions[uid]

    def extract_max_area(self, text):
        match = re.search(r"\(Max:\s*(\d+)\)", text, re.IGNORECASE)
        return int(match.group(1)) if match else None

async def setup(bot):
    await bot.add_cog(Trades(bot))