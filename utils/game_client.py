#################################################################
# game_client.py                                                #
# Client for querying game servers (Minecraft, Steam A2S, etc.) #
#################################################################

import asyncio
import logging
from mcstatus import JavaServer
from little_a2s import AsyncA2S
from config import NODE2_IP, EGG_PROTOCOL_MAP

logger = logging.getLogger("game_client")

# --- Protocol Detection ---
# Keywords used to automatically detect the query protocol from the Egg or Nest name
# These are checked case-insensitively against the Egg name and Nest name from Pterodactyl
MINECRAFT_KEYWORDS = [
    "minecraft", "paper", "spigot", "purpur", "forge", "fabric",
    "bungeecord", "velocity", "waterfall", "sponge", "mohist",
]
A2S_KEYWORDS = [
    "vein", "7 days", "7dtd", "valheim", "palworld", "rust",
    "ark", "steam", "source", "squad", "insurgency", "unturned",
    "satisfactory", "enshrouded", "conan",
]

# Cache for discovered A2S query ports (identifier -> port)
_query_port_cache: dict[str, int] = {}


# Detects query protocol (minecraft, a2s, unknown) via config override or egg keywords
def detect_protocol(server: dict) -> str:
    egg_id = server.get("egg")

    # Check manual override first (always takes priority)
    if egg_id and egg_id in EGG_PROTOCOL_MAP:
        proto = EGG_PROTOCOL_MAP[egg_id]
        logger.debug(f"Protocol for '{server.get('name')}' resolved via config override: {proto}")
        return proto

    # Gather the egg name and nest name for keyword matching
    egg_rel = server.get("relationships", {}).get("egg", {})
    egg_name = egg_rel.get("attributes", {}).get("name", "")
    nest_rel = server.get("relationships", {}).get("nest", {})
    nest_name = nest_rel.get("attributes", {}).get("name", "") or str(egg_rel.get("attributes", {}).get("nest", ""))
    # Use server name as a last resort for matching
    server_name = server.get("name", "")

    searchable = f"{egg_name} {nest_name} {server_name}".lower()

    for keyword in MINECRAFT_KEYWORDS:
        if keyword in searchable:
            return "minecraft"

    for keyword in A2S_KEYWORDS:
        if keyword in searchable:
            return "a2s"

    # Unknown protocol, can't query this server
    logger.warning(
        f"Server '{server_name}' (Egg ID: {egg_id}, Egg: '{egg_name}') could not be matched to any game protocol. "
        f"Set EGG_PROTOCOL_MAP = {{{egg_id}: 'a2s'}} in config.py if this is a Steam/A2S server."
    )
    return "unknown"


# Resolves query IP, falling back to NODE2_IP for local/bind addresses
def _resolve_query_ip(ip: str) -> str:
    if ip in ("0.0.0.0", "127.0.0.1", "localhost", ""):
        return NODE2_IP
    return ip


# Builds candidate ports to try for A2S queries (secondary allocations, 27015, primary + 1/+2)
def _find_query_port_candidates(server: dict, primary_port: int) -> list[int]:
    candidates = []

    # If primary port is 27015, it's very likely the query port
    if primary_port == 27015:
        candidates.append(27015)

    # Collect all allocated secondary ports (assigned to this container in Pterodactyl)
    allocations = server.get("relationships", {}).get("allocations", {}).get("data", [])
    primary_id = server.get("allocation")

    for alloc in allocations:
        alloc_id = alloc.get("attributes", {}).get("id")
        alloc_port = alloc.get("attributes", {}).get("port")
        if alloc_id != primary_id and alloc_port and alloc_port not in candidates:
            candidates.append(alloc_port)

    # Common query port fallbacks (27015 is default for Steam/VEIN, primary+1 / +2 for others)
    fallbacks = [27015, primary_port + 1, primary_port + 2]
    for fb in fallbacks:
        if fb not in candidates and fb != primary_port:
            candidates.append(fb)

    # Last resort: try the primary port itself
    if primary_port not in candidates:
        candidates.append(primary_port)

    return candidates


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
        logger.debug(f"Failed to query Minecraft server {ip}:{port} - {e}")
        return {
            "online": False,
            "players_online": 0,
            "players_max": 0,
        }


