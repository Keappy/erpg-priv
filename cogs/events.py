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

    @commands.Cog.listener()
    async def on_message(self, message):
        await self.check_rpg_events(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        await self.check_rpg_events(after)

    def get_event_config(self, event_type):
        """Pulls both the role ID and custom message from the new JSON config."""
        # Navigate to the new event_configs section
        configs = self.data.get("server_configs", {}).get("global", {}).get("event_configs", {})
        event_cfg = configs.get(event_type)
        
        if event_cfg:
            message = event_cfg['msg']
            return message
        
        # Fallback if event is missing from config
        return "No Role Configured", f"{event_type.upper()} started!"

    async def check_rpg_events(self, message):
        cfg = self.data.get("server_configs", {}).get("global", {})
        # Verify message is from RPG bots
        if message.author.id not in [cfg.get("EPIC_RPG_ID"), cfg.get("IDLE_FARM_ID")]:
            return

        event_type, is_starting, is_ending = self.parse_buttons(message)
        if not event_type:
            return

        now = time.time()
        chan_id_str = str(message.channel.id)
        chan_ev_key = f"{chan_id_str}_{event_type}"
        squad = self.data.get("squadrons", {}).get(chan_id_str)

        # --- PHASE 1: THE PING (UNIVERSAL) ---
        if is_starting:
            # Prevent double-pings from message edits
            if (now - self.last_event_time.get(f"start_{chan_ev_key}", 0)) < 4:
                return
            self.last_event_time[f"start_{chan_ev_key}"] = now
            
            # GET NEW CONFIG DATA
            custom_msg = self.get_event_config(event_type)
            
            # Send the Navi-style formatted message
            await message.channel.send(f"🔔 {custom_msg}")

        # --- PHASE 2: SQUADRON PERMISSIONS ---
        # Only runs if the channel is a registered squadron
        if squad:
            if "active_events" not in squad:
                squad["active_events"] = []

            if is_starting:
                if event_type not in squad["active_events"]:
                    squad["active_events"].append(event_type)
                    self.save_data(self.data)

                # PERMISSION CHECK: 
                # Should we unhide? Only if events_enabled=True AND squad_only=False
                can_unhide = squad.get("events_enabled", True) and not squad.get("squad_only_mode", False)
                
                if can_unhide:
                    manager = self.bot.get_cog("SquadronManager")
                    if manager:
                        await manager.update_permissions(message.channel, hide=False)
                else:
                    # If it's flagged OFF, we send a small note so they know why it's still hidden
                    if squad.get("squad_only_mode"):
                        await message.channel.send("ℹ️ *Squad-Only mode is ON. Channel remains hidden.*", delete_after=5)
                    elif not squad.get("events_enabled"):
                        await message.channel.send("ℹ️ *Events unhide is OFF. Channel remains hidden.*", delete_after=5)

            elif is_ending:
                if (now - self.last_event_time.get(f"end_{chan_ev_key}", 0)) < 2:
                    return
                self.last_event_time[f"end_{chan_ev_key}"] = now

                if event_type in squad["active_events"]:
                    squad["active_events"].remove(event_type)
                    self.save_data(self.data)
                
                # HIDE LOGIC: Only hide if the list is finally empty
                if len(squad["active_events"]) == 0:
                    manager = self.bot.get_cog("SquadronManager")
                    if manager:
                        await manager.update_permissions(message.channel, hide=True)
                        await message.channel.send(f"🔒 **{event_type.upper()} ended. Channel hidden.**")
                else:
                    remaining = ", ".join(squad["active_events"]).upper()
                    await message.channel.send(f"✅ **{event_type.upper()} ended.** (Still active: {remaining})")

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