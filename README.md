# Pterodactyl Multinode Discord Bot

## Project Context
A Discord Bot to manage Ptereodactyl servers on a multinode setup.
- **Node 1 (Infrastructure):** Runs 24/7 (Proxmox, Pterodactyl Panel).
- **Node 2 (Game Servers):** Game server node (Wings, Game Servers). Turned on on demand to minimize power consumption.

## Features
- **Hardware Control:** Integration of Wake-on-LAN (WoL) to remotely boot Node 2.
- **Node Status Verification:** Verifies the physical machine status via SSH port check.
- **Automatic SSH Shutdown:** 2-Tier shutdown logic. Stops idle game servers when no players are online for x mins, and shuts down Node 2 via SSH when no servers are running.
- **Pterodactyl API Integration:** Bulk querying of server limits and allocations.

## Vision / Roadmap
- **Discord Embedded Message-Dashboard**: Dashboard with buttons to monitor and control servers (start/stop/restart/show Server-IP).
- **Resource Management (One-Server-Rule):** Queries the Pterodactyl API before starting a server. Automatically stops running servers on the same node to prevent RAM overflow.
- **Permitted User Role:** Only Users with a specific Role ID in Discord can use the command buttons.
- **CI/CD Pipeline:** Auto testing and deployment via GitHub Actions.
- **Multi-Game Support (Egg IDs):** Route server status queries dynamically based on Pterodactyl Egg IDs (e.g. Minecraft, 7 Days to Die, etc.). (Currently it's only for minecraft)
- **Map Control:** The ability to change maps for a server from the Discord Dashboard (currently only planned for Minecraft).

## Hardware Setup 
### Step 1: Node 2 User Setup
- 1. `apt install sudo`
- 2. `sudo adduser [bot-username]` (if you install as root, use the command without `sudo`) Make sure to remember the password for step 2.
- 3. `sudo visudo` -> Add: `[bot-username] ALL=(ALL) NOPASSWD: /sbin/shutdown` (to the very bottom)

### Step 2: Node 1 (container in which the Bot runs)
- 1. If you set a password: Log in as root
- 1. `ssh-keygen -t ed25519` -> press enter without input to use default path and no passphrase
- 2. `ssh-copy-id [bot-username]@[NODE2_IP]` (it will save the key to `/home/[bot-username]/.ssh/id_ed25519`, when moving it to another path also change the path in the .env)