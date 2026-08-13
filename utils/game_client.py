#################################################################
# game_client.py                                                #
# Client for interacting with game servers (e.g. Minecraft)     #
#################################################################

import logging
from mcstatus import JavaServer

logger = logging.getLogger("game_client")

# --- Minecraft (JAVA) ---
async def get_minecraft_status(ip: str, port: int) -> dict:
    # Returns a dict with "online", "players_online", "players_max"
    try:
        # mcstatus JavaServer supports standard Java ping
        server = JavaServer.lookup(f"{ip}:{port}")
        # Using a timeout so it doesnt block too long if offline
        status = await server.async_status()
        return {
            "online": True,
            "players_online": status.players.online,
            "players_max": status.players.max,
        }
    except Exception as e:
        # This is expected if the server is offline or still starting
        # TODO: set this to 0 once multi egg support is implemented, it's at 1 now
        # so if a non-mc server is running, it won't randomly turn off with players online
        logger.debug(f"Failed to query Minecraft server {ip}:{port} - {e}")
        return {
            "online": False,
            "players_online": 1,
            "players_max": 1,
        }

# --- TODO: Add support for other game eggs ---
