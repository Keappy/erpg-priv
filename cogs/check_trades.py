from math import floor
import discord
from discord.ext import commands
import re
import asyncio
from datetime import datetime, timedelta

class Trades(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_sessions = {}
        self.bot.loop.create_task(self.session_cleanup_loop())
        self.CAP_LIMIT = 25_000_000_000
        self.dismantle_returns = {
            "ultra log": ("hyper log", 10),
            "hyper log": ("mega log", 10),
            "mega log": ("super log", 10),
            "super log": ("epic log", 10),
            "epic log": ("wooden log", 25),
            "banana": ("apple", 15),
            "epic fish": ("golden fish", 100),
            "golden fish": ("normie fish", 15)
            # Dismantle only returns 80%
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
            11: {"log_to_fish": 3, "log_to_apple": 8, "log_to_ruby": 500}, 
            12: {"log_to_fish": 3, "log_to_apple": 8, "log_to_ruby": 350},
            13: {"log_to_fish": 3, "log_to_apple": 8, "log_to_ruby": 350}, 
            14: {"log_to_fish": 3, "log_to_apple": 12, "log_to_ruby": 350},
            15: {"log_to_fish": 3, "log_to_apple": 12, "log_to_ruby": 350},
            16: {"log_to_fish": 2, "log_to_apple": 4, "log_to_ruby": 250},
            17: {"log_to_fish": 2, "log_to_apple": 4, "log_to_ruby": 250},
            18: {"log_to_fish": 2, "log_to_apple": 4, "log_to_ruby": 250},
            19: {"log_to_fish": 2, "log_to_apple": 4, "log_to_ruby": 250},
            20: {"log_to_fish": 2, "log_to_apple": 4, "log_to_ruby": 250}
        }

        self.base_guides = {
            2: {"dismantle": ["epic log", "super log", "mega log", "hyper log", "ultra log"], "trades": ["log to fish"]},
            3: {"dismantle": ["banana", "epic log", "super log", "mega log", "hyper log", "ultra log"], "trades": ["apple to log", "log to fish"]},
            4: {"dismantle": ["golden fish", "epic fish", "epic log", "super log", "mega log", "hyper log", "ultra log"], "trades": ["fish to log", "log to apple"]},
            5: {"dismantle": ["golden fish", "epic fish", "epic log", "super log", "mega log", "hyper log", "ultra log"], "trades": ["ruby to log", "fish to log", "log to apple"]},
            7: {"dismantle": ["banana"], "trades": ["apple to log"]},
            8: {"dismantle": ["golden fish", "epic fish", "epic log", "super log", "mega log", "hyper log", "ultra log"], "trades": ["ruby to log", "fish to log", "log to apple"]},
            9: {"dismantle": ["banana", "epic log", "super log", "mega log", "hyper log", "ultra log"], "trades": ["ruby to log", "apple to log", "log to fish"]},
            10: {"dismantle": ["banana"], "trades": ["apple to log"]},
            11: {"dismantle": [], "trades": ["ruby to log"]},
            12: {"dismantle": [], "trades": []},
            15: {"dismantle": ["banana", "golden fish", "epic fish"], "trades": ["ruby to log", "fish to log", "apple to log"]}
        }
        self.craft_guides = {
            # Area: [(Source, Target, Recipe_Cost)]
            3: [("normie fish", "golden fish", 15), ("golden fish", "epic fish", 100)],
            5: [("apple", "banana", 15), ("wooden log", "ruby", 450)],
            7: [("wooden log", "ruby", 675)],
            8: [("wooden log", "ruby", 675), ("apple", "banana", 15)],
            9: [("normie fish", "golden fish", 15)], # Epic fish excluded (0.96 loss)
            15: [
                ("wooden log", "epic log", 25) # Further than epic log will cause into loss mats after time potion !! (⚠️ multiplier is lower than 0.81 after super log !!)   
            ]
        }


        self.area_map = {1 : 2, 6: 7, 13 : 12, 14 : 12}
        self.craft_area_map = {
            1: 3, 2: 3,   # Mapping 1 & 2 to 3 (Craft Golden/Epic Fish)
            4: 5,         # Mapping 4 to 5 (Apple -> Banana -> Ruby)
            6: 7,         # Mapping 6 to 7 (Log -> Ruby)
            13: 12, 14: 12
        }

        # In __init__
        self.command_locks = {}

    def get_overflow_tasks(self, session):
        import math
        area = session["real_area"]
        inv = session["virtual_inv"]
        
        # Strictly 25 Billion as requested
        CAP = 25000000000 
        tasks = []

        logic_area = self.craft_area_map.get(area, area)
        steps = self.craft_guides.get(logic_area, [])

        for source, target, cost in steps:
            count_source = inv.get(source, 0)
            count_target = inv.get(target, 0)

            # Calculate how many we are OVER 25b
            excess_source = max(0, count_source - CAP)
            
            # Use math.ceil so that any amount over 0 (like 8) results in 1 craft
            potential_new_target = math.ceil(excess_source / cost) if excess_source > 0 else 0
            total_potential_target = count_target + potential_new_target

            # 1. Cascade Check: Will the RESULT of this craft overflow the next tier?
            if total_potential_target > CAP:
                if target == "golden fish":
                    excess_target = total_potential_target - CAP
                    amt = math.ceil(excess_target / 100)
                    if amt > 0: tasks.append(("epic fish", amt))
                elif target == "banana":
                    if inv.get("wooden log", 0) > CAP:
                        tasks.append(("ruby", "all"))
                return tasks

            # 2. Standard Check: Is the source currently over 25b?
            if count_source > CAP:
                amt = math.ceil((count_source - CAP) / cost)
                if amt > 0:
                    tasks.append((target, amt if target != "ruby" else "all"))
                return tasks

        return tasks

    def get_count(self, item_name, text):
        # Regex matches the bold name and captures the following number/commas
        match = re.search(rf"\*\*{re.escape(item_name)}\*\*:\s*([\d,]+)", text)
        if match:
            return int(match.group(1).replace(",", ""))
        return 0
    
    async def session_cleanup_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            now = datetime.now()
            to_delete = []

            for uid, session in self.active_sessions.items():
                # If no activity for more than 2 minutes
                if now - session.get("last_seen", now) > timedelta(minutes=2):
                    to_delete.append(uid)

            for uid in to_delete:
                # Optional: send a message to the channel letting them know it expired
                session = self.active_sessions[uid]
                channel = self.bot.get_channel(session["channel_id"])
                if channel:
                    await channel.send(f"⏰ Session for <@{uid}> expired due to inactivity.")
                del self.active_sessions[uid]
                print(f"CLEANUP: Removed inactive session for {uid}")

            await asyncio.sleep(60) # Check every 30 seconds

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
                "current_task": None,
                "last_action": None,
                "mismatch_detected": False,
                "virtual_inv": {},
                "last_seen": datetime.now(), # Add this
                "pending_dismantle": None # Track what we just asked to dismantle
                
            }
            return

        # 2. Track USER Dismantle Commands
        if uid in self.active_sessions:
            session = self.active_sessions[uid]
            if "rpg dismantle" in content:
                session["last_seen"] = datetime.now() # Refresh the timer
                session["last_action"] = "dismantle"
                
                # Enhanced Regex: Matches "rpg dismantle item" or "rpg dismantle item amount"
                # This captures the item name and optionally the amount/all
                match = re.search(r"rpg dismantle\s+(.*?)(?:\s+(all|\d+))?$", content)
                if match:
                    item_to_lose = match.group(1).strip().lower()
                    
                    # Look at the saved task instead of the list
                    expected_item = session.get("current_task")
                    
                    print(f"DEBUG: Input='{item_to_lose}' | Expected='{expected_item}'")

                    if expected_item and item_to_lose != expected_item:
                        print(f"DEBUG: BLOCKING mismatch.")
                        # IMPORTANT: If they fail, we put the item BACK so they can try again
                        session["todo_list"].insert(0, expected_item)
                        return
                    
                    raw_amt = match.group(2)
                    
                    # Logic for amount: if 'all', we use inventory; if None, it's 1.
                    if raw_amt == "all":
                        amt = session["virtual_inv"].get(item_to_lose, 0)
                    elif raw_amt is None:
                        amt = 1
                    else:
                        amt = int(raw_amt)

                    session["pending_dismantle"] = {"item": item_to_lose, "amount": amt}
                    print(f"DEBUG: User dismantling {amt}x {item_to_lose}.")
            elif "rpg trade" in content:
                session["last_seen"] = datetime.now()
                
                match = re.search(r"rpg trade\s+([a-f])", content)
                if match:
                    typed_id = match.group(1)
                    expected_id = session.get("current_task")

                    # VALIDATION
                    if expected_id and typed_id != expected_id:
                        print(f"DEBUG: BLOCKING wrong trade ID. User: {typed_id} | Task: {expected_id}")
                        # NEW: Set a flag to ignore the inevitable error message from RPG Bot
                        session["mismatch_detected"] = True
                        return 

                    session["last_action"] = "trade"
                    # Reset flag if they finally got it right
                    session["mismatch_detected"] = False

        # 4. BOT RESPONSES: Processing RPG Bot's output
        if uid == 555955826880413696:
            # 1. Capture content from either text OR embed
            raw_content = message.content.lower()
            if not raw_content and message.embeds:
                raw_content = str(message.embeds[0].description).lower()
            
            # 2. Identify the user (If this fails, the whole block is skipped)
            target_uid = self.identify_user(message)
            if not target_uid or target_uid not in self.active_sessions: 
                return
            
            session = self.active_sessions[target_uid]
            
            # Step B: Double-check if we have an active session for this specific human
            if not target_uid or target_uid not in self.active_sessions:
                return

            session = self.active_sessions[target_uid]

            # Step C: Crucial Security Check - Is this the right channel?
            if session["channel_id"] != message.channel.id:
                return

            embed = message.embeds[0] if message.embeds else None

            is_dismantle_error = False
            if embed and embed.title and "don't have enough items" in embed.title.lower():
                is_dismantle_error = True

            if is_dismantle_error:
                # NEW: If we didn't expect a dismantle, ignore the error!
                if not session.get("pending_dismantle"):
                    print(f"DEBUG: Ignoring RPG Bot error because no dismantle was pending.")
                    return
                failed_item = "unknown item"
                
                if embed.description:
                    # Extracts the item name from the bold text in the description
                    match = re.search(r"\*\*(.*?)\*\*", embed.description)
                    if match:
                        failed_item = match.group(1).strip().lower()

                # Set status to SYNC_REQUIRED to stop automation and force a refresh
                session["status"] = "SYNC_REQUIRED"
                print(f"DEBUG: Dismantle failed. Forcing re-sync for {failed_item}")
                return await message.channel.send(
                    f"❌ **Dismantle Failed!** <@{target_uid}>, you are missing **{failed_item}**.\n"
                    f"Please run `rpg i` to re-sync your inventory."
                )
            
           # Case 1: "You don't have enough [item]"
            if "you don't have enough" in raw_content:
                # NEW: If we flagged a mismatch, ignore this specific bot response
                if session.get("mismatch_detected"):
                    print("DEBUG: Silence mismatch error (Not enough items)")
                    session["mismatch_detected"] = False
                    return
                
                # Extracts the item name after the emoji/mention
                item_match = re.search(r"enough\s+(?:<[^>]+>\s+)?(.*?),\s+check", raw_content)
                if item_match:
                    failed_item = item_match.group(1).strip().lower()
                    current_target = session.get("last_item_attempted")
                    
                    if current_target and failed_item in current_target:
                        session["status"] = "SYNC_REQUIRED"
                        return await message.channel.send(
                            f"❌ **Out of Items!** <@{target_uid}>, you need more **{failed_item}**.\n"
                            f"Please run `rpg i` to re-sync."
                        )

            # Case 2: "the amount has to be 1 or higher"
            elif "amount has to be 1 or higher" in raw_content:
                # NEW: If we flagged a mismatch, ignore this specific bot response
                if session.get("mismatch_detected"):
                    print("DEBUG: Silence mismatch error (Zero items)")
                    session["mismatch_detected"] = False
                    return
                
                current_target = session.get("last_item_attempted")
                session["status"] = "SYNC_REQUIRED"
                return await message.channel.send(
                    f"❌ **Empty Inventory!** <@{target_uid}>, your **{current_target or 'items'}** are at 0.\n"
                    f"Please run `rpg i` to refresh."
                )
            # --- SESSION LOGIC START ---

            # Profile Detection (Locks Area)
            if session["status"] == "WAITING_FOR_PROFILE" and embed and "profile" in str(embed.author.name).lower():
                area = self.extract_area(embed)
                for field in embed.fields:
                    print(f"field name: {field.name}")
                    print(f"field val: {field.value}")
                print()
                if area:
                    session["real_area"] = area
                    session["logic_area"] = self.area_map.get(area, area)
                    session["status"] = "ACTIVE"
                    await message.channel.send(
                        f"⚠️ **Warning**! There might be malfunctions in the current testing phase.\n"
                        f"Please do not use **work** commands during sessions!\n"
                        f"✅ **Area {area}** locked for **{session['username']}**. Please Run `rpg i`.\n")
            
            print(f"DEBUG: RPG Bot said: '{content}'")
            # 3. Robust Craft/Dismantle Detection
            if "successfully crafted" in raw_content:
                # Group 1: Amount, Group 2: Item Name, Group 3: Optional Refund %
                CRAFT_RE = r"([\d,]+).*?`([^`]+)` successfully crafted!(?:\s+woah!! you got ([\d.]+)% of the recipe back)?"
                match = re.search(CRAFT_RE, raw_content)
                
                if match:
                    got_amt = int(match.group(1).replace(",", ""))
                    yield_item = match.group(2).strip().lower() 
                    refund_percent = float(match.group(3)) if match.group(3) else 0.0
                    
                    # Normalize names for internal virtual_inv keys
                    if yield_item == "fish": yield_item = "normie fish"
                    elif yield_item == "log": yield_item = "wooden log"
                    
                    pending = session.get("pending_dismantle")
                    
                    # --- SCENARIO A: DISMANTLE (triggered by user/todo_list) ---
                    # We check 'pending' first because dismantle is a priority task
                    if pending:
                        high_tier_item = pending["item"]
                        
                        # 1. Update Virtual Inventory
                        session["virtual_inv"][high_tier_item] = max(0, session["virtual_inv"].get(high_tier_item, 0) - pending["amount"])
                        session["virtual_inv"][yield_item] = session["virtual_inv"].get(yield_item, 0) + got_amt
                        
                        # 2. VALIDATION LOGIC
                        recipe = self.dismantle_returns.get(high_tier_item)
                        if recipe:
                            _, recipe_amt = recipe
                            # Dismantle yield is strictly 80% of (Input Amount * Recipe Amount)
                            expected_yield = floor(pending["amount"] * recipe_amt * 0.8)
                            
                            if got_amt == expected_yield:
                                print(f"✅ Verified Dismantle: {high_tier_item} -> {got_amt} {yield_item}")
                            else:
                                print(f"⚠️ Yield mismatch: Expected {expected_yield}, got {got_amt}")

                        session["pending_dismantle"] = None # Reset 

                    # --- SCENARIO B: OVERFLOW CRAFT ---
                    else:
                        # 1. Try to find if it's a dismantle-style craft (e.g., getting normie fish from golden)
                        # We use the result (v[0]) to find the source (k) and cost (v[1])
                        recipe = self.dismantle_returns.get(yield_item)
                        
                        if recipe:
                            req_item, req_per_unit = recipe
                        else:
                            # 2. Fallback to standard craft guides (e.g., Apple -> Banana, Log -> Ruby)
                            # This flattens your craft_guides to find the source and cost
                            all_steps = [step for steps in self.craft_guides.values() for step in steps]
                            standard_recipe = next((s for s in all_steps if s[1] == yield_item), None)
                            
                            if standard_recipe:
                                req_item, _, req_per_unit = standard_recipe
                            else:
                                req_item, req_per_unit = None, 0

                        # If we found a recipe (either from dismantle_returns or craft_guides)
                        if req_item:
                            total_req = got_amt * req_per_unit
                            
                            # Using math.floor for the RPG Bot refund logic
                            refund_amt = floor(total_req * (refund_percent / 100))
                            actual_spent = total_req - refund_amt
                            
                            # Update Virtual Inventory
                            session["virtual_inv"][yield_item] = session["virtual_inv"].get(yield_item, 0) + got_amt
                            session["virtual_inv"][req_item] = max(0, session["virtual_inv"].get(req_item, 0) - actual_spent)
                            
                            print(f"DEBUG: Overflow Craft. Spent {actual_spent} {req_item} (Refunded {refund_amt}).")
                        else:
                            # This handles items the bot doesn't know how to track yet
                            print(f"DEBUG: Unknown craft target '{yield_item}'. Virtual inventory not updated.")

                    await self.refresh_tasks(target_uid)
                    await self.send_next_command(message.channel, target_uid)

            # Inside process_trade_logic, locate the "Trade Result Detector" elif:
            elif embed and any(x in str(embed.fields[0].name if embed.fields else "").lower() for x in ["traded items", "trade is done"]):
                field_val = embed.fields[0].value.lower()
                # Ensure we only process if our username is the one GIVING items
                if session["username"] in field_val:
                    # Stricter regex to catch the item you gave vs what NPC gave
                    gave_match = re.search(rf"{session['username']}.*?(log|fish|apple|ruby).*?x([\d,]+)", field_val)
                    npc_match = re.search(r"epic npc\*\*: .*?(log|fish|apple|ruby).*?x([\d,]+)", field_val)

                    if gave_match and npc_match:
                        def clean_item(name):
                            if "log" in name: return "wooden log"
                            if "fish" in name: return "normie fish"
                            return name.strip()

                        gave_item = clean_item(gave_match.group(1))
                        got_item = clean_item(npc_match.group(1))
                        gave_amt = int(gave_match.group(2).replace(",", ""))
                        got_amt = int(npc_match.group(2).replace(",", ""))

                        # Important: Refresh and then send command
                        await self.refresh_tasks(target_uid, None, virtual_update=(gave_item, gave_amt, got_item, got_amt))
                    await self.send_next_command(message.channel, target_uid)

            # Inventory Detector
            elif embed and "inventory" in str(embed.author.name).lower():
                # Verify it's the right user's inventory
                if session["username"] in str(embed.author.name).lower():
                    await self.refresh_tasks(target_uid, embed)
                    await self.send_next_command(message.channel, target_uid)
    
    def identify_user(self, message):
        # 1. Check for a direct mention in the message content (Handles Errors with pings)
        # This keeps 'target_uid' consistent with the pinged user
        mention_match = re.search(r"<@!?(\d+)>", message.content)
        if mention_match:
            uid_from_ping = int(mention_match.group(1))
            if uid_from_ping in self.active_sessions:
                return uid_from_ping

        # 2. Check Embeds (Handles standard trade/inventory/profile)
        if message.embeds:
            emb = message.embeds[0]
            # Check Avatar ID (The most reliable way)
            icon_url = str(emb.author.icon_url) if emb.author else ""
            match = re.search(r"avatars/(\d+)/", icon_url)
            if match: return int(match.group(1))
            
            # Scan text for username (Handles image_4c729c.png where only name appears)
            search_blob = f"{emb.author.name if emb.author else ''} {emb.description or ''} ".lower()
            search_blob += " ".join([f"{f.name} {f.value}" for f in emb.fields]).lower()
            for uid, sess in self.active_sessions.items():
                if sess["username"] in search_blob: return uid

        # 3. Last Resort: Channel Context
        for uid, sess in self.active_sessions.items():
            if sess["channel_id"] == message.channel.id:
                return uid
        
        return None

    async def send_next_command(self, channel, uid):
        session = self.active_sessions.get(uid)
        if not session: return

        # 1. IMMEDIATE LOCK: Update this first to prevent race conditions
        now = datetime.now()
        last_sent = session.get("last_msg_time", datetime.min)
        
        # Increased to 2.0s because your logs show triggers happening very fast
        if (now - last_sent).total_seconds() < 2.0:
            print(f"DEBUG: Blocked double-fire for {session['username']}")
            return

        session["last_msg_time"] = now

        # 2. DISMANTLE FIRST
        if session.get("todo_list"):
            item = session["todo_list"].pop(0)
            session["current_task"] = item
            session["last_item_attempted"] = item 
            return await channel.send(f"**{session['username'].capitalize()}** `rpg dismantle {item} all` !\n> ```rpg dismantle {item} all```")

        # 3. TRADE SECOND
        if session.get("trade_list"):
            tid = session["trade_list"].pop(0)
            session["current_task"] = tid
            reverse_map = {"a": "normie fish", "b": "wooden log", "c": "apple", "d": "wooden log", "e": "ruby", "f": "wooden log"}
            session["last_item_attempted"] = reverse_map.get(tid)
            return await channel.send(f"**{session['username'].capitalize()}** `rpg trade {tid} all` !\n> ```rpg trade {tid} all```")

        # 4. CRAFT/OVERFLOW THIRD
        if session.get("craft_list"):
            target, amt = session["craft_list"].pop(0)
            session["current_task"] = target
            if target == "ruby" and amt == "all":
                session["current_task"] = "f"
                return await channel.send(f"**{session['username'].capitalize()}** `rpg trade f all` !\n> ```rpg trade f all```")
            return await channel.send(f"**{session['username'].capitalize()}** `rpg craft {target} {amt}` !\n> ```rpg craft {target} {amt}```")

        # 5. FINISHED
        await channel.send(f"✅ **Optimized!** Area {session.get('real_area', '?')} finished.")
        if uid in self.active_sessions:
            del self.active_sessions[uid]

    def extract_area(self, embed):
        # Combine all possible text sources from the embed
        sources = [str(embed.title or ""), str(embed.description or ""), str(embed.footer.text if embed.footer else "")]
        for field in embed.fields:
            sources.append(field.name)
            sources.append(field.value)
        full_text = " ".join(sources).lower()

        # UPDATED REGEX: Specifically looks for the number after "max:"
        # This matches: (max: 8) and captures the 8
        m = re.search(r"max:\s*(\d+)", full_text, re.I)
        
        if m:
            return int(m.group(1))
        
        # FALLBACK: If "max" isn't found, look for the standard Area number
        fallback = re.search(r"area\*\*[:\s]*(\d+)", full_text, re.I)
        return int(fallback.group(1)) if fallback else None

    async def refresh_tasks(self, uid, embed=None, virtual_update=None):
        session = self.active_sessions[uid]
        logic_area = self.area_map.get(session["real_area"], session["real_area"])
        guide = self.base_guides.get(logic_area, {"dismantle": [], "trades": []})
        
        # 1. UPDATE VIRTUAL INVENTORY
        if embed:
            f0 = embed.fields[0].value.lower()
            # List every single item the bot ever tracks
            all_tracked_items = [
                "wooden log", "normie fish", "apple", "ruby", "banana", 
                "golden fish", "epic fish", "ultra log", "hyper log", 
                "mega log", "super log", "epic log"
            ]
            
            # FORCE refresh: if it's not in the embed, it's 0.
            for item in all_tracked_items:
                count = self.get_count(item, f0)
                session["virtual_inv"][item] = count
                if count > 0:
                    print(f"DEBUG: Sync {item} = {count}")

        if virtual_update:
            gave_item, gave_amt, got_item, got_amt = virtual_update
            session["virtual_inv"][gave_item] = max(0, session["virtual_inv"].get(gave_item, 0) - gave_amt)
            session["virtual_inv"][got_item] = session["virtual_inv"].get(got_item, 0) + got_amt

        # 2. REBUILD TODO LIST (Dismantle)
        # Only add to list if count is actually > 0 in virtual_inv
        todos = [item for item in guide["dismantle"] if session["virtual_inv"].get(item, 0) > 0]
        session["todo_list"] = list(reversed(todos)) 

        # 3. REBUILD TRADE QUEUE
        new_trades = []
        if not session["todo_list"]:
            ratios = self.area_ratios.get(session["real_area"], {})
            for t_str in guide["trades"]:
                parts = t_str.split(" to ")
                src, target = parts[0], parts[1]
                key = f"log_to_{target}" if src == "log" else src
                search_name = "wooden log" if src == "log" else "normie fish" if src == "fish" else src
                
                if session["virtual_inv"].get(search_name, 0) >= ratios.get(key, 1):
                    tid = self.trade_ids.get(key)
                    if tid: new_trades.append(tid)
        session["trade_list"] = new_trades

        # 4. REBUILD CRAFT QUEUE
        session["craft_list"] = []
        if not session["todo_list"] and not session["trade_list"]:
            overflow_tasks = self.get_overflow_tasks(session)
            session["craft_list"] = overflow_tasks

async def setup(bot):
    await bot.add_cog(Trades(bot))