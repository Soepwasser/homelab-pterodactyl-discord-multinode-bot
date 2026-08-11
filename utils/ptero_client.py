#################################################################
# ptero_client.py                                               #
# Asynchronous HTTP client for the Pterodactyl Panel API        #
#################################################################

import aiohttp
import logging
from typing import Optional, Dict, Any
from config import PTERO_PANEL_URL, PTERO_API_KEY, PTERO_CLIENT_KEY, NODE2_PTERO_ID

logger = logging.getLogger("ptero_client")

class PteroClient:
    def __init__(self):
        self.panel_url = PTERO_PANEL_URL
        self.app_api_key = PTERO_API_KEY
        self.client_api_key = PTERO_CLIENT_KEY
        
        self.app_headers = {
            "Authorization": f"Bearer {self.app_api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        self.client_headers = {
            "Authorization": f"Bearer {self.client_api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    async def _request(self, method: str, endpoint: str, is_client_api: bool = False, **kwargs) -> Optional[Dict[str, Any]]:
        url = f"{self.panel_url}{endpoint}"
        headers = self.client_headers if is_client_api else self.app_headers
        
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.request(method, url, **kwargs) as response:
                    if response.status in (200, 201):
                        return await response.json()
                    elif response.status == 204:
                        return {}
                    else:
                        text = await response.text()
                        logger.error(f"Pterodactyl API Error ({response.status}) at {url}: {text}")
                        return None
        except Exception as e:
            logger.error(f"Pterodactyl Request failed: {e}")
            return None

    # Gets node configuration and status from Application API
    async def get_node_info(self, node_id: int) -> Optional[Dict[str, Any]]:
        return await self._request("GET", f"/api/application/nodes/{node_id}")

    # Checks if the Wings daemon is responding and ready, by checking if the panel successfully returns node details
    async def is_node_wings_ready(self, node_id: int) -> bool:
        data = await self.get_node_info(node_id)
        if data and "attributes" in data:
            # If the API returns the node, it means PtrPanel knows it
            return True
        return False

# Global instance
ptero = PteroClient()
