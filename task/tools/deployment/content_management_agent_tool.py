from typing import Any

from task.tools.deployment.base_agent_tool import BaseAgentTool


class ContentManagementAgentTool(BaseAgentTool):

    #TODO:
    # Provide implementations of deployment_name (in core config), name, description and parameters.
    # Don't forget to mark them as @property
    # Parameters:
    #   - prompt: string. Required.
    #   - propagate_history: boolean
    @property
    def deployment_name(self) -> str:
        return "content-management-agent"

    @property
    def name(self) -> str:
        return "content_management_agent"

    @property
    def description(self) -> str:
        return "Content Management Agent. Equipped with: Files content extractor and RAG search (supports PDF, TXT, CSV files)."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The query or instruction to send to the Calculations Agent."
                },
                "propagate_history": {
                    "type": "boolean",
                    "default": False,
                    "description": (
                        "Controls whether prior conversation history between the current agent and the Content Management Agent is included. "
                        "If `true`, the Content Management Agent receives previous exchanges to maintain context. "
                        "If `false`, the interaction is handled independently with no past context. "
                        "Only history shared between these two agents is included—interactions with other agents are never passed. "
                        "Enable this only when the `prompt` does not provide enough context but the necessary information exists in the prior conversation."
                    )
                },
            },
            "required": [
                "prompt"
            ]
        }
