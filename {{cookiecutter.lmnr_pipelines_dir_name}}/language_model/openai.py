import requests

from lmnr.types import ChatMessage
from lmnr_engine.engine.action import NodeRunError
from lmnr_engine.language_model import ChatCompletion, ChatChoice, ChatUsage


def chat_completion(messages: list[ChatMessage], model: str, prompt: str, params: dict, _env: dict[str, str]) -> ChatCompletion:
    message_jsons = [
        {"role": message.role, "content": message.content} for message in messages
    ]

    data = {
        "model": model,
        "messages": message_jsons,
    }
    data.update(params)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {_env['OPENAI_API_KEY']}",
    }
    res = requests.post(
        "https://api.openai.com/v1/chat/completions", json=data, headers=headers
    )

    if res.status_code != 200:
        res_json = res.json()
        raise NodeRunError(f'OpenAI completions request failed: {res_json["error"]["message"]}')

    completion = res.json()

    """meta_log = {}
    # TODO: Add node chunk id
    meta_log["node_chunk_id"] = None
    meta_log["model"] = model
    meta_log["prompt"] = prompt
    meta_log["input_message_count"] = len(messages)
    meta_log["input_token_count"] = completion["usage"]["prompt_tokens"]
    meta_log["output_token_count"] = completion["usage"]["completion_tokens"]
    meta_log["total_token_count"] = (
        completion["usage"]["prompt_tokens"] + completion["usage"]["completion_tokens"]
    )
    # TODO: Add approximate cost
    meta_log["approximate_cost"] = None"""

    return ChatCompletion(
        choices=[ChatChoice(
            message=ChatMessage(role="assistant", content=completion["choices"][0]["message"]["content"])
        )],
        usage=ChatUsage(
            completion_tokens=completion["usage"]["completion_tokens"],
            prompt_tokens=completion["usage"]["prompt_tokens"],
            total_tokens=completion["usage"]["total_tokens"],
            approximate_cost=None,
        ),
        model=model,
    )