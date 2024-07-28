import requests

from lmnr.types import ChatMessage
from lmnr_engine.engine.action import NodeRunError
from lmnr_engine.language_model import ChatCompletion, ChatChoice, ChatUsage


def chat_completion(messages: list[ChatMessage], model: str, prompt: str, params: dict, _env: dict[str, str]) -> ChatCompletion:
    data = {
        "model": model,
        "max_tokens": 4096,
    }
    data.update(params)

    if len(messages) == 1 and messages[0].role == "system":
        messages[0].role = "user"
        message_jsons = [
            {"role": message.role, "content": message.content} for message in messages
        ]
        data["messages"] = message_jsons
    else:
        data["system"] = messages[0].content
        message_jsons = [
            {"role": message.role, "content": message.content} for message in messages[1:]
        ]
        data["messages"] = message_jsons

    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": _env['ANTHROPIC_API_KEY'],
        "Anthropic-Version": "2023-06-01",
    }
    res = requests.post(
        "https://api.anthropic.com/v1/messages", json=data, headers=headers
    )

    if res.status_code != 200:
        raise NodeRunError(f"Anthropic message request failed: {res.text}")

    completion = res.json()

    """ meta_log = {}
    # TODO: Add node chunk id#}
    meta_log["node_chunk_id"] = None
    meta_log["model"] = model
    meta_log["prompt"] = prompt
    meta_log["input_message_count"] = len(messages)
    meta_log["input_token_count"] = completion["usage"]["input_tokens"]
    meta_log["output_token_count"] = completion["usage"]["output_tokens"]
    meta_log["total_token_count"] = (
        completion["usage"]["input_tokens"] + completion["usage"]["output_tokens"]
    )
    # TODO: Add approximate cost#}
    meta_log["approximate_cost"] = None"""

    return ChatCompletion(
        choices=[ChatChoice(
            message=ChatMessage(role="assistant", content=completion["content"][0]["text"])
        )],
        usage=ChatUsage(
            completion_tokens=completion["usage"]["output_tokens"],
            prompt_tokens=completion["usage"]["input_tokens"],
            total_tokens=completion["usage"]["input_tokens"] + completion["usage"]["output_tokens"],
            approximate_cost=None,
        ),
        model=model,
    )
