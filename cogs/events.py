import asyncio
import discord
from discord.ext import commands
import time
import re

class EventTracker(commands.Cog):
    def __init__(self, bot, data, save_func):
        self.bot = bot
        self.data = data
        self.save_data = save_func
        self.last_event_time = {}

    def parse_value(self, val_str):
        val_str = val_str.lower().replace(",", "").strip()
        multipliers = {'k': 1000, 'm': 1000000, 'b': 1000000000, 't': 1000000000000, 'q': 1000000000000000}
        for char, mult in multipliers.items():
            if val_str.endswith(char):
                try: return float(val_str[:-1]) * mult
                except: return 0
        try: return float(val_str)
        except: return 0

    async def check_rpg_events(self, message):
        cfg = self.data.get("server_configs", {}).get("global", {})
        bot_ids = [cfg.get("EPIC_RPG_ID"), cfg.get("IDLE_FARM_ID")]
        if message.author.id not in bot_ids:
            return

        is_result_msg = self.is_result_embed(message)
        event_type, is_starting, is_ending = self.parse_buttons(message)
        
        chan_id_str = str(message.channel.id)
        squads = self.data.get("squadrons", {})
        squad = squads.get(chan_id_str)

        # Force end phase for events where buttons never disable (Arena/Miniboss)
        if is_result_msg and squad:
            active = squad.get("active_events", [])
            if "arena" in active:
                event_type, is_ending = "arena", True
            elif "miniboss" in active:
                event_type, is_ending = "miniboss", True

        if not event_type: return

        now = time.time()
        chan_ev_key = f"{chan_id_str}_{event_type}"

        # --- PHASE 1: EVENT START ---
        if is_starting:
            if (now - self.last_event_time.get(f"start_{chan_ev_key}", 0)) < 4: return
            self.last_event_time[f"start_{chan_ev_key}"] = now

            if squad is not None:
                if "active_events" not in squad: squad["active_events"] = []
                if event_type not in squad["active_events"]:
                    squad["active_events"].append(event_type)
                    self.save_data(self.data)
                
                if squad.get("events_enabled", True) and not squad.get("squad_only_mode", False):
                    manager = self.bot.get_cog("SquadronManager")
                    if manager: await manager.update_permissions(message.channel, hide=False)

            base_msg = self.get_event_config_msg(event_type)
            await message.channel.send(base_msg)

            if event_type == "catch" and message.embeds:
                field_val = message.embeds[0].fields[0].value if message.embeds[0].fields else ""
                # Updated to capture the MAX value (after the ~) for big/super big catches
                match = re.search(r"~\s*([\d,]+[kmbtq]?)", field_val, re.IGNORECASE)
                if match:
                    val_to_check = self.parse_value(match.group(1))
                    special_ping = None
                    if 500_000_000_000_000 > val_to_check >= 1_000_000_000_000:
                        special_ping = "<@&1475848220453109892>"
                    elif val_to_check >= 500_000_000_000_000:
                        special_ping = "<@&1475850290229018684>"
                    
                    if special_ping: 
                        await message.reply(special_ping)

        # --- PHASE 2: EVENT END ---
        elif is_ending:
            if squad is not None:
                if "active_events" in squad and event_type in squad["active_events"]:
                    squad["active_events"].remove(event_type)
                    self.save_data(self.data)

            if (now - self.last_event_time.get(f"end_{chan_ev_key}", 0)) < 2: return
            self.last_event_time[f"end_{chan_ev_key}"] = now

            was_visible = False
            if squad is not None and len(squad.get("active_events", [])) == 0:
                manager = self.bot.get_cog("SquadronManager")
                if manager:
                    overwrites = message.channel.overwrites_for(message.guild.default_role)
                    was_visible = overwrites.view_channel is not False 
                    await manager.update_permissions(message.channel, hide=True)

                target_message = message
                is_result = is_result_msg

                if not is_result:
                    await asyncio.sleep(0.5) 
                    async for msg in message.channel.history(limit=40):
                        if msg.author.id in bot_ids and self.is_result_embed(msg):
                            target_message = msg
                            is_result = True
                            break

                if is_result and was_visible:
                    try:
                        await target_message.reply("🔒 **Event ended. Channel hidden.**")
                    except:
                        await message.channel.send("🔒 **Event ended. Channel hidden.**")

    def is_result_embed(self, message):
        if not message.embeds: return False
        emb = message.embeds[0]
        
        # 1. Direct Text Triggers
        desc = emb.description or ""
        title = emb.title or ""
        if any(x in desc for x in ["See `idle randomevents` for more information about random event buffs and nerfs"]): return True
        if any(x in title for x in ["has not been defeated", "has been defeated!"]): return True

        # 2. EPIC RPG (Fields/Author)
        # We replace ':' with ' ' so :moneybag: becomes ' moneybag '
        # AND we keep the original emoji 💰 in the text
        field_content = f"{emb.author.name if emb.author else ''}".replace("*", "")
        clean_content = field_content.replace(":", " ")
        for field in emb.fields:
            text = f" {field.name} {field.value}".replace("*", "")
            field_content += text
            clean_content += text.replace(":", " ")
        print(f"{field_content}")
        # Trigger if "need at least 2 players" appears in fields
        if "Rip, arena events need at least 2 players" in field_content or "Arena boost" in field_content:
            return True
        
        # Comprehensive list including both versions of the moneybag
        items = [
            "coins", "moneybag", "💰", "normie fish", "wooden logs", 
            "EDGY lootbox", "EPIC lootbox", "rare lootbox", 
            "uncommon lootbox", "common lootbox",
            "599768567105191964", "568572122788659250", 
            "568572122788659253", "568572122788659211", "568572122226491395",
            "697940429999439872", "770880739926999070"
        ]
        
        item_regex = f"({'|'.join(items)})"

        patterns = [
            # A & B: Item nearby "Everyone got"
            fr"Everyone got.*{item_regex}", 
            fr"{item_regex}.*Everyone got",
            # C: "Everyone got" followed by numbers/commas/spaces (The 412,499... logic)
            r"Everyone got (\d+|,| )+", 
            # D: Bosses & Rare Hunt
            r"has (not )?been defeated",
            r"THE LEGENDARY BOSS DIED! EVERYONE LEVELED UP",
            r"THE RARE HUNT MONSTER DIED! EVERYONE GOT THEIR HUNT COOLDOWN RESET"
        ]
        
        # We check both the raw content (for the 💰) and the clean content (for 'moneybag')
        return any(re.search(p, field_content, re.IGNORECASE) or re.search(p, clean_content, re.IGNORECASE) for p in patterns)
    
    def get_event_config_msg(self, event_type):
        configs = self.data.get("server_configs", {}).get("global", {}).get("event_configs", {})
        event_cfg = configs.get(event_type)
        return event_cfg["msg"] if event_cfg and "msg" in event_cfg else f"⚠️ {event_type.upper()} started!"
    
    def parse_buttons(self, message):
        if not message.components: return None, False, False
        for row in message.components:
            for btn in row.children:
                if not isinstance(btn, discord.Button): continue
                lbl = (btn.label or "").upper()
                cid = (btn.custom_id or "").lower()
                
                if lbl == "BOOST": continue

                event = None
                if lbl == "CATCH": event = "catch"
                elif lbl == "CUT": event = "cut"
                elif lbl == "LURE": event = "lure"
                elif lbl == "SUMMON": event = "summon"
                elif lbl == "PACK": event = "pack"
                elif lbl == "OHMMM": event = "ohmmm"
                elif lbl == "TIME TO FIGHT": event = "boss"
                elif lbl == "LETS GET THAT PICKAXE": event = "pickaxe"
                elif lbl == "JOIN" or "join" in cid:
                    emo = str(btn.emoji).lower() if btn.emoji else ""
                    # Priority check for IDs which are consistent in slash commands
                    if "arena" in cid or "swords" in emo: event = "arena"
                    elif "miniboss" in cid or "dagger" in emo: event = "miniboss"
                    elif "idlons" in emo: event = "lucky rewards"
                
                if event: return event, not btn.disabled, btn.disabled
        return None, False, False

async def setup(bot):
    await bot.add_cog(EventTracker(bot, bot.squad_data, bot.save_data))