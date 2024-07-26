import requests
import json

from lmnr.types import ConditionedValue, ChatMessage, NodeInput
from lmnr_engine.engine.action import NodeRunError, RunOutput


{% for task in cookiecutter._tasks.values() %}
{% if task.node_type == "LLM" %}
def {{task.function_name}}({{ task.handle_args }}, _env: dict[str, str]) -> RunOutput:
    {% set chat_messages_found = false %}
    {% for input_handle_name in task.input_handle_names %}
    {% if input_handle_name == 'chat_messages' %}
    {% set chat_messages_found = true %}
    {% endif %}
    {% endfor %}

    {% if chat_messages_found %}
    input_chat_messages = chat_messages
    {% else %}
    input_chat_messages = []
    {% endif %}

    model = "{{task.config.model}}"

    rendered_prompt = """{{task.config.prompt}}"""
    {% set prompt_variables = task.input_handle_names|reject("equalto", "chat_messages") %}
    {% for prompt_variable in prompt_variables %}
    {# TODO: Fix this. Using double curly braces in quotes because normal double curly braces
    # get replaced during rendering by Cookiecutter. This is a hacky solution.#}
    rendered_prompt = rendered_prompt.replace("{{'{{'}}{{prompt_variable}}{{'}}'}}", {{prompt_variable}})  # type: ignore
    {% endfor %}

    {% if task.config.enable_structured_output %}
    import lmnr_baml
    baml_schema = """{{ task.config.structured_output_schema }}"""
    baml_target = {{ task.config.structured_output_schema_target_str }}
    rendered_baml = lmnr_baml.render_prompt(baml_schema, baml_target)
    prompt = f"{rendered_prompt}\n\n{rendered_baml}"
    {% else %}
    prompt = rendered_prompt
    {% endif %}

    {% if task.config.model_params == none %}
    params = {}
    {% else %}
    params = json.loads(
        """{{task.config.model_params}}"""
    )
    {% endif %}

    messages = [ChatMessage(role="system", content=prompt)]
    messages.extend(input_chat_messages)

    {% if task.config.provider == "openai" %}
    from lmnr_engine.language_model.openai import chat_completion
    completion = chat_completion(messages, model, prompt, params, _env)
    {% elif task.config.provider == "anthropic" %}
    from lmnr_engine.language_model.anthropic import chat_completion
    completion = chat_completion(messages, model, prompt, params, _env)
    {% else %}
    {% endif %}

    completion_message = completion.choices[0].message.content
    {% if task.config.enable_structured_output %}
    retry_count = 0
    max_retries = {{ task.config.structured_output_max_retries }}
    while True:
        try:
            completion_message = lmnr_baml.validate_result(baml_schema, completion_message, baml_target)
        except Exception as e:
            retry_count += 1
            if retry_count > max_retries:
                raise NodeRunError(f"Json schema validation failed after {max_retries} retries.\n\nLast attempt's output:\n{completion_message}.\n\nError:\n{str(e)}")

            messages.extend([ChatMessage(role="assistant", content=completion_message)])
            messages.extend([ChatMessage(role="user", content=f"Json schema validation failed with error: {str(e)}\n\nPlease retry")])
            completion = chat_completion(messages, model, prompt, params, _env)
            completion_message = completion.choices[0].message.content
        else:
            break
        
    {% endif %}

    return RunOutput(status="Success", output=completion_message)


{% elif task.node_type == "SemanticSearch" %}
def {{task.function_name}}(query: NodeInput, _env: dict[str, str]) -> RunOutput:
    {% set datasources_length=task.config.datasource_ids|length %}
    {% if datasources_length == 0 %}
    raise NodeRunError("No datasources provided")
    {% endif %}

    headers = {
        "Authorization": f"Bearer {_env['LMNR_PROJECT_API_KEY']}",
    }
    data = {
        "query": query,
        "limit": {{ task.config.limit }},
        "threshold": {{ task.config.threshold }},
        "datasourceIds": {{ task.config.datasource_ids_list }},
    }
    query_res = requests.post("https://api.lmnr.ai/v2/semantic-search", headers=headers, json=data)
    if query_res.status_code != 200:
        raise NodeRunError(f"Vector search request failed:{query_res.status_code}\n{query_res.text}")

    results = query_res.json()

    def render_query_res_point(template: str, point: dict, relevance_index: int) -> str:
        data = point["data"]
        data["relevance_index"] = relevance_index
        res = template
        for key, value in data.items():
            res = res.replace("{{'{{'}}" + key + "{{'}}'}}", str(value))
        return res

    rendered_res_points = [render_query_res_point("""{{task.config.template}}""", res_point, index + 1) for (index, res_point) in enumerate(results)]
    output = "\n".join(rendered_res_points)

    return RunOutput(status="Success", output=output)


{% elif task.node_type == "Router" %}
def {{task.function_name}}(condition: NodeInput, input: NodeInput, _env: dict[str, str]) -> RunOutput:
    routes = {{ task.config.routes }}
    has_default_route = {{ task.config.has_default_route }}

    for route in routes:
        if route == condition:
            return RunOutput(status="Success", output=ConditionedValue(condition=route, value=input))
        
    if has_default_route:
        return RunOutput(status="Success", output=ConditionedValue(condition=routes[-1], value=input))

    raise NodeRunError(f"No route found for condition {condition}")


{% elif task.node_type == "Condition" %}
def {{task.function_name}}(input: NodeInput, _env: dict[str, str]) -> RunOutput:
    condition = "{{task.config.condition}}"

    if input.condition == condition:
        return RunOutput(status="Success", output=input.value)
    else:
        return RunOutput(status="Termination", output=None)


{% elif task.node_type == "Code" %}
def {{task.function_name}}({{ task.handle_args }}, _env: dict[str, str]) -> RunOutput:
    {# TODO: Add support for ChatMessageContentPart #}
    def input_to_code_node_arg(inp):
        if isinstance(inp, str):
            return inp
        elif isinstance(inp, list):
            if all(isinstance(elem, str) for elem in inp):
                return inp
            else:
                return [{"role": elem.role, "content": elem.content} for elem in inp]
        elif isinstance(inp, ConditionedValue):
            return {"condition": inp.condition, "value": input_to_code_node_arg(inp.value)}
        else:
            raise NodeRunError(f"Unsupported input type: {type(inp)}")

    def code_node_res_to_node_input(res):
        if isinstance(res, str):
            return res
        elif isinstance(res, list):
            if all(isinstance(elem, str) for elem in res):
                return res
            else:
                return [ChatMessage(role=elem["role"], content=elem["content"]) for elem in res]
        else:
            raise NodeRunError(f"Unsupported output type: {type(res)}")

{{ task.config.code | indent(4, "   ", false) }}

    res = {{ task.config.fn_name }}({{ task.config.fn_inputs }})

    return RunOutput(status="Success", output=code_node_res_to_node_input(res))


{% elif task.node_type == "JsonExtractor" %}
def {{task.function_name}}(input: NodeInput, _env: dict[str, str]) -> RunOutput:
    import re
    import pystache

    # Replaces "json" extension used in pipeline builder and not needed in pystache
    def remove_json_word(text: str) -> str:
        pattern = re.compile(r'{{'{{'}}\s*json\s+')
        result = pattern.sub('{{'{{'}}', text)
        return result

    template = remove_json_word("""{{task.config.template}}""")

    renderer = pystache.Renderer(escape = lambda u: u)
    res = renderer.render(template, json.loads(input))

    return RunOutput(status="Success", output=res)


{% elif task.node_type == "Output" %}
def {{task.function_name}}(output: NodeInput, _env: dict[str, str]) -> RunOutput:
    return RunOutput(status="Success", output=output)


{% elif task.node_type == "Input" %}
{# Do nothing for Input tasks #}
{% else %}
def {{task.function_name}}(output: NodeInput, _env: dict[str, str]) -> RunOutput:
    return RunOutput(status="Success", output=output)


{% endif %}
{% endfor %}
# Other functions can be added here
