import json
from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Any

from aidial_client import AsyncDial
from aidial_sdk.chat_completion import Message, Role, CustomContent, Stage, Attachment
from pydantic import StrictStr

from task.tools.base_tool import BaseTool
from task.tools.models import ToolCallParams
from task.utils.stage import StageProcessor


class BaseAgentTool(BaseTool, ABC):

    def __init__(self, endpoint: str):
        self.endpoint = endpoint

    @property
    @abstractmethod
    def deployment_name(self) -> str:
        pass

    async def _execute(self, tool_call_params: ToolCallParams) -> str | Message:
        #TODO:
        # 1. All the agents that will used as tools will have two parameters in request:
        #   - `prompt` (the request to agent)
        #   - `propagate_history`, boolean whether we need to propagate the history of communication with called agent
        arguments = json.loads(tool_call_params.tool_call.function.arguments)

        stage = tool_call_params.stage
        choice = tool_call_params.choice

        if prompt := arguments.get("prompt"):
            stage.append_name(f": {prompt}")
            del arguments["prompt"]

        # 2. Use AsyncDial (api_version='2025-01-01-preview'), call the agent with steaming option.
        #    Here, actually, you can find one of the most powerful features of DIAL - Unified protocol. All the
        #    applications that provide `/chat/completions` endpoint and following Unified protocol - can `communicate`
        #    between each other though Unified protocol (that is OpenAI compatible), in other words, applications can
        #    `communicate` between each other like they communication with OpenAI models (Unified protocol is OpenAI compatible).
        #    The second powerful feature is that the application that makes the call provides with whole context and
        #    responsible to manage this context. So, like we calling the model and provide it with the whole history in
        #    the same way we are working with applications, the application that makes a call provide the conversation history.
        #    ⚠️ To provide proper message history you need to implement the `_prepare_messages` method!
        #    ⚠️ Don't forget to include as extra_headers `x-conversation-id`!
        client: AsyncDial = AsyncDial(
            base_url=self.endpoint,
            api_key=tool_call_params.api_key,
            api_version='2025-01-01-preview'
        )
        chunks = await client.chat.completions.create(
            messages=self._prepare_messages(tool_call_params),
            stream=True,
            deployment_name=self.deployment_name,
            extra_body={
                "custom_fields": {
                    "configuration": {**arguments}
                }
            },
            extra_headers={
                "x-conversation-id": tool_call_params.conversation_id,
            },
        )
        # 3. Prepare:
        #   - `content` variable, here we will collect the streamed content
        #   - `custom_content: CustomContent` variable, here we will collect variable CustomContent from agent response
        #   - `stages_map: dict[int, Stage]` variable, here will be persisted propagated stages
        content = ''
        custom_content: CustomContent = CustomContent(attachments=[])
        stages_map: dict[int, Stage] = {}
        # 4. Iterate through chunks and:
        #   - Stream content to the Stage (from tool_call_params) for this tool call
        #   - For custom_content:
        #       - set `state` from response CustomContent to the `custom_content`
        #       - in attachments are found propagate them to choice
        #       - Optional:
        #           Stages propagation: convert response CustomContent to dict and if stages are present:
        #           - each Stage has it is `index`, it will be returned in each chunk. If stage by such index is present
        #             in `stages_map` then you need to propagate content, otherwise you need to create stage
        #           - propagate stage name from response to propagated stage name, the same story for `content` and `attachments`
        #           - if response stage has `status = completed` - we need to close such stage
        async for chunk in chunks:
            if not chunk.choices or not len(chunk.choices): continue

            delta = chunk.choices[0].delta

            if delta and delta.content:
                stage.append_content(delta.content)
                content += delta.content

            if delta and delta.custom_content:
                delta_custom_content = delta.custom_content

                if delta_custom_content.state:
                    custom_content.state = delta_custom_content.state

                if delta_custom_content.attachments:
                    custom_content.attachments.extend(delta_custom_content.attachments)

                custom_content_dct = delta_custom_content.dict(exclude_none=True)

                if stages := custom_content_dct.get("stages"):
                    for stg in stages:
                        index = stg["index"]

                        if found_stage := stages_map.get(index):
                            if stg_name := stg.get("name"):
                                    found_stage.append_name(stg_name)

                            elif stg_content := stg.get("content"):
                                found_stage.append_content(stg_content)

                            elif stg_attachments := stg.get("attachments"):
                                for stg_attachment in stg_attachments:
                                    found_stage.add_attachment(Attachment(**stg_attachment))

                            elif stg.get("status") == "completed":
                                StageProcessor.close_stage_safely(found_stage)
                        else:
                            stages_map[index] = StageProcessor.open_stage(choice, stg.get("name"))

        # 5. Ensure that stages are closed (just iterate through them and close safely with StageProcessor)
        for stage in stages_map.values():
            StageProcessor.close_stage_safely(stage)
        # 6. Return Tool message
        #    ⚠️ Remember, tool message must have tool call id, also don't forget to add `custom_content` since we need
        #       to save properly tool history to choice state later
        for attachment in custom_content.attachments:
            tool_call_params.choice.add_attachment(
                Attachment(**attachment.dict(exclude_none=True))
            )

        return Message(
            role=Role.TOOL,
            content=StrictStr(content),
            custom_content=custom_content,
            tool_call_id=StrictStr(tool_call_params.tool_call.id),
        )

    def _prepare_messages(self, tool_call_params: ToolCallParams) -> list[dict[str, Any]]:
        #TODO:
        # In here we will manage the context for the agent that we are going to call.
        # We support two modes:
        #   - One-shot: only one user message to the Agent with prompt
        #   - Propagate whole Per-To-Per history between this Agent and the Agent that we are calling
        # ---
        # 1. Get: `prompt` and `propagate_history` params from tool call
        arguments = json.loads(tool_call_params.tool_call.function.arguments)

        prompt = arguments["prompt"]


        propagate_history = bool(arguments.get("propagate_history", False))
        # 2. Prepare empty `messages` array, here we will collect history with Per-To-Per communication between this
        #    agent and the agent that we are colling
        messages = []
        # 3. Collect the proper history, iterate through messages and:
        #   - In Assistant messages presented the state with tool_call_history, we need to properly unpack it. If message
        #   from assistant and in custom content present state and in this state present history for this `self.name`
        #   (self.name is the key in state to get tool_call_history from the agent that we are going to call), then
        #   firstly add to `messages` user message that is going before the assistant message and then add assistant
        #   message. For assistant message you need to make a deepcopy and refactor the state for copied message, instead
        #   of the whole state you need to get from the state value by `self.name`
        if propagate_history:
            for i in range(len(tool_call_params.messages)):
                message = tool_call_params.messages[i]
                if message.role == Role.ASSISTANT:
                    if  message.custom_content and message.custom_content.state:
                        message_state = message.custom_content.state
                        if message_state.get(self.name):
                            messages.append(tool_call_params.messages[i - 1].dict(exclude_none=True))

                            message_copy = deepcopy(message)
                            message_copy.custom_content.state = message_state.get(self.name)
                            messages.append(message_copy.dict(exclude_none=True))


        # 4. Lastly, add the user message with `prompt` and don't forget about the custom_content
        last_message = tool_call_params.messages[-1]
        custom_content = last_message.custom_content
        messages.append(
            {
                "role": "user",
                "content": prompt,
                "custom_content": custom_content.dict(exclude_none=True) if custom_content else None,
            }
        )

        return messages