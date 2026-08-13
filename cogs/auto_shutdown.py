#################################################################
# auto_shutdown.py                                              #
# Background task to monitor and auto-shutdown idle servers     #
#################################################################

import logging
from datetime import datetime, timezone, timedelta
from discord.ext import tasks, commands
from config import ENABLE_AUTO_SHUTDOWN, SERVER_IDLE_SHUTDOWN_MINUTES, NODE_IDLE_SHUTDOWN_MINUTES, NODE2_PTERO_ID
from utils.ptero_client import ptero
from utils.game_client import get_minecraft_status
from utils.power_manager import shutdown_node2
import utils.power_manager as power_manager

logger = logging.getLogger("auto_shutdown")

class AutoShutdown(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Track when a server first had 0 players (identifier -> datetime)
        self.server_idle_since = {}
        # Track when Node 2 first had 0 active servers (datetime)
        self.node_idle_since = None
        
        if ENABLE_AUTO_SHUTDOWN:
            self.shutdown_loop.start()
        else:
            logger.info("Auto-shutdown feature is disabled in config.")

    def cog_unload(self):
        if self.shutdown_loop.is_running():
            self.shutdown_loop.cancel()

    @tasks.loop(minutes=5.0)
    async def shutdown_loop(self):
        # If Node 2 is currently processing a command, skip auto-shutdown loop and wait for the next cycle
        if power_manager.is_node2_processing:
            logger.info("Node is currently processing a command, skipping auto-shutdown check.")
            return

        logger.info("Running auto-shutdown check...")
        
        # 1. Fetch all servers on Node 2
        servers = await ptero.get_node_servers(NODE2_PTERO_ID)
        
        # If servers is empty (no servers on the node), the loop below will just skip and hardware idle logic will trigger
        if servers is None:
            logger.error(f"API Error while fetching servers for Node {NODE2_PTERO_ID}.")
            return

        active_servers_count = 0
        
        for server in servers:
            identifier = server.get("identifier")
            if not identifier:
                continue

            # 2. Get server real-time status
            status = await ptero.get_server_status(identifier)
            if status is None:
                continue
                
            # 3. Check if active for hardware timer purposes
            # "starting", "running", "stopping" are considered active
            if status in ["starting", "running", "stopping"]:
                active_servers_count += 1
            
            # 4. Server Idle Logic (only for "running" servers)
            if status == "running":
                # Get IP and Port from the pre-fetched allocations
                allocations = server.get("relationships", {}).get("allocations", {}).get("data", [])
                primary_id = server.get("allocation")
                primary_allocation = next((a for a in allocations if a.get("attributes", {}).get("id") == primary_id), None)
                
                ip = ""
                port = 0
                if primary_allocation:
                    ip = primary_allocation["attributes"].get("alias") or primary_allocation["attributes"].get("ip")
                    port = primary_allocation["attributes"].get("port")
                
                if ip and port:
                    # TODO: Currently hardcoded to Minecraft. In the future, fetch the server's
                    # Egg ID (e.g. from the details API) and dynamically route to the correct
                    # game client (Minecraft, Hytale, 7DtD, etc.) based on the Egg ID
                    mc_status = await get_minecraft_status(ip, port)
                    
                    if mc_status["players_online"] == 0:
                        # Server is empty
                        if identifier not in self.server_idle_since:
                            self.server_idle_since[identifier] = datetime.now(timezone.utc)
                            logger.info(f"Server {identifier} is empty. Started idle timer.")
                        else:
                            # Check how long it has been empty
                            idle_time = datetime.now(timezone.utc) - self.server_idle_since[identifier]
                            if idle_time >= timedelta(minutes=SERVER_IDLE_SHUTDOWN_MINUTES):
                                logger.info(f"Server {identifier} has been empty for >= {SERVER_IDLE_SHUTDOWN_MINUTES} mins. Sending STOP signal.")
                                await ptero.send_power_action(identifier, "stop")
                                # Remove from tracking to prevent spamming stop commands
                                del self.server_idle_since[identifier]
                    else:
                        # Players are online, reset timer if it was tracking
                        if identifier in self.server_idle_since:
                            logger.info(f"Players joined server {identifier}. Resetting idle timer.")
                            del self.server_idle_since[identifier]
            else:
                # If server is not running, remove it from tracking for idle shutdown
                if identifier in self.server_idle_since:
                    del self.server_idle_since[identifier]

        # 5. Hardware Idle Logic
        if active_servers_count == 0:
            if self.node_idle_since is None:
                self.node_idle_since = datetime.now(timezone.utc)
                logger.info(f"All servers on Node {NODE2_PTERO_ID} are offline. Started hardware idle timer.")
            else:
                idle_time = datetime.now(timezone.utc) - self.node_idle_since
                if idle_time >= timedelta(minutes=NODE_IDLE_SHUTDOWN_MINUTES):
                    logger.info(f"Node {NODE2_PTERO_ID} has had 0 active servers for >= {NODE_IDLE_SHUTDOWN_MINUTES} mins. Initiating hardware shutdown.")
                    await shutdown_node2()
                    # Reset node timer to prevent spamming shutdown commands
                    self.node_idle_since = None
        else:
            if self.node_idle_since is not None:
                logger.info(f"Active servers detected on Node {NODE2_PTERO_ID}. Resetting hardware idle timer.")
                self.node_idle_since = None

    @shutdown_loop.before_loop
    async def before_shutdown_loop(self):
        await self.bot.wait_until_ready()
        logger.info("Starting auto-shutdown loop...")

async def setup(bot):
    await bot.add_cog(AutoShutdown(bot))
