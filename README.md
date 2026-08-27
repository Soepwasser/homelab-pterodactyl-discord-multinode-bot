# Pterodactyl Multinode Discord Bot

## Project Context
A Discord Bot to manage Pterodactyl servers on a multinode setup.
- **Node 1 (Infrastructure):** Runs 24/7 (Proxmox, Pterodactyl Panel).
- **Node 2 (Game Servers):** Game server node (Wings, Game Servers). Turned on on demand to minimize power consumption.

```text
[ Discord User ] ─── (Slash Commands / UI Buttons) ───► [ PteroBot (Node 1) ]
                                                              │
                     ┌────────────────────────────────────────┴────────────────────────────────────────┐
                     ▼                                                                                 ▼
     [ Pterodactyl Panel API ]                                                                 [ Node 2 Hardware ]
  (Server List, Allocations, Power Actions)                                               (WoL / SSH Port Ping / SSH Shutdown)
```

## Features
- **Interactive Discord Live Dashboard (`/gservers`):**
  - Live 2-part Embed displaying global Node 2 status, running server overview, and player counts.
  - Dropdown menu to select any server on Node 2.
  - Interactive UI buttons: **Start**, **Stop**, **Refresh**, and **Show IP** (ephemeral IP/Port display).
  - Background auto-refresh loop updating the dashboard state every 10 seconds.
- **Resource Management (One-Server-Rule & Graceful Swap):**
  - Ensures only one heavy game server runs at a time on Node 2 to prevent RAM exhaustion.
  - Automatically stops running servers before booting a newly selected server.
- **Hardware Control:** Integration of Wake-on-LAN (WoL) to remotely boot Node 2.
- **Node Status Verification:** Verifies the physical machine status via SSH port check.
- **Automatic SSH Shutdown:** 2-Tier shutdown logic. Stops idle game servers when no players are online for x mins, and shuts down Node 2 via SSH when no servers are running.
- **Pterodactyl API Integration:** Bulk querying of server limits and allocations.
- **Permitted User Role:** Only users with a specific Role ID in Discord can use the command buttons.

---

## Setup & Installation

### Step 1: Node 2 Setup (Target Machine)
- 1. `apt update && apt install -y sudo`
- 2. `sudo adduser [bot-username]` (if you install as root, use the command without `sudo`). Make sure to remember the password.
- 3. `sudo visudo` -> Add the following line at the very bottom:
  ```text
  [bot-username] ALL=(ALL) NOPASSWD: /sbin/shutdown
  ```

### Step 2: Node 1 Setup (SSH Key Configuration)
- 1. If you set a password: Log in as root.
- 2. `ssh-keygen -t ed25519` -> Press enter without input to use default path and empty passphrase.
- 3. `ssh-copy-id [bot-username]@[NODE2_IP]` (it will save the key to `/home/[bot-username]/.ssh/id_ed25519`, when moving it to another path also change the path in the `.env`).
- 4. Test passwordless connection:
  ```bash
  ssh -i ~/.ssh/id_ed25519 [bot-username]@[NODE2_IP] "sudo /sbin/shutdown --help"
  ```

### Step 3: Installation & Configuration (Node 1)
1. Clone the repository:
   ```bash
   git clone https://github.com/Soepwasser/homelab-pterodactyl-discord-multinode-bot.git
   cd homelab-pterodactyl-discord-multinode-bot
   ```
2. Create and activate virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure `.env`:
   ```bash
   cp .env.example .env
   nano .env
   ```

#### Environment Variables (`.env`)
| Variable | Description |
| :--- | :--- |
| `DISCORD_TOKEN` | Discord Bot Token from the Discord Developer Portal |
| `PERMITTED_USER_ROLE_ID` | Discord Role ID allowed to click dashboard buttons |
| `PTERO_PANEL_URL` | Base URL of your Pterodactyl panel (e.g. `https://panel.example.com`) |
| `PTERO_API_KEY` | Application API Key (*Admin Panel → Application API*) |
| `PTERO_CLIENT_KEY` | Client API Key of an Admin account (*Account Settings → API Credentials*) |
| `NODE2_MAC` | MAC address of Node 2 network interface (used for WoL) |
| `NODE2_IP` | Local IP address of Node 2 (e.g. `192.168.1.50`) |
| `NODE2_SSH_USER` | SSH username on Node 2 (e.g. `bot-admin`) |
| `NODE2_SSH_KEY_PATH` | Path to the private SSH key (e.g. `~/.ssh/id_ed25519`) |
| `NODE2_PTERO_ID` | Node ID of Node 2 in the Pterodactyl Panel (e.g. `2`) |

#### Additional Settings (`config.py`)
| Setting | Default | Description |
| :--- | :--- | :--- |
| `PTERO_SERVER_FETCH_LIMIT` | `50` | Maximum number of servers fetched in one API request (increase if > 50 servers) |
| `ENABLE_AUTO_SHUTDOWN` | `True` | Global toggle to enable or disable the auto-shutdown background loop |
| `SERVER_IDLE_SHUTDOWN_MINUTES` | `60` | Idle time in minutes with 0 players online before stopping a running game server |
| `NODE_IDLE_SHUTDOWN_MINUTES` | `120` | Idle time in minutes with 0 active servers before shutting down Node 2 hardware via SSH |

---

## Running 24/7 as a Systemd Service

To ensure the bot runs continuously in the background and restarts on system reboot:

### 1. Create Service File
Create `/etc/systemd/system/ptero-discord-bot.service`:
```bash
sudo nano /etc/systemd/system/ptero-discord-bot.service
```

```ini
[Unit]
Description=Pterodactyl Multinode Discord Bot
After=network.target

[Service]
Type=simple
User=YOUR_USER
WorkingDirectory=/home/YOUR_USER/homelab-pterodactyl-discord-multinode-bot
ExecStart=/home/YOUR_USER/homelab-pterodactyl-discord-multinode-bot/.venv/bin/python main.py
Restart=always
RestartSec=10
EnvironmentFile=/home/YOUR_USER/homelab-pterodactyl-discord-multinode-bot/.env

# Security
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

### 2. Enable and Start the Service
```bash
# Reload systemd daemon
sudo systemctl daemon-reload

# Enable autostart on boot and start the bot immediately
sudo systemctl enable --now ptero-discord-bot

# Check status
sudo systemctl status ptero-discord-bot
```

### 3. Service Management Commands
```bash
# Start the bot
sudo systemctl start ptero-discord-bot

# Stop the bot
sudo systemctl stop ptero-discord-bot

# Restart the bot (e.g. after code updates)
sudo systemctl restart ptero-discord-bot

# View live logs
sudo journalctl -u ptero-discord-bot -f
```

---

## Discord Usage
1. In Discord, run the slash command:
   ```text
   /gservers
   ```
2. The bot spawns the live dashboard embed with a dropdown to choose servers and buttons to control the node/server.
3. The dashboard automatically refreshes every 10 seconds (configurable).

---

## Vision / Roadmap
- [ ] **Setup Script:** Add a one-liner setup / Install / Update / Uninstall script.
- [ ] **Separate Auto-Shutdown Toggles:** Separate settings to enable/disable Server-level and Hardware-level auto-shutdown independently.
- [ ] **Multi-Game Support (Egg IDs):** Route server status queries dynamically based on Pterodactyl Egg IDs (e.g. Minecraft, 7 Days to Die, etc.). (Currently it's only for minecraft)
- [ ] **Map Control:** The ability to change maps for a server from the Discord Dashboard (currently only planned for Minecraft).
- [ ] **CI/CD Pipeline:** Auto testing and deployment via GitHub Actions.