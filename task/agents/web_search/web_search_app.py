import os

import uvicorn
from aidial_sdk import DIALApp
from aidial_sdk.chat_completion import ChatCompletion, Request, Response

from task.agents.web_search.web_search_agent import WebSearchAgent
from task.tools.base_tool import BaseTool
from task.tools.deployment.calculations_agent_tool import CalculationsAgentTool
from task.tools.deployment.content_management_agent_tool import ContentManagementAgentTool
from task.tools.mcp.mcp_client import MCPClient
from task.tools.mcp.mcp_tool import MCPTool
from task.utils.constants import DIAL_ENDPOINT, DEPLOYMENT_NAME

_DDG_MCP_URL = os.getenv('DDG_MCP_URL', "http://localhost:8051/mcp")

#TODO:
# 1. Create WebSearchApplication class and extend ChatCompletion
class WebSearchApplication(ChatCompletion):

    def __init__(self):
        self._tools: list[BaseTool] = []
# 2. As a tools for WebSearchAgent you need to provide:
#   - MCP tools by _DDG_MCP_URL
#   - CalculationsAgentTool (MAS Mesh)
#   - ContentManagementAgentTool (MAS Mesh)
    async def _get_mcp_tools(self, url: str) -> list[BaseTool]:
        try:
            mcp_client = await MCPClient.create(url)

            mcp_tools = await mcp_client.get_tools()

            return [MCPTool(mcp_client, t) for t in mcp_tools]
        except Exception as e:
            print(f"Failed to load MCP tools: {e}")
            raise e

    async def _get_tools(self) -> list[BaseTool]:
        if not self._tools:
            mcp_toops = await self._get_mcp_tools(_DDG_MCP_URL)

            self._tools = [
                CalculationsAgentTool(DIAL_ENDPOINT),
                ContentManagementAgentTool(DIAL_ENDPOINT),
                *mcp_toops
            ]

        return self._tools

# 3. Override the chat_completion method of ChatCompletion, create Choice and call WebSearchAgent
# ---
    async def chat_completion( self, request: Request, response: Response) -> None:
        tools = await self._get_tools()

        with response.create_single_choice() as choice:
            agent = WebSearchAgent(endpoint=DIAL_ENDPOINT, tools=tools)
            await agent.handle_request(
                deployment_name=DEPLOYMENT_NAME,
                choice=choice,
                request=request,
                response=response,
            )
# 4. Create DIALApp with deployment_name `web-search-agent` (the same as in the core config) and impl is instance
#    of the WebSearchApplication
app: DIALApp = DIALApp()
agent = WebSearchApplication()
app.add_chat_completion(deployment_name="web-search-agent", impl=agent)

# 5. Add starter with DIALApp, port is 5003 (see core config)
if __name__ == "__main__":
    uvicorn.run(app, port=5003, host="0.0.0.0", log_level="info")