# --- Steam / Valve A2S (VEIN, Valheim, 7DtD, etc.) ---
async def get_a2s_status(ip: str, primary_port: int, server: dict) -> dict:
    # Returns a dict with "online", "players_online", "players_max"
    identifier = server.get("identifier", "")
    server_name = server.get("name", identifier)

    # Check if the query port is already known/cached
    cached_port = _query_port_cache.get(identifier)
    if cached_port:
        result = await _try_a2s_query(ip, cached_port)
        if result:
            return result
        # Cache miss (port may have changed), clear and re-discover
        del _query_port_cache[identifier]

    # Try all candidate ports in order
    candidates = _find_query_port_candidates(server, primary_port)
    for port in candidates:
        result = await _try_a2s_query(ip, port)
        if result:
            # Cache the working port for future queries
            _query_port_cache[identifier] = port
            logger.info(f"A2S query successful for '{server_name}' on {ip}:{port} ({result['players_online']}/{result['players_max']} players)")
            return result

    logger.warning(
        f"Failed to query A2S server '{server_name}' on {ip} (tried ports: {candidates}). "
        f"Ensure the query port (usually 27015 or {primary_port + 1}) is assigned as an allocation in Pterodactyl."
    )
    return {
        "online": False,
        "players_online": 0,
        "players_max": 0,
    }


# Attempts a single A2S query on the given IP and port, returns None on failure
async def _try_a2s_query(ip: str, port: int) -> dict | None:
    try:
        async with AsyncA2S.from_ipv4() as a2s:
            async with asyncio.timeout(2.5):
                info = await a2s.info((ip, port))
                return {
                    "online": True,
                    "players_online": info.players,
                    "players_max": info.max_players,
                }
    except TimeoutError:
        logger.debug(f"A2S query to {ip}:{port} timed out (no response within 2.5s)")
        return None
    except Exception as e:
        logger.debug(f"A2S query to {ip}:{port} failed: {type(e).__name__} - {e}")
        return None


# --- Central Entry Point ---
# Queries any game server for player status, auto-detects protocol and query port
async def get_server_game_status(server: dict) -> dict:
    # Returns a dict with "online", "players_online", "players_max", "protocol"
    protocol = detect_protocol(server)

    # If protocol is explicitly set to "none" or unknown, skip querying
    if protocol in ("none", "unknown"):
        return {
            "online": False,
            "players_online": 0,
            "players_max": 0,
            "protocol": protocol,
        }

    # Get IP and Port from the pre-fetched allocations
    allocations = server.get("relationships", {}).get("allocations", {}).get("data", [])
    primary_id = server.get("allocation")
    primary_allocation = next(
        (a for a in allocations if a.get("attributes", {}).get("id") == primary_id), None
    )

    if not primary_allocation:
        return {
            "online": False,
            "players_online": 0,
            "players_max": 0,
            "protocol": protocol,
        }

    # Use raw IP for game queries (aliases may not be resolvable)
    raw_ip = primary_allocation["attributes"].get("ip", "")
    port = primary_allocation["attributes"].get("port", 0)
    ip = _resolve_query_ip(raw_ip)

    if not ip or not port:
        return {
            "online": False,
            "players_online": 0,
            "players_max": 0,
            "protocol": protocol,
        }

    # Route to the correct game client
    if protocol == "minecraft":
        result = await get_minecraft_status(ip, port)
    elif protocol == "a2s":
        result = await get_a2s_status(ip, port, server)
    else:
        result = {"online": False, "players_online": 0, "players_max": 0}

    result["protocol"] = protocol
    return result
