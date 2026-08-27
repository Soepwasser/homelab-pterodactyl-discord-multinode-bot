#####################
# main.py           #
#####################

import asyncio
import logging
import discord
from discord.ext import commands
from config import DISCORD_TOKEN, BOT_NAME, BOT_VERSION, validate_config

# logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("bot")

class PteroBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!", 
            intents=discord.Intents.default(),
            help_command=None
        )

    async def setup_hook(self):
        await self.load_extension("cogs.auto_shutdown")
        await self.load_extension("cogs.dashboard")
        await self.tree.sync()

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"{BOT_NAME} v{BOT_VERSION} is ready and running!")

        await self.change_presence(
            activity=discord.Game(name="moin")
        )

async def main():
    # 1. Validate configuration, abort if invalid
    try:
        validate_config()
        logger.info("Configuration validated successfully.")
    except ValueError as e:
        logger.critical(f"Configuration error: {e}")
        return

    # 2. Start the bot
    bot = PteroBot()
    async with bot:
        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
