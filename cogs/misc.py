import discord
from discord import app_commands
from discord.ext import commands
import platform
import psutil
from datetime import datetime
import subprocess
import cpuinfo
from .KatyaCog import KatyaCog  # import base cog

launch_time = datetime.now()

class Misc(KatyaCog):  # inherit from KatyaCog
    def __init__(self, bot):
        super().__init__(bot)
    misc = app_commands.Group(name="misc", description="Misc.")

    @misc.command(name="ping", description="Check the bot's latency")
    async def ping(self, interaction: discord.Interaction):
        latency_ms = round(self.bot.latency * 1000)  # convert to ms
        embed = discord.Embed(
            title="Latency:",
            description=f"`{latency_ms}ms`",
            colour=self.accent,
            timestamp=datetime.now()
        )
        embed.set_author(name="Pong!")
        embed.set_footer(text=self.emoji)
        await interaction.response.send_message(embed=embed)

    @misc.command(name="clear", description="pseudo-clears chat")
    async def leakprotext(self, interaction: discord.Interaction):
        try:
            await interaction.response.send_message(
                ":3\n\n" + ("\n" * 70) + f"{self.emoji} Done"
            )
        except Exception as e:
            print(f"Error occurred: {str(e)}")

    @misc.command(name="info", description="System info")
    async def info(self, interaction: discord.Interaction):
        await interaction.response.defer()
        uptime = datetime.now() - launch_time

        system = platform.system()
        release = platform.release()
        version = platform.version()
        cpu = cpuinfo.get_cpu_info().get("brand_raw", platform.processor())
        memory = psutil.virtual_memory()
        memory_usage = f"{memory.used // (1024**2)} MB / {memory.total // (1024**2)} MB"
        python_version = platform.python_version()

        cpu_usage = f"{psutil.cpu_percent()}% ({psutil.cpu_count()} cores)"
        disk_usage = psutil.disk_usage('/')
        disk_usage_str = f"{disk_usage.used // (1024**3)} GB / {disk_usage.total // (1024**3)} GB"
        latency = f"{self.bot.latency * 1000:.2f} ms"

        cpufreq = psutil.cpu_freq()
        cpu_freq = f"{cpufreq.current:.2f} MHz" if cpufreq else "N/A"

        shard_info = f"{interaction.guild.shard_id if interaction.guild else 0} / {self.bot.shard_count}"

        # nvidia specific
        try:
            output = subprocess.check_output([
                'nvidia-smi',
                '--query-gpu=name,memory.used,memory.total',
                '--format=csv,noheader,nounits'
            ]).decode('utf-8')
            gpu_name, gpu_used, gpu_total = output.strip().split(', ')
            gpu_info = f"{gpu_name}\n{int(gpu_used)} MB / {int(gpu_total)} MB"
        except Exception:
            gpu_info = "Not available"

        embed = discord.Embed(
            title="System & Bot Info",
            colour=self.accent,
            timestamp=datetime.utcnow()
        )

        # Organize fields
        embed.add_field(name="OS", value=f"{system} {release}\n{version}", inline=False)
        embed.add_field(name="Python", value=python_version, inline=True)
        embed.add_field(name="Uptime", value=str(uptime).split('.')[0], inline=True)
        embed.add_field(name="RAM", value=memory_usage, inline=True)
        embed.add_field(name="CPU", value=cpu_usage, inline=True)
        embed.add_field(name="Disk", value=disk_usage_str, inline=True)
        embed.add_field(name="Latency", value=latency, inline=True)
        embed.add_field(name="CPU Name", value=cpu, inline=False)
        embed.add_field(name="CPU Freq", value=cpu_freq, inline=True)
        embed.add_field(name="Shard", value=shard_info, inline=True)
        embed.add_field(name="GPU", value=gpu_info, inline=False)

        embed.set_footer(text=self.emoji)
        await interaction.edit_original_response(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Misc(bot))
