import discord
from discord.ext import commands
import re
import asyncio

class Trades(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_sessions = {}

        self.dismantle_returns = {
            "ultra log": ("hyper log", 10),
            "hyper log": ("mega log", 10),
            "mega log": ("super log", 10),
            "super log": ("epic log", 10),
            "epic log": ("wooden log", 25),
            "banana": ("apple", 15),
            "epic fish": ("golden fish", 100),
            "golden fish": ("normie fish", 15)
        }

        self.trade_ids = {
            "fish": "a", "apple": "c", "ruby": "e",
            "log_to_fish": "b", "log_to_apple": "d", "log_to_ruby": "f",
        }

        self.area_ratios = {
            1: {"log_to_fish": 1}, 2: {"log_to_fish": 1},
            3: {"log_to_fish": 1, "log_to_apple": 3},
            4: {"log_to_fish": 2, "log_to_apple": 4},
            5: {"log_to_fish": 2, "log_to_apple": 4, "log_to_ruby": 450},
            6: {"log_to_fish": 3, "log_to_apple": 15, "log_to_ruby": 675},
            7: {"log_to_fish": 3, "log_to_apple": 15, "log_to_ruby": 675},
            8: {"log_to_fish": 3, "log_to_apple": 8, "log_to_ruby": 675},
            9: {"log_to_fish": 2, "log_to_apple": 12, "log_to_ruby": 850},
            10: {"log_to_fish": 3, "log_to_apple": 12, "log_to_ruby": 500},
            11: {"log_to_ruby": 500}, 12: {"log_to_ruby": 500},
            13: {"log_to_ruby": 500}, 14: {"log_to_ruby": 500},
        }

        self.base_guides = {
            3: {"dismantle": ["epic log", "super log", "mega log", "hyper log", "ultra log", "banana"], "trades": ["apple to log", "log to fish"]},
            5: {"dismantle": ["golden fish", "epic fish", "epic log", "super log", "mega log", "hyper log", "ultra log"], "trades": ["ruby to log", "fish to log", "log to apple"]},
            7: {"dismantle": ["banana"], "trades": ["apple to log"]},
            8: {"dismantle": ["golden fish", "epic fish", "epic log", "super log", "mega log", "hyper log", "ultra log"], "trades": ["ruby to log", "fish to log", "log to apple"]},
            9: {"dismantle": ["epic log", "super log", "mega log", "hyper log", "ultra log", "banana"], "trades": ["ruby to log", "apple to log", "log to fish"]},
            10: {"dismantle": ["banana"], "trades": ["apple to log"]},
            11: {"dismantle": [], "trades": ["ruby to log"]},
            15: {"dismantle": [], "trades": []}
        }
        self.area_map = {1: 3, 2: 3, 4: 5, 6: 7, 12: 11, 13: 11, 14: 11, 15:11}

    def get_count(self, item_name, text):
        # Regex matches the bold name and captures the following number/commas
        match = re.search(rf"\*\*{re.escape(item_name)}\*\*:\s*([\d,]+)", text)
        if match:
            return int(match.group(1).replace(",", ""))
        return 0
    
    async def process_trade_logic(self, message):
        content = message.content.lower()
        uid = message.author.id

        # 1. Trigger Session
        if content.startswith("rpg p trd"):
            self.active_sessions[uid] = {
                "user_id": uid,
                "username": str(message.author.name).lower(),
                "todo_list": [], "trade_list": [],
                "logic_area": None, "real_area": 0,
                "status": "WAITING_FOR_PROFILE",
                "channel_id": message.channel.id,
                "last_action": None,
                "virtual_inv": {}
            }
            return

        # 2. Track USER Dismantle Commands
        if uid in self.active_sessions:
            if "rpg dismantle" in content:
                session = self.active_sessions[uid]
                session["last_action"] = "dismantle"
                
                # Logic: Find which item the user is dismantling
                # Matches: "rpg dismantle mega log all" or "rpg dismantle mega log 5"
                match = re.search(r"rpg dismantle\s+(.*?)\s+(all|\d+)", content)
                if match:
                    item_to_lose = match.group(1).strip()
                    # We treat 'all' as removing whatever we have in virtual_inv
                    session["virtual_inv"][item_to_lose] = 0 
                    print(f"DEBUG: User dismantling {item_to_lose}. Virtual count set to 0.")

        # 3. USER COMMANDS: Dismantle or Trade
        # We only track these if the user ALREADY has an active session
        if uid in self.active_sessions:
            if "rpg dismantle" in content:
                self.active_sessions[uid]["last_action"] = "dismantle"
            elif "rpg trade" in content:
                self.active_sessions[uid]["last_action"] = "trade"

        # 4. BOT RESPONSES: Processing RPG Bot's output
        if uid == 555955826880413696:
            print(f"--- DEBUG: Bot Message Received: {content} ---")
            # 1. Capture content from either text OR embed
            raw_content = message.content.lower()
            if not raw_content and message.embeds:
                raw_content = str(message.embeds[0].description).lower()
            
            # 2. Identify the user (If this fails, the whole block is skipped)
            target_uid = self.identify_user(message)
            if not target_uid or target_uid not in self.active_sessions: 
                return
            
            session = self.active_sessions[target_uid]
            print(f"--- DEBUG: Processing message for {session['username']} ---")
            
            # Step B: Double-check if we have an active session for this specific human
            if not target_uid or target_uid not in self.active_sessions:
                return

            session = self.active_sessions[target_uid]

            # Step C: Crucial Security Check - Is this the right channel?
            if session["channel_id"] != message.channel.id:
                return

            embed = message.embeds[0] if message.embeds else None
            # --- SESSION LOGIC START ---

            # Profile Detection (Locks Area)
            if session["status"] == "WAITING_FOR_PROFILE" and embed and "profile" in str(embed.author.name).lower():
                area = self.extract_area(embed)
                if area:
                    session["real_area"] = area
                    session["logic_area"] = self.area_map.get(area, area)
                    session["status"] = "ACTIVE"
                    await message.channel.send(f"✅ **Area {area}** locked for **{session['username']}**. Run `rpg i`.")
            
            print(f"DEBUG: RPG Bot said: '{content}'")
            # 3. Robust Dismantle Detection
            if "successfully crafted" in raw_content:
                print(f"--- DEBUG: Craft Success Found in: {raw_content} ---")
                
                # This regex skips everything between the number and the name inside backticks
                match = re.search(r"([\d,]+).*?`([^`]+)`", raw_content)
                
                if match:
                    got_amt = int(match.group(1).replace(",", ""))
                    item_name = match.group(2).strip().lower()
                    
                    # Update virtual inventory
                    session["virtual_inv"][item_name] = session["virtual_inv"].get(item_name, 0) + got_amt
                    print(f"--- DEBUG: Virtual Inv Updated: +{got_amt} {item_name} ---")

                # ALWAYS continue the chain even if regex fails to prevent a permanent stall
                session["last_action"] = None
                await asyncio.sleep(1.5)
                await self.refresh_tasks(target_uid)
                await self.send_next_command(message.channel, target_uid)

            # Trade Result Detector
            elif embed and any(x in str(embed.fields[0].name if embed.fields else "").lower() for x in ["traded items", "trade is done"]):
                field_val = embed.fields[0].value.lower()
                # Verify the human's name is actually in this specific trade embed
                if session["username"] in field_val:
                    gave_match = re.search(rf"{session['username']}.*?(log|fish|apple|ruby).*?x([\d,]+)", field_val)
                    npc_match = re.search(r"epic npc\*\*: .*?(log|fish|apple|ruby).*?x([\d,]+)", field_val)

                    if gave_match and npc_match:
                        gave_item = "wooden log" if "log" in gave_match.group(1) else "normie fish" if "fish" in gave_match.group(1) else gave_match.group(1)
                        got_item = "wooden log" if "log" in npc_match.group(1) else "normie fish" if "fish" in npc_match.group(1) else npc_match.group(1)
                        gave_amt = int(gave_match.group(2).replace(",", ""))
                        got_amt = int(npc_match.group(2).replace(",", ""))

                        await self.refresh_tasks(target_uid, None, virtual_update=(gave_item, gave_amt, got_item, got_amt))
                    
                    await self.send_next_command(message.channel, target_uid)

            # Inventory Detector
            elif embed and "inventory" in str(embed.author.name).lower():
                # Verify it's the right user's inventory
                if session["username"] in str(embed.author.name).lower():
                    await self.refresh_tasks(target_uid, embed)
                    await self.send_next_command(message.channel, target_uid)

    def check_trade_validity(self, text, session):
        area = session.get("real_area")
        # Split text to look specifically at what the PLAYER received (the NPC line)
        parts = text.lower().split("epic npc**:")
        if len(parts) < 2: return None
        npc_received = parts[1]

        # Mistake: You got fish in Area 4 (ID 'a' turns it back to logs)
        if area == 4 and ("fish" in npc_received or "697940429999439872" in npc_received):
            print("--- DEBUG: Mistake detected (Fish in A4). Suggesting trade 'a' ---")
            return "rpg trade a all"
            
        return None
    
    def identify_user(self, message):
        # 1. Check Embeds first (standard RPG behavior)
        if message.embeds:
            emb = message.embeds[0]
            icon_url = str(emb.author.icon_url) if emb.author else ""
            match = re.search(r"avatars/(\d+)/", icon_url)
            if match: return int(match.group(1))
            
            search_blob = f"{emb.author.name} {emb.description} ".lower()
            search_blob += " ".join([f"{f.name} {f.value}" for f in emb.fields]).lower()
            for uid, sess in self.active_sessions.items():
                if sess["username"] in search_blob: return uid

        # 2. FALLBACK: Plain Text Identification (For dismantle/craft messages)
        # If the bot is replying in a channel where a session is ACTIVE, 
        # it's almost certainly for that session's user.
        for uid, sess in self.active_sessions.items():
            if sess["channel_id"] == message.channel.id:
                return uid
        
        return None

    async def send_next_command(self, channel, uid):
        session = self.active_sessions.get(uid)
        print(f"--- DEBUG: Attempting to send command. Todo: {session.get('todo_list')} | Trade: {session.get('trade_list')} ---")
        if not session: return

        # 1. DISMANTLE FIRST: Check the guide's dismantle list
        if session.get("todo_list"):
            item = session["todo_list"].pop(0)
            session["last_action"] = "dismantle" # Set this so we can catch the success message
            return await channel.send(f"```rpg dismantle {item} all```")

        # 2. TRADE SECOND: If nothing left to dismantle, start trading
        if session.get("trade_list"):
            tid = session["trade_list"][0] # Peek (pop happens in refresh_tasks or after confirmation)
            session["last_action"] = "trade"
            return await channel.send(f"```rpg trade {tid} all```")
        
        # 3. GOAL REACHED
        area_num = session.get("real_area", "?")
        await channel.send(f"✅ **Optimized!** Area {area_num} finished.")
        if uid in self.active_sessions:
            del self.active_sessions[uid]

    def extract_area(self, embed):
        sources = [str(embed.title or ""), str(embed.description or ""), str(embed.footer.text if embed.footer else "")]
        for field in embed.fields:
            sources.append(field.name)
            sources.append(field.value)
        full_text = " ".join(sources).lower()
        m = re.search(r"area\*\*[:\s]*(\d+)", full_text, re.I)
        return int(m.group(1)) if m else None

    async def refresh_tasks(self, uid, embed=None, virtual_update=None):
        session = self.active_sessions[uid]
        guide = self.base_guides.get(session["logic_area"], {"dismantle": [], "trades": []})
        
        # 1. INITIAL SEED (Only from 'rpg i')
        if embed:
            field_0_value = embed.fields[0].value.lower()
            
            # Start with base items
            session["virtual_inv"] = {
                "wooden log": self.get_count("wooden log", field_0_value),
                "normie fish": self.get_count("normie fish", field_0_value),
                "apple": self.get_count("apple", field_0_value),
                "ruby": self.get_count("ruby", field_0_value)
            }
            # Add high tier items found in the embed
            for item in guide["dismantle"]:
              session["virtual_inv"][item] = self.get_count(item, field_0_value)

        # DYNAMICALLY ADD HIGHER ITEMS FROM YOUR GUIDE
        # This captures: epic log, super log, mega log, hyper log, ultra log, golden fish, epic fish, etc.
        todos = []
        for item in guide["dismantle"]:
            if session["virtual_inv"].get(item, 0) > 0:
              # We only add it if it's not already the current action
              todos.append(item)
            
        # Important: Reverse the list so it dismantles from highest to lowest (Ultra -> Hyper -> Mega)
        session["todo_list"] = list(reversed(todos)) 
        print(f"DEBUG: Updated Todo List: {session['todo_list']}")
        print(f"--- Inventory Seeded (Virtual): {session['virtual_inv']} ---")

        # 2. VIRTUAL UPDATE (For Trades)
        if virtual_update:
            gave_item, gave_amt, got_item, got_amt = virtual_update
            if gave_item in session["virtual_inv"]:
                session["virtual_inv"][gave_item] -= gave_amt
            if got_item in session["virtual_inv"]:
                session["virtual_inv"][got_item] += got_amt
            print(f"--- Virtual Trade Update: {gave_item} -> {got_item} | New Inv: {session['virtual_inv']} ---")

        # 3. REBUILD TRADE QUEUE (Only if todo_list is empty)
        new_trades = []
        if not session.get("todo_list"):
            ratios = self.area_ratios.get(session["real_area"], {})
            for t_str in guide["trades"]:
                parts = t_str.split(" to ")
                source, target = parts[0], parts[1]
                search_name = "wooden log" if source == "log" else "normie fish" if source == "fish" else source
                key = f"log_to_{target}" if source == "log" else source
                
                if session["virtual_inv"].get(search_name, 0) >= (ratios.get(key, 1) if source == "log" else 1):
                    tid = self.trade_ids.get(key)
                    if tid: new_trades.append(tid)

        session["trade_list"] = new_trades

async def setup(bot):
    await bot.add_cog(Trades(bot))