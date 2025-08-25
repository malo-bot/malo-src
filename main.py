import discord
from discord.ext import commands
from discord import app_commands
import yaml
import os

with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

intents = discord.Intents.default()
intents.message_content = True

class Katya(commands.Bot):
    def __init__(self, *args, **kwargs):
        # fix contexts /make the bot usable everywhere .
        super().__init__(
            *args,
            allowed_installs=app_commands.AppInstallationType(
                guild=True, user=True
            ),
            allowed_contexts=app_commands.AppCommandContext(
                guild=True, dm_channel=True, private_channel=True
            ),
            **kwargs
        )

    async def setup_hook(self):
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py") and filename != "__init__.py" and not filename.startswith("KatyaCog"):
                cog_name = f"cogs.{filename[:-3]}"
                try:
                    await self.load_extension(cog_name)
                    print(f"[INFO] Loaded cog: {cog_name}")
                except Exception as e:
                    print(f"[ERROR] Failed to load {cog_name}: {e}")

        try:
            synced = await self.tree.sync()
            print(f"\n[INFO] Synced {len(synced)} commands")
            for cmd in synced:
                print(f"  -> /{cmd.name} | {cmd.description}")
        except Exception as e:
            print(f"[ERROR] Failed to sync: {e}")
            
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        raw_color = self.config.get("accent", "#ff8040")
        color = int(raw_color.lstrip("#"), 16) if isinstance(raw_color, str) else int(raw_color)
        emoji = self.config.get("error")
        
        if isinstance(error, app_commands.MissingPermissions):
            embed = discord.Embed(
                title=f"{emoji} Missing Permissions",
                description="You don't have the required permissions to use this command.",
                color=color
            )
        elif isinstance(error, app_commands.BotMissingPermissions):
            embed = discord.Embed(
                title=f"{emoji} Bot Missing Permissions",
                description="I don't have the required permissions to execute this command.",
                color=color
            )
        elif isinstance(error, app_commands.CommandOnCooldown):
            embed = discord.Embed(
                title=f"{emoji} Command On Cooldown",
                description=f"Please wait {error.retry_after:.2f} seconds before using this command again.",
                color=color
            )
        else:
            print(f"Unhandled error in command {interaction.command.name}: {error}")
            embed = discord.Embed(
                title=f"{emoji} Unexpected Error",
                description=f"An unexpected error occurred: \n ```{error}```",
                color=color
            )
        
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

bot = Katya(command_prefix=config["prefix"], intents=intents)
bot.config = config

@bot.event
async def on_ready():
    print(f"[INFO] Logged in as {bot.user}")
    print(f"[EXTRA] User install URL: https://discord.com/oauth2/authorize?client_id={bot.user.id}&integration_type=1&scope=applications.commands")
    print(f"[EXTRA] Guild install URL: https://discord.com/oauth2/authorize?client_id={bot.user.id}&permissions=1126314438683712&integration_type=0&scope=bot")

    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name="you~"
    )
    await bot.change_presence(status=discord.Status.dnd, activity=activity)
    print(f"[INFO] Activity set.")

# Run
bot.run(config["token"])
