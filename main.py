import discord
from discord.ext import commands
import json
import os
from dotenv import load_dotenv
from cogs.help import CustomHelp

load_dotenv()
TOKEN = os.getenv("TOKEN")
DATA_FILE = "squadrons_data.json"

class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True 
        intents.guilds = True
        
        super().__init__(command_prefix='?', intents=intents, help_command=CustomHelp())
        
        # --- SINGLE SOURCE OF TRUTH ---
        self.cogslist = [
            "squadrons",
            "events",
            "help", 
            "config",
            "listeners",
            "check_trades", 
            #"calculator"
        ]
        
        self.data_file = DATA_FILE
        self.squad_data = self.load_data()

    def load_data(self):
        if os.path.exists(self.data_file):
            with open(self.data_file, "r") as f:
                data = json.load(f)
            
            changes_made = False
            for squad_id, info in data.get("squadrons", {}).items():
                if "is_hidden" not in info:
                    info["is_hidden"] = True
                    changes_made = True
            
            if changes_made:
                self.save_data(data)
                print("🛠️ Fixed missing 'is_hidden' keys in JSON.")
                
            return data
        return {"server_configs": {"global": {}}, "squadrons": {}}
    
    def reload_data(self):
        self.squad_data = self.load_data()
        return self.squad_data

    def save_data(self, data=None):
        to_save = data if data is not None else self.squad_data
        with open(self.data_file, "w") as f:
            json.dump(to_save, f, indent=4)

    async def setup_hook(self):
        # Loops through the single list defined in __init__
        for ext in self.cogslist:
            await self.load_extension(f"cogs.{ext}")
        print(f"📂 Loaded {len(self.cogslist)} extensions: {', '.join(self.cogslist)}")

    async def on_ready(self):
        print(f"✅ Logged in as {self.user.name}")
    
client = Bot()

@client.command(hidden=True)
@commands.is_owner() 
async def reload(ctx, extension: str):
    """Reloads a specific cog."""
    try:
        await client.reload_extension(f"cogs.{extension.lower()}")
        await ctx.send(f"✅ Successfully reloaded: 📂`cogs.{extension.lower()}`")
    except Exception as e:
        await ctx.send(f"❌ Error: `{e}`")

@client.command()
@commands.is_owner()
async def reloadjson(ctx):
    """Force reloads the JSON file."""
    client.reload_data()
    await ctx.send(f"🔄 Data from `{DATA_FILE}` has been re-synced!")

@client.command(hidden=True)
@commands.has_permissions(administrator=True)
async def reloadall(ctx):
    """Reloads all cogs using the central list."""
    results = []
    # Pulls from the list inside the bot class
    for ext in client.cogslist:
        try:
            await client.reload_extension(f"cogs.{ext}")
            results.append(f"✅ {ext}")
        except Exception as e:
            results.append(f"❌ {ext} ({e})")
    
    client.reload_data()
    status_msg = "\n".join(results)
    await ctx.send(f"🔄 Data re-synced!\n**Cog Reload Status:**\n{status_msg}")

client.run(TOKEN)