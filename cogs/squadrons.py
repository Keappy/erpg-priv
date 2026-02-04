import discord
from discord.ext import commands

class SquadronManager(commands.Cog):
    def __init__(self, bot, data, save_func):
        self.bot = bot
        self.data = data
        self.save_data = save_func

    # --- PERMISSIONS HELPER ---
    async def update_permissions(self, channel, hide=True):
        squad = self.data["squadrons"].get(str(channel.id))
        if not squad: return

        cfg = self.data.get("server_configs", {}).get("global", {})
        rpg_role_id = cfg.get("EPIC_RPG_ROLE_ID")
        mod_role_id = cfg.get("MODERATOR_ROLE_ID")

        # Determine if the channel is "Locked" (Members can't send messages)
        is_locked = squad.get("is_locked", False)
        send_perms = False if is_locked else None # None follows category/default

        overwrites = {
            channel.guild.default_role: discord.PermissionOverwrite(view_channel=not hide, send_messages=send_perms),
            channel.guild.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True)
        }

        if rpg_role_id:
            rpg_role = channel.guild.get_role(int(rpg_role_id))
            if rpg_role: 
                overwrites[rpg_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        if mod_role_id:
            mod_role = channel.guild.get_role(int(mod_role_id))
            if mod_role: 
                overwrites[mod_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        all_uids = [squad["owner_id"]] + squad["members"]
        for uid in all_uids:
            member = channel.guild.get_member(int(uid))
            if member: 
                # If locked, members can only view, not send.
                overwrites[member] = discord.PermissionOverwrite(view_channel=True, send_messages=send_perms)

        await channel.edit(overwrites=overwrites)

    def is_mod_or_owner(self, ctx, squad):
        is_owner = squad["owner_id"] == ctx.author.id
        mod_role_id = self.data.get("server_configs", {}).get("global", {}).get("MODERATOR_ROLE_ID")
        is_mod = ctx.author.guild_permissions.manage_channels or any(r.id == mod_role_id for r in ctx.author.roles)
        return is_owner or is_mod

    async def get_squad_embed(self, channel_id):
        squad = self.data["squadrons"].get(str(channel_id))
        if not squad: return None

        owner = f"<@{squad['owner_id']}> (Owner)"
        members = "\n".join([f"<@{uid}>" for uid in squad["members"]]) if squad["members"] else "None"
        
        event_status = "✅ Enabled" if squad.get("events_enabled", True) else "❌ Disabled"
        squad_only = "🔒 ON (Always Hidden)" if squad.get("squad_only_mode", False) else "🔓 OFF (Default)"
        state_text = "🙈 Hidden" if squad.get("is_hidden", True) else "👁️ Visible"
        
        # New Status Fields
        lock_status = "🔒 Locked" if squad.get("is_locked", False) else "🔓 Unlocked"
        slow_val = squad.get("slowmode", 0)
        slow_status = f"⏱️ {slow_val}s" if slow_val > 0 else "🚀 Off"

        embed = discord.Embed(
            title="👥 Squadron Information", 
            description=f"Settings and members for <#{channel_id}>",
            color=discord.Color.blue()
        )
        embed.add_field(name="🔔 Auto-Unhide", value=event_status, inline=True)
        embed.add_field(name="🛡️ Squad-Only", value=squad_only, inline=True)
        embed.add_field(name="📍 Visibility", value=state_text, inline=True)
        embed.add_field(name="🔒 Chat Lock", value=lock_status, inline=True)
        embed.add_field(name="⏱️ Slowmode", value=slow_status, inline=True)
        embed.add_field(name="⭐ Owner", value=owner, inline=False)
        embed.add_field(name="Members", value=members, inline=False)
        
        active = ", ".join(squad.get("active_events", []))
        if active:
            embed.add_field(name="🔥 Active Events", value=active.upper(), inline=False)

        prefix = self.bot.command_prefix
        display_prefix = prefix[0] if isinstance(prefix, (list, tuple)) else prefix
        embed.set_footer(text=f"For more information use {display_prefix}help")
        return embed
   
    # --- COMMANDS ---

# --- NEW COMMANDS: LOCK, UNLOCK, SLOWMODE ---

    @commands.command()
    async def lock(self, ctx):
        """Disables sending messages for squadron members."""
        squad = self.data["squadrons"].get(str(ctx.channel.id))
        if not squad or not self.is_mod_or_owner(ctx, squad):
            return await ctx.send("❌ Access denied.")
        
        squad["is_locked"] = True
        self.save_data(self.data)
        await self.update_permissions(ctx.channel, hide=squad.get("is_hidden", True))
        await ctx.send("🔒 **Squadron locked.** Only Moderators can chat.")

    @commands.command()
    async def unlock(self, ctx):
        """Re-enables sending messages for squadron members."""
        squad = self.data["squadrons"].get(str(ctx.channel.id))
        if not squad or not self.is_mod_or_owner(ctx, squad):
            return await ctx.send("❌ Access denied.")
        
        squad["is_locked"] = False
        self.save_data(self.data)
        await self.update_permissions(ctx.channel, hide=squad.get("is_hidden", True))
        await ctx.send("🔓 **Squadron unlocked.** Members can now chat.")

    @commands.command()
    async def slowmode(self, ctx, seconds: int):
        """Sets slowmode for the channel. Use 0 to disable."""
        squad = self.data["squadrons"].get(str(ctx.channel.id))
        if not squad or not self.is_mod_or_owner(ctx, squad):
            return await ctx.send("❌ Access denied.")
        
        if seconds < 0 or seconds > 21600:
            return await ctx.send("❌ Invalid time (0-21600 seconds).")

        squad["slowmode"] = seconds
        self.save_data(self.data)
        await ctx.channel.edit(slowmode_delay=seconds)
        await ctx.send(f"⏱️ **Slowmode set to {seconds} seconds.**")

    @commands.command(name="squad", aliases=["mysquads"])
    async def squad(self, ctx):
        """Tells the user which squadron channel they belong to with clickable links."""
        user_id = ctx.author.id
        found_squads = []

        # Access the squadrons dictionary from your data
        squads = self.data.get("squadrons", {})

        # Search through all saved squadrons
        # k is the channel_id, v is the squad data dictionary
        for channel_id, squad_info in squads.items():
            owner_id = squad_info.get("owner_id")
            members = squad_info.get("members", [])

            # Check if user is owner or in the member list
            # We convert to int just in case they are stored as strings in JSON
            if int(owner_id) == user_id or any(int(m) == user_id for m in members):
                # Format as <#ID> to make it a clickable blue link
                found_squads.append(f"<#{channel_id}>")

        if found_squads:
            channels_str = ", ".join(found_squads)
            await ctx.send(f"👥 {ctx.author.mention}, you are in these squadrons: {channels_str}")
        else:
            await ctx.send(f"❌ {ctx.author.mention}, you aren't in any squadrons yet.")

    @commands.command(hidden=True)
    async def viewsquadrons(self, ctx):
        """Moderator only: Lists all active squadron channels."""
        # Permission Check
        mod_role_id = self.data.get("server_configs", {}).get("global", {}).get("MODERATOR_ROLE_ID")
        is_mod = ctx.author.guild_permissions.manage_channels or any(r.id == mod_role_id for r in ctx.author.roles)
        
        if not is_mod and ctx.author.id != ctx.guild.owner_id:
            return await ctx.send("❌ This command is restricted to the Developer Team and Moderators.")

        if not self.data["squadrons"]:
            return await ctx.send("📂 No squadrons have been created yet.")

        # Build the list of links
        squad_list = []
        for channel_id, info in self.data["squadrons"].items():
            owner = f"<@{info['owner_id']}>"
            squad_list.append(f"• <#{channel_id}> — Owner: {owner}")

        # Split into multiple embeds if the list is huge (Discord limit)
        embed = discord.Embed(
            title="🛡️ Moderator Oversight: Active Squadrons",
            description="\n".join(squad_list),
            color=discord.Color.dark_red()
        )
        embed.set_footer(text=f"Total Squadrons: {len(self.data['squadrons'])}")
        await ctx.send(embed=embed)

    @commands.command(hidden=True)
    @commands.has_permissions(administrator=True)
    async def setcategory(self, ctx, category_id: int):
        """Updates the Private Battalions category ID in the config."""
        try:
            # 1. Update the nested value in memory
            self.bot.squad_data["server_configs"]["global"]["CATEGORY_ID"] = category_id
            
            # 2. Save the updated dictionary back to squadrons_data.json
            self.bot.save_data()
            
            await ctx.send(f"✅ **Category Updated!** All new squadrons will now be created in: `{category_id}`")
        except KeyError:
            await ctx.send("❌ Error: Could not find 'server_configs' or 'global' in your JSON structure.")
        except Exception as e:
            await ctx.send(f"❌ An unexpected error occurred: `{e}`")

    @commands.command(aliases=["modhelp"], hidden=True)
    async def devhelp(self, ctx):
        """Displays hidden commands for the Admin/Dev team."""
        mod_role_id = self.data.get("server_configs", {}).get("global", {}).get("MODERATOR_ROLE_ID")
        is_mod = ctx.author.guild_permissions.manage_channels or any(r.id == mod_role_id for r in ctx.author.roles)

        if not is_mod and ctx.author.id != ctx.guild.owner_id:
            return # Silently ignore so non-admins don't even know it exists

        prefix = ctx.prefix
        embed = discord.Embed(
            title="👨‍💻 Developer & Moderator Dashboard",
            description="Restricted commands for server maintenance.",
            color=discord.Color.gold()
        )

        dev_cmds = (
            f"`{prefix}viewsquadrons` - View all private squadron links\n"
            f"`{prefix}clearactive` - Reset event status for any channel\n"
            f"`{prefix}transferowner` - Forcefully change a squad owner\n"
            f"`{prefix}rename` - Override a channel name\n"
            f"`{prefix}showlist [channel]` - Shows info for specified channel\n"
            f"`{prefix}setcategory` - Moves all registered squadrons into the designated category\n"
            f"`{prefix}config` - Opens the global event configuration menu."
        )
        embed.add_field(name="⚠️ Sensitive Commands", value=dev_cmds, inline=False)
        
        embed.set_footer(text="Confidential - Internal Use Only")
        await ctx.send(embed=embed)

    @commands.command()
    async def clearactive(self, ctx):
        """Clears the active events list if it gets stuck."""
        squad = self.data["squadrons"].get(str(ctx.channel.id))
        if not squad or not self.is_mod_or_owner(ctx, squad):
            return await ctx.send("❌ Access denied.")
        """Manually unhides the channel and sets state to VISIBLE."""
        squad = self.data["squadrons"].get(str(ctx.channel.id))
        if not squad or not self.is_mod_or_owner(ctx, squad):
            return await ctx.send("❌ Access denied.")
        
        squad["is_hidden"] = False # Set current state
        self.save_data(self.data)
        
        await self.update_permissions(ctx.channel, hide=False)
        await ctx.send("🔓 **Channel manually unhidden.** (State: Visible)")    
        
        
        squad["active_events"] = []
        self.save_data(self.data)
        await ctx.send("🧹 **Active events cleared for this channel.**")

    # --- UPDATED CREATE COMMAND ---
    @commands.command()
    async def create(self, ctx, *, name: str):
        if any(s["owner_id"] == ctx.author.id for s in self.data["squadrons"].values()):
            return await ctx.send("❌ You already own a squadron!")

        cat_id = self.data["server_configs"]["global"].get("CATEGORY_ID")
        category = self.bot.get_channel(cat_id)
        
        new_channel = await ctx.guild.create_text_channel(name=name, category=category)
        
        # Added new keys to initial JSON entry
        self.data["squadrons"][str(new_channel.id)] = {
            "owner_id": ctx.author.id,
            "members": [],
            "events_enabled": True,
            "squad_only_mode": False,
            "active_events": [],
            "is_hidden": True,
            "is_locked": False,
            "slowmode": 0
        }
        self.save_data(self.data)
        await self.update_permissions(new_channel, hide=True)
        
        await ctx.send(f"✅ Squadron **{name}** created! Link: {new_channel.mention}")
        embed = await self.get_squad_embed(new_channel.id)
        await new_channel.send(f"Welcome {ctx.author.mention}!", embed=embed)

    # --- EXISTING COMMANDS (UNCHANGED BUT INCLUDED FOR CONTEXT) ---
    @commands.command()
    async def showlist(self, ctx, target_channel: discord.TextChannel = None):
        target = target_channel or ctx.channel
        squad = self.data["squadrons"].get(str(target.id))
        if not squad:
            return await ctx.send(f"❌ <#{target.id}> is not a squadron.")

        if target != ctx.channel:
            mod_role_id = self.data.get("server_configs", {}).get("global", {}).get("MODERATOR_ROLE_ID")
            is_mod = ctx.author.guild_permissions.manage_channels or any(r.id == mod_role_id for r in ctx.author.roles)
            if not is_mod:
                return await ctx.send("❌ Moderators only for viewing other channels.")

        embed = await self.get_squad_embed(target.id)
        await ctx.send(embed=embed)

    @commands.command()
    async def hide(self, ctx):
        squad = self.data["squadrons"].get(str(ctx.channel.id))
        if not squad or not self.is_mod_or_owner(ctx, squad): return
        squad["is_hidden"] = True
        self.save_data(self.data)
        await self.update_permissions(ctx.channel, hide=True)
        await ctx.send("🔒 **Hidden.**")

    @commands.command()
    async def unhide(self, ctx):
        squad = self.data["squadrons"].get(str(ctx.channel.id))
        if not squad or not self.is_mod_or_owner(ctx, squad): return
        squad["is_hidden"] = False
        self.save_data(self.data)
        await self.update_permissions(ctx.channel, hide=False)
        await ctx.send("🔓 **Visible.**")

    @commands.command(aliases=["changeowner"])
    async def transferowner(self, ctx, new_owner: discord.Member):
        squad = self.data["squadrons"].get(str(ctx.channel.id))
        if not squad or not self.is_mod_or_owner(ctx, squad):
            return await ctx.send("❌ Access denied.")

        old_owner_id = squad["owner_id"]
        squad["owner_id"] = new_owner.id
        if old_owner_id not in squad["members"]:
            squad["members"].append(old_owner_id)
        if new_owner.id in squad["members"]:
            squad["members"].remove(new_owner.id)

        self.save_data(self.data)
        await self.update_permissions(ctx.channel, hide=True)
        await ctx.send(f"👑 Ownership transferred to {new_owner.mention}!")

    @commands.command()
    async def squadonly(self, ctx, toggle: str):
        """Toggles Squad-Only Mode (Always Hidden). Usage: ?squadonly on/off"""
        squad = self.data["squadrons"].get(str(ctx.channel.id))
        
        # 1. Permission Check
        if not squad or not self.is_mod_or_owner(ctx, squad):
            return await ctx.send("❌ Access denied. This must be a squadron channel and you must be the owner/mod.")

        # 2. Logic to determine True/False
        if toggle.lower() in ["on", "yes", "true"]:
            state = True
        elif toggle.lower() in ["off", "no", "false"]:
            state = False
        else:
            return await ctx.send("❓ Invalid input! Please use `?squadonly on` or `?squadonly off`.")

        # 3. Save and Update
        squad["squad_only_mode"] = state
        self.save_data(self.data)
        
        # If toggling ON, hide the channel immediately. 
        # If toggling OFF, we leave it as is (it will unhide on next event or via ?unhide)
        if state:
            await self.update_permissions(ctx.channel, hide=True)
            await ctx.send("🔒 **Squad-Only Mode: ON**. This channel will now remain hidden even during events.")
        else:
            await ctx.send("🔓 **Squad-Only Mode: OFF**. This channel will now unhide automatically when RPG events start.")

    # --- ERROR HANDLER FOR SQUADONLY ---
    @squadonly.error
    async def squadonly_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            prefix = self.bot.command_prefix
            await ctx.send(
                f"❌ **Missing Argument!**\n"
                f"Usage: `{prefix}squadonly <on/off>`\n"
                f"Example: `{prefix}squadonly on` to keep the channel private at all times."
            )
    @commands.command()
    async def rename(self, ctx, *, new_name: str):
        squad = self.data["squadrons"].get(str(ctx.channel.id))
        if not squad or not self.is_mod_or_owner(ctx, squad):
            return await ctx.send("❌ Access denied.")

        await ctx.channel.edit(name=new_name)
        await ctx.send(f"📝 Channel renamed to `{new_name}`.")

    @commands.command()
    async def allow(self, ctx, member: discord.Member):
        squad = self.data["squadrons"].get(str(ctx.channel.id))
        if not squad or not self.is_mod_or_owner(ctx, squad): return
        if member.id not in squad["members"]:
            squad["members"].append(member.id)
            self.save_data(self.data)
            await self.update_permissions(ctx.channel, hide=True)
            await ctx.send(f"✅ {member.mention} added.")

    @commands.command()
    async def deny(self, ctx, member: discord.Member):
        squad = self.data["squadrons"].get(str(ctx.channel.id))
        if not squad or not self.is_mod_or_owner(ctx, squad): return
        if member.id in squad["members"]:
            squad["members"].remove(member.id)
            self.save_data(self.data)
            await ctx.channel.set_permissions(member, overwrite=None)
            await ctx.send(f"❌ {member.mention} removed.")
            
    @commands.command()
    async def eventson(self, ctx):
        squad = self.data["squadrons"].get(str(ctx.channel.id))
        if squad:
            squad["events_enabled"] = True
            self.save_data(self.data)
            await ctx.send("🔔 Events enabled (Channel will unhide).")

    @commands.command()
    async def eventsoff(self, ctx):
        squad = self.data["squadrons"].get(str(ctx.channel.id))
        if squad:
            squad["events_enabled"] = False
            self.save_data(self.data)
            await ctx.send("🔕 Events disabled (Pings only, no unhide).")

async def setup(bot):
    # We pull the data directly from the bot instance
    await bot.add_cog(SquadronManager(bot, bot.squad_data, bot.save_data))