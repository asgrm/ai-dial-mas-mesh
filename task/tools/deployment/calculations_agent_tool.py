from typing import Any

from task.tools.deployment.base_agent_tool import BaseAgentTool


class CalculationsAgentTool(BaseAgentTool):

    #TODO:
    # Provide implementations of deployment_name (in core config), name, description and parameters.
    # Don't forget to mark them as @property
    # Parameters:
    #   - prompt: string. Required.
    #   - propagate_history: boolean

    @property
    def deployment_name(self) -> str:
        return "calculations-agent"

    def name(self) -> str:
        return "calculations_agent"

    @property
    def description(self) -> str:
        return ("Calculations Agent. Primary goal to to work with calculations. Capable to make plotly graphics and chart bars. Equipped with: Python Code Interpreter (via MCP), and Simple calculator.")

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                },
                "propagate_history": {
                    "type": "boolean",
                    "default": False,
                    "description": (
                        "Controls whether prior conversation history between the current agent and the Calculations Agent is included. "
                        "If `true`, the Calculations Agent receives previous exchanges to maintain context. "
                        "If `false`, the interaction is handled independently with no past context. "
                        "Only history shared between these two agents is included—interactions with other agents are never passed. "
                        "Enable this only when the `prompt` does not provide enough context but the necessary information exists in the prior conversation."
                    )
                },
            },
            "required": [
                "prompt",
            ]
        }
