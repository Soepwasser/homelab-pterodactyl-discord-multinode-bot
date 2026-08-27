#################################################################
# dashboard.py                                                  #
# Interactive Live-Dashboard for Server Management              #
#################################################################

import logging
import asyncio
import discord
from discord.ext import commands, tasks
from discord import app_commands
from config import NODE2_PTERO_ID, PERMITTED_USER_ROLE_ID
from utils.ptero_client import ptero
from utils.game_client import get_minecraft_status
from utils.power_manager import wake_node2, is_node2_online
import utils.power_manager as power_manager

logger = logging.getLogger("dashboard")

# Global reference to keep track of the active dashboard message for the update loop
dashboard_message_ref = None
dashboard_view_ref = None

# Builds the 2-part dashboard embed (global overview and selected server details)
async def build_dashboard_embed(selected_server_id: str = None) -> discord.Embed:
    # 1. Global Node Overview
    node_online = await is_node2_online()
    node_status_str = "🟢 Online" if node_online else "🔴 Offline"
    if power_manager.is_node2_processing:
        node_status_str += " (Processing...)"
        embed_color = discord.Color.gold()
    elif node_online:
        embed_color = discord.Color.green()
    else:
        embed_color = discord.Color.red()
        
    embed = discord.Embed(title="Server Dashboard", color=embed_color)
        
    servers = await ptero.get_node_servers(NODE2_PTERO_ID)
    
    if not servers:
        embed.description = f"**Node Status:** {node_status_str}\n\nNo servers found."
        return embed

    overview_lines = []
    selected_server = None
    
    for srv in servers:
        identifier = srv.get("identifier")
        name = srv.get("name")
        
        if identifier == selected_server_id:
            selected_server = srv

        if not node_online:
            overview_lines.append(f"**{name}**: Node Offline")
            continue

        status = await ptero.get_server_status(identifier)

        if status == "running":
            # Fetch players using allocations from the server list
            allocs = srv.get("relationships", {}).get("allocations", {}).get("data", [])
            primary_id = srv.get("allocation")
            primary = next((a for a in allocs if a.get("attributes", {}).get("id") == primary_id), None)
            players_str = ""
            if primary:
                # Use raw IP for game queries (aliases may not be resolvable)
                ip = primary["attributes"].get("ip")
                port = primary["attributes"].get("port")
                if ip and port:
                    # TODO: Multi-Game Support (Egg ID) for players in overview
                    mc_status = await get_minecraft_status(ip, port)
                    if mc_status["online"]:
                        players_str = f"({mc_status['players_online']}/{mc_status['players_max']} players)"
            
            overview_lines.append(f"🟢 **{name}**: Online {players_str}")
        elif status == "starting":
            overview_lines.append(f"🟡 **{name}**: Starting...")
        elif status == "stopping":
            overview_lines.append(f"🟠 **{name}**: Stopping...")
        else:
            overview_lines.append(f"🔴 **{name}**: Offline")

    overview_text = "\n".join(overview_lines)
    embed.description = f"**Node Status:** {node_status_str}\n\n**Server Overview:**\n{overview_text}"
    
    # 2. Detailed View for Selected Server
    if selected_server:
        embed.add_field(name="="*40, value="\u200b", inline=False)
        
        s_name = selected_server.get("name")
        
        if not node_online:
            s_status = "offline"
            status_emoji = "🔴"
        else:
            s_status = await ptero.get_server_status(selected_server_id)
            status_emoji = "🔴"
            if s_status == "running": 
                status_emoji = "🟢"
            elif s_status in ["starting", "stopping"]: 
                status_emoji = "🟡"
            
        embed.add_field(
            name=f"Selected: {s_name}", 
            value=f"**Status:** {status_emoji} {s_status.capitalize() if s_status else 'Unknown'}", 
            inline=False
        )
        
    return embed


class ServerSelect(discord.ui.Select):
    def __init__(self, servers, default_val=None):
        options = ServerSelect._build_options(servers, default_val)
        super().__init__(
            placeholder="Select a server...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="btn_select_server",
            row=0
        )

    # Builds the dropdown options list from the server data
    def _build_options(servers, default_val=None):
        options = []
        for srv in servers:
            name = srv.get("name", "Unknown")
            identifier = srv.get("identifier")
            options.append(discord.SelectOption(label=name, value=identifier, default=(identifier == default_val)))
        if not options:
            options.append(discord.SelectOption(label="No servers found", value="none"))
        return options

    async def callback(self, interaction: discord.Interaction):
        if power_manager.is_node2_processing:
            return await interaction.response.send_message("System is currently processing, please wait...", ephemeral=True)
            
        # Defer before anything else to avoid Discord timeout
        await interaction.response.defer()

        # Use global refs (persistent view from cog_load has no server data)
        target_view = dashboard_view_ref or self.view
        message = dashboard_message_ref or interaction.message

        if target_view and hasattr(target_view, 'selected_server'):
            target_view.selected_server = self.values[0]
            await target_view.refresh_dashboard(message, force=True)


