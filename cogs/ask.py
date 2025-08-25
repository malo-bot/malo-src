import discord
from discord import app_commands
import asyncio
import yaml
import openai
from collections import defaultdict, deque
with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)
from datetime import datetime
error_emoji = config["error"]
raw_color = config["error_accent"]
if isinstance(raw_color, str):
    accent = int(raw_color.lstrip("#"), 16)
else:
    accent = int(raw_color)
def create_error_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(
        title=f"{error_emoji} {title}",
        description=description,
        color=accent
    )

system_message = config['openai']['system_message']

openai_client = openai.AsyncOpenAI(
    api_key=config['openai']['api_key'],
    base_url=config['openai']['base_url']
)
model = config['openai']['model']

async def setup(bot):
    chat_history = defaultdict(lambda: deque(maxlen=8)) # halved by two. 8 = 4 exchanges. Change this if you want the bot to remember more than 4 messages.
    @app_commands.command(
        name="ask",
        description="Query qwen3:1.7b"
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def ask_command(interaction: discord.Interaction, prompt: str):
        await interaction.response.send_message("🧡 Reasoning...")

        try:
            user_id = interaction.user.id

            # add the new user message
            chat_history[user_id].append({"role": "user", "content": prompt})

            # build messages: system prompt + history
            messages = [
                {"role": "system", "content": system_message + "Current date and time: " + datetime.now().strftime("%B %d, %Y at %I:%M %p")}
            ]
            messages.extend(chat_history[user_id])

            # query model
            response = await openai_client.chat.completions.create(
                model=model,
                messages=messages
            )

            ai_response = response.choices[0].message.content
            final_content = ai_response.split("</think>")[-1].strip() if "</think>" in ai_response else ai_response

            # save assistant reply in history
            chat_history[user_id].append({"role": "assistant", "content": final_content})

            # edit the "reasoning" message with the reply
            await interaction.edit_original_response(content=final_content[:2000])

        except Exception as e:
            embed = create_error_embed("Error while calling function", f"```{str(e)}```")
            await interaction.edit_original_response(embed=embed)
            print(f"Error in ask command: {e}")

            
    bot.tree.add_command(ask_command)