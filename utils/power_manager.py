#################################################################
# power_manager.py                                              #
# Handles hardware-level power state (WoL, SSH Shutdown, Ping)  #
#################################################################

import asyncio
import asyncssh
import wakeonlan
import logging
from config import NODE2_MAC, NODE2_IP, NODE2_SSH_USER, NODE2_SSH_KEY_PATH

logger = logging.getLogger("power_manager")

# Global lock to indicate that a start/stop/restart/kill command is currently running (prevents race conditions)
is_node2_processing = False

# Checks if Node 2 is online by attempting to connect to its SSH port (22)
async def is_node2_online() -> bool:
    try:
        # Try to open a connection to port 22 with a 3-second timeout
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(NODE2_IP, 22), 
            timeout=3.0
        )
        writer.close()
        await writer.wait_closed()
        return True
    except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
        return False

# Sends a Wake-on-LAN Magic Packet to Node 2's MAC address
def wake_node2():
    logger.info(f"Sending WoL Magic Packet to {NODE2_MAC}")
    wakeonlan.send_magic_packet(NODE2_MAC)

# Connects to Node 2 via SSH and issues the poweroff command
async def shutdown_node2() -> bool:
    logger.info(f"Attempting SSH shutdown on {NODE2_IP} as {NODE2_SSH_USER}")
    
    try:
        async with asyncssh.connect(
            NODE2_IP,
            username=NODE2_SSH_USER,
            client_keys=[NODE2_SSH_KEY_PATH],
            known_hosts=None  # Disable known_hosts check for simplicity (cuz homelab)
        ) as conn:
            result = await conn.run('sudo /sbin/shutdown -h now', check=False)
            
            if result.exit_status == 0 or result.exit_status == -1: # -1 sometimes returned if connection drops on poweroff
                logger.info("Shutdown command sent successfully.")
                return True
            else:
                logger.error(f"Failed to shutdown: {result.stderr}")
                return False
                
    except Exception as e:
        logger.error(f"SSH shutdown failed: {e}")
        return False
