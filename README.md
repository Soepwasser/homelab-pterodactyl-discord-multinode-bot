# Pterodactyl Multinode Discord Bot

## Project Context
A Discord Bot to manage Ptereodactyl servers on a multinode setup.
- **Node 1 (Infrastructure):** Runs 24/7 (Proxmox, Pterodactyl Panel).
- **Node 2 (Game Servers):** Game server node (Wings, Game Servers). Turned on on demand to minimize power consumption.

## Features
- NOTHING :(

## Vision / Roadmap
- **Discord Embedded Message-Dashboard**: Dashboard with buttons to monitor and control servers (start/stop/restart/show Server-IP)
- **Hardware Control:** Integration of Wake-on-LAN (WoL) to remotely boot Node 2 when a game server is started via Discord.
- **Automatic SSH Shutdown:** Shutdown (not forced) of Node 2 via SSH when no servers are online for x mins. Servers shut down if no Players are online for x mins.
- **Resource Management (One-Server-Rule):** Queries the Pterodactyl API before starting a server. Automatically stops running servers on the same node to prevent RAM overflow.
- **Status Verification:** Verifies the physical machine status (ping) and the Wings daemon readiness before sending API commands.
- **Permitted User Role:** Only Users with a specific Role ID in Discord can use the command buttons.
- **CI/CD Pipeline:** Auto testing and deployment via GitHub Actions.
- **Map Control:** The ability to change maps for a server from the Discord Dashboard (currently only planned for Minecraft).