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
        self.cogslist = {"squadrons", "events", "help", "config"}
        
        # --- ATTACH DATA TO CLIENT ---
        self.data_file = DATA_FILE
        self.squad_data = self.load_data()

    def load_data(self):
        if os.path.exists(self.data_file):
            with open(self.data_file, "r") as f:
                return json.load(f)
        return {"server_configs": {"global": {}}, "squadrons": {}}
    
    def reload_data(self):
        """Reloads the JSON file back into the bot's memory."""
        self.squad_data = self.load_data()
        return self.squad_data

    def save_data(self, data=None):
        # If no data passed, save the internal squad_data
        to_save = data if data is not None else self.squad_data
        with open(self.data_file, "w") as f:
            json.dump(to_save, f, indent=4)

    async def setup_hook(self):
        initial_extensions = ["cogs.squadrons", "cogs.events", "cogs.help", "cogs.config"]
        for ext in self.cogslist:
            await self.load_extension(f"cogs.{ext}")
        print(f"📂 Loaded: {', '.join(initial_extensions)}")

    async def on_ready(self):
        print(f"✅ Logged in as {self.user.name}")
    
client = Bot()

@client.command(hidden=True)
@commands.is_owner() 
async def reload(ctx, extension: str):
    """Reloads a specific cog. Usage: ?reload squadrons"""
    try:
        # We ensure it's lowercase and prefixed with 'cogs.'
        await client.reload_extension(f"cogs.{extension.lower()}")
        await ctx.send(f"✅ Successfully reloaded: 📂`cogs.{extension.lower()}`")
    except commands.ExtensionNotLoaded:
        await ctx.send(f"❌ Cog `cogs.{extension}` wasn't even loaded! Try `?load` instead.")
    except Exception as e:
        await ctx.send(f"❌ Error: `{e}`")

@client.command()
@commands.is_owner()
async def reloadjson(ctx):
    """Force reloads the JSON file without restarting the bot."""
    client.reload_data()
    await ctx.send(f"🔄 Data from `{DATA_FILE}` has been re-synced to the bot!")

@client.command(hidden=True)
@commands.has_permissions(administrator=True)
async def reloadall(ctx):
    """Reloads all active cogs."""
    extensions = ["squadrons", "events", "help", "config"] 
    results = []
    for ext in extensions:
        try:
            await client.reload_extension(f"cogs.{ext}")
            """Force reloads the JSON file without restarting the bot."""
            client.reload_data()
            await ctx.send(f"🔄 Data from `{DATA_FILE}` has been re-synced to the bot!")
            results.append(f"✅ {ext}")
        except Exception as e:
            results.append(f"❌ {ext} (Error: {e})")
    
    await ctx.send("**Cog Reload Status:**\n" + "\n".join(results))


client.run(TOKEN)