class DashboardView(discord.ui.View):
    def __init__(self, bot, servers=None, default_server=None):
        super().__init__(timeout=None)
        self.bot = bot
        self.servers = servers if servers is not None else []
        self.selected_server = default_server if default_server else (self.servers[0]["identifier"] if self.servers else None)
        self.update_select()

    def update_select(self):
        # Update options in place to keep the view store reference valid (used remove/add before, not good no no)
        existing_select = next(
            (child for child in self.children if isinstance(child, ServerSelect)),
            None
        )

        if existing_select is not None:
            existing_select.options = ServerSelect._build_options(self.servers, self.selected_server)
        else:
            self.add_item(ServerSelect(self.servers, self.selected_server))

    def update_item_states(self):
        is_busy = power_manager.is_node2_processing
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if child.custom_id == "btn_start":
                    child.disabled = is_busy
                    child.label = "Starting..." if is_busy else "Start"
                elif child.custom_id == "btn_stop":
                    child.disabled = is_busy
                elif child.custom_id in ["btn_refresh", "btn_ip"]:
                    child.disabled = False
            elif isinstance(child, discord.ui.Select):
                child.disabled = is_busy

    async def ensure_servers_loaded(self):
        if not self.servers:
            servers = await ptero.get_node_servers(NODE2_PTERO_ID)
            if servers:
                self.servers = servers
                if not self.selected_server:
                    self.selected_server = self.servers[0]["identifier"]
                self.update_select()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if isinstance(interaction.user, discord.Member):
            role = interaction.guild.get_role(PERMITTED_USER_ROLE_ID)
            if role in interaction.user.roles:
                return True
        await interaction.response.send_message("You do not have permission to use this dashboard.", ephemeral=True)
        return False

    async def refresh_dashboard(self, message: discord.Message, force: bool = False):
        await self.ensure_servers_loaded()
        self.update_select()
        self.update_item_states()
        embed = await build_dashboard_embed(self.selected_server)
        new_dict = embed.to_dict()
        
        is_busy = power_manager.is_node2_processing
        was_busy = getattr(self, "_last_busy_state", None)
        
        # Only send Discord API request if content changed, busy state changed, or forced
        if force or getattr(self, "_last_embed_dict", None) != new_dict or was_busy != is_busy:
            self._last_embed_dict = new_dict
            self._last_busy_state = is_busy
            try:
                await message.edit(embed=embed, view=self)
            except (discord.NotFound, discord.HTTPException) as e:
                logger.debug(f"Could not edit dashboard message: {e}")

    @discord.ui.button(label="Start", style=discord.ButtonStyle.success, custom_id="btn_start", row=1)
    async def start_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.ensure_servers_loaded()
        if power_manager.is_node2_processing:
            return await interaction.response.send_message("Hardware is currently processing an operation. Please wait...", ephemeral=True)
        if not self.selected_server or self.selected_server == "none":
            return await interaction.response.send_message("No server selected.", ephemeral=True)
            
        await interaction.response.defer()
        power_manager.is_node2_processing = True

        # Immediately update UI so buttons are disabled
        await self.refresh_dashboard(interaction.message, force=True)

        auto_cog = self.bot.get_cog("AutoShutdown")
        if auto_cog:
            auto_cog.reset_all_timers()
        
        try:
            # 1. Wake up Node if offline
            if not await is_node2_online():
                wake_node2()
                # Poll Pterodactyl until Wings is reachable (Client API returns data)
                wings_up = False
                for _ in range(60): # Max 2 mins wait
                    await asyncio.sleep(2)
                    if await ptero.get_server_status(self.selected_server) is not None:
                        wings_up = True
                        break
                if not wings_up:
                    logger.error("Node wakeup timeout.")
                    return
            
            # 2. One-Server-Rule: Graceful Swap
            for s in self.servers:
                s_id = s.get("identifier")
                if s_id != self.selected_server:
                    status = await ptero.get_server_status(s_id)
                    if status in ["running", "starting"]:
                        await ptero.send_power_action(s_id, "stop")
                        
                    # Wait for it to become offline (with a timeout of 120 seconds to prevent infinite locks)
                    if status in ["running", "starting", "stopping"]:
                        for _ in range(60):
                            await asyncio.sleep(2)
                            chk = await ptero.get_server_status(s_id)
                            if chk not in ["running", "starting", "stopping"]:
                                break
                                
            # 3. Start target server
            await ptero.send_power_action(self.selected_server, "start")

            # 4. Grace period to allow Wings to initialize the container cleanly
            await asyncio.sleep(10)
        finally:
            power_manager.is_node2_processing = False
            await self.refresh_dashboard(interaction.message, force=True)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, custom_id="btn_stop", row=1)
    async def stop_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.ensure_servers_loaded()
        if power_manager.is_node2_processing:
            return await interaction.response.send_message("Hardware is currently processing an operation. Please wait...", ephemeral=True)
        if not self.selected_server or self.selected_server == "none":
            return await interaction.response.send_message("No server selected.", ephemeral=True)
            
        await interaction.response.defer()
        await ptero.send_power_action(self.selected_server, "stop")
        await self.refresh_dashboard(interaction.message, force=True)

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, custom_id="btn_refresh", row=1)
    async def refresh_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        servers = await ptero.get_node_servers(NODE2_PTERO_ID)
        if servers:
            self.servers = servers
        await self.refresh_dashboard(interaction.message, force=True)

    @discord.ui.button(label="Show IP", style=discord.ButtonStyle.primary, custom_id="btn_ip", row=1)
    async def ip_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.ensure_servers_loaded()
        if not self.selected_server or self.selected_server == "none":
            return await interaction.response.send_message("No server selected.", ephemeral=True)
            
        selected_srv = next((s for s in self.servers if s.get("identifier") == self.selected_server), None)
        if not selected_srv:
            return await interaction.response.send_message("Error retrieving server details.", ephemeral=True)
            
        allocs = selected_srv.get("relationships", {}).get("allocations", {}).get("data", [])
        primary_id = selected_srv.get("allocation")
        primary = next((a for a in allocs if a.get("attributes", {}).get("id") == primary_id), None)
        
        if primary:
            alias = primary["attributes"].get("alias")
            raw_ip = primary["attributes"].get("ip")
            port = primary["attributes"].get("port")
            if alias:
                # If alias is set, show port as optional, since sometimes its already included in the alias
                addr_str = f"{alias} (:{port})"
            else:
                addr_str = f"{raw_ip}:{port}"
            await interaction.response.send_message(f"Connection address: **{addr_str}**", ephemeral=True)
        else:
            await interaction.response.send_message("No IP address found.", ephemeral=True)


class DashboardCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.update_dashboard_loop.start()

    async def cog_load(self):
        # Register persistent view so button and select clicks work across bot restarts
        self.bot.add_view(DashboardView(self.bot))

    def cog_unload(self):
        if self.update_dashboard_loop.is_running():
            self.update_dashboard_loop.cancel()

    @app_commands.command(name="gservers", description="Displays the server management dashboard")
    async def spawn_dashboard(self, interaction: discord.Interaction):
        global dashboard_message_ref, dashboard_view_ref
        
        # Check permission for permitted role
        if isinstance(interaction.user, discord.Member):
            role = interaction.guild.get_role(PERMITTED_USER_ROLE_ID)
            if role not in interaction.user.roles:
                return await interaction.response.send_message("You do not have permission to view this dashboard.", ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)
        
        servers = await ptero.get_node_servers(NODE2_PTERO_ID)
        view = DashboardView(self.bot, servers)
        embed = await build_dashboard_embed(view.selected_server)
        
        # Delete old message if exists (for cleanliness)
        if dashboard_message_ref:
            try:
                await dashboard_message_ref.delete()
            except Exception:
                pass
                
        msg = await interaction.channel.send(embed=embed, view=view)
        dashboard_message_ref = msg
        dashboard_view_ref = view

        # Delete ephemeral message
        try:
            await interaction.delete_original_response()
        except Exception:
            pass

    @tasks.loop(seconds=10.0)
    async def update_dashboard_loop(self):
        global dashboard_message_ref, dashboard_view_ref
        if dashboard_message_ref and dashboard_view_ref:
            if not power_manager.is_node2_processing:
                try:
                    # Update server list from API to capture changes (e.g. IPs or new servers)
                    servers = await ptero.get_node_servers(NODE2_PTERO_ID)
                    if servers:
                        dashboard_view_ref.servers = servers
                    await dashboard_view_ref.refresh_dashboard(dashboard_message_ref)
                except Exception as e:
                    logger.error(f"Error updating dashboard loop: {e}")

    @update_dashboard_loop.before_loop
    async def before_update(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(DashboardCog(bot))
