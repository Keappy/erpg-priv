import discord
from discord.ext import commands
import time

class EventTracker(commands.Cog):
    def __init__(self, bot, data, save_func):
        self.bot = bot
        self.data = data
        self.save_data = save_func
        self.last_event_time = {}

    def get_role_ping(self, event_type):
        """Pulls the role ID from the JSON config."""
        roles = self.data.get("server_configs", {}).get("global", {}).get("roles", {})
        role_id = roles.get(event_type)
        return f"<@&{role_id}>" if role_id else "@everyone"

    def get_event_config(self, event_type):
        configs = self.data.get("server_configs", {}).get("global", {}).get("event_configs", {})
        event_cfg = configs.get(event_type)
        
        if event_cfg:
            return event_cfg['msg']
        
        # Simple string fallback
        return f"⚠️ {event_type.upper()} started (Config missing)!"
        
        # Fallback if event is missing from config
        return "No Role Configured", f"{event_type.upper()} started!"

    async def check_rpg_events(self, message):
        cfg = self.data.get("server_configs", {}).get("global", {})
        if message.author.id not in [cfg.get("EPIC_RPG_ID"), cfg.get("IDLE_FARM_ID")]:
            return

        event_type, is_starting, is_ending = self.parse_buttons(message)
        if not event_type: return

        now = time.time()
        chan_id_str = str(message.channel.id)
        chan_ev_key = f"{chan_id_str}_{event_type}"
        squad = self.data.get("squadrons", {}).get(chan_id_str)

        if not squad: return # Only run logic for registered squads

        if "active_events" not in squad:
            squad["active_events"] = []

        # --- PHASE 1: EVENT START ---
        if is_starting:
            if (now - self.last_event_time.get(f"start_{chan_ev_key}", 0)) < 4: return
            self.last_event_time[f"start_{chan_ev_key}"] = now
            
            # Add to active list
            if event_type not in squad["active_events"]:
                squad["active_events"].append(event_type)
                self.save_data(self.data)

            # Announce the event
            custom_msg = self.get_event_config(event_type)
            await message.channel.send(f"🔔 {custom_msg}")

            # UNHIDE LOGIC: Unhide if Auto-unhide is ON and it's NOT in Squad-Only (Permanent Lock) mode
            if squad.get("events_enabled", True) and not squad.get("squad_only_mode", False):
                manager = self.bot.get_cog("SquadronManager")
                if manager:
                    await manager.update_permissions(message.channel, hide=False)

        # --- PHASE 2: EVENT END ---
        elif is_ending:
            if (now - self.last_event_time.get(f"end_{chan_ev_key}", 0)) < 2: return
            self.last_event_time[f"end_{chan_ev_key}"] = now

            if event_type in squad["active_events"]:
                squad["active_events"].remove(event_type)
                self.save_data(self.data)
            
            if len(squad["active_events"]) == 0:
                is_manual_hidden = squad.get("is_hidden", True)
                
                if is_manual_hidden:
                    manager = self.bot.get_cog("SquadronManager")
                    if manager:
                        # --- CHECK IF UNHIDE ACTUALLY HAPPENED ---
                        # We only send the message if the channel is currently visible
                        overwrites = message.channel.overwrites_for(message.guild.default_role)
                        was_visible = overwrites.view_channel is True

                        await manager.update_permissions(message.channel, hide=True)
                        
                        # Only announce if it was actually visible to prevent spam
                        if was_visible:
                            await message.channel.send(f"🔒 **{event_type.upper()} ended. Channel hidden.**")
                        else:
                            # Just a quiet confirmation that the event is over
                            await message.channel.send(f"✅ **{event_type.upper()}**")
                else:
                    await message.channel.send(f"✅ **{event_type.upper()} ended.**")

    def parse_buttons(self, message):
        """Detects event type and status via buttons, matching JSON keys."""
        if not message.components:
            return None, False, False
        
        for row in message.components:
            for btn in row.children:
                if isinstance(btn, discord.Button):
                    lbl = btn.label.upper() if btn.label else ""
                    
                    event = None
                    # Match these EXACTLY to your JSON keys
                    if lbl == "JOIN":
                        # Check if it's Miniboss/Idlons vs Arena
                        emo = str(btn.emoji).lower() if btn.emoji else ""
                        if "swords" in emo: event = "arena"
                        elif "idlons" in emo: event = "lucky rewards" # Matches JSON
                        elif "dagger" in emo: event = "miniboss" # Fallback for IDLONS join
                    elif lbl == "PACK": event = "pack"
                    elif lbl == "OHMMM": event = "ohmmm"
                    elif lbl == "SUMMON": event = "summon"
                    elif lbl == "TIME TO FIGHT": event = "boss"
                    elif lbl == "LETS GET THAT PICKAXE": event = "pickaxe"
                    elif lbl == "CATCH": event = "catch"
                    elif lbl == "CUT": event = "cut"
                    elif lbl == "LURE": event = "lure" # Fixed (was fish)

                    if event:
                        # Return: event_name, is_starting, is_ending
                        return event, not btn.disabled, btn.disabled
        return None, False, False
    
async def setup(bot):
    await bot.add_cog(EventTracker(bot, bot.squad_data, bot.save_data))