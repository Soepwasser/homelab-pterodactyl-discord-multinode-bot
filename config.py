#################################################################
# config.py                                                     #
# Centralised configuration, reads from .env via python-dotenv  #
#################################################################

import os
from dotenv import load_dotenv

load_dotenv()

# --- Discord ---
DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
PERMITTED_USER_ROLE_ID: int      = int(os.getenv("PERMITTED_USER_ROLE_ID", "0"))

# --- Node 1 ---
# ----- Pterodactyl -----
PTERO_PANEL_URL: str        = os.getenv("PTERO_PANEL_URL", "").rstrip("/")

PTERO_API_KEY: str    = os.getenv("PTERO_API_KEY", "")
PTERO_CLIENT_KEY: str = os.getenv("PTERO_CLIENT_KEY", "")

# --- Node 2 ---
# ----- Hardware & Power Management -----
NODE2_MAC: str          = os.getenv("NODE2_MAC", "")
NODE2_IP: str           = os.getenv("NODE2_IP", "")
NODE2_SSH_USER: str     = os.getenv("NODE2_SSH_USER", "bot-admin")
NODE2_SSH_KEY_PATH: str = os.path.expanduser(os.getenv("NODE2_SSH_KEY_PATH", "~/.ssh/id_ed25519"))
# ----- Pterodactyl -----
NODE2_PTERO_ID: int     = int(os.getenv("NODE2_PTERO_ID", "2"))

# Validate that all essential config vars are set, if not, error and abort
def validate_config():
    missing = []
    
    # Discord
    if not DISCORD_TOKEN: missing.append("DISCORD_TOKEN")
    if not PERMITTED_USER_ROLE_ID: missing.append("PERMITTED_USER_ROLE_ID")
    
    # Pterodactyl
    if not PTERO_PANEL_URL: missing.append("PTERO_PANEL_URL")
    if not PTERO_API_KEY: missing.append("PTERO_API_KEY")
    if not PTERO_CLIENT_KEY: missing.append("PTERO_CLIENT_KEY")
    
    # Node 2 Hardware
    if not NODE2_MAC: missing.append("NODE2_MAC")
    if not NODE2_IP: missing.append("NODE2_IP")
    if not NODE2_SSH_USER: missing.append("NODE2_SSH_USER")
    if not NODE2_SSH_KEY_PATH: missing.append("NODE2_SSH_KEY_PATH")
    if not NODE2_PTERO_ID: missing.append("NODE2_PTERO_ID")
    
    if missing:
        raise ValueError(f"Missing essential configuration variables: {', '.join(missing)}")

# Defines how many servers are fetched in one API request. Increase if there are more than 50 servers in total.
PTERO_SERVER_FETCH_LIMIT: int = 50

# --- Auto-Shutdown Settings ---
ENABLE_AUTO_SHUTDOWN: bool = True
SERVER_IDLE_SHUTDOWN_MINUTES: int = 60
NODE_IDLE_SHUTDOWN_MINUTES: int = 120

# --- Meta ---
BOT_NAME    = "Pterodactyl Multinode Bot"
BOT_VERSION = "1.0.0"
