"""Read advertised model limits without changing settings or running inference."""

from datetime import datetime, timezone
import json
import os

import httpx

from tradingagents.llm_clients.api_key_env import get_api_key_env
from tradingagents.llm_clients.openai_client import is_openai_compatible


def _positive(value):
    return value if type(value) is int and value > 0 else None


def _first(mapping, keys):
    for key in keys:
        value = _positive(mapping.get(key))
        if value is not None:
            return value
    return None


def _limits(model):
    meta = model.get("meta") if isinstance(model.get("meta"), dict) else {}
    status = model.get("status") if isinstance(model.get("status"), dict) else {}
    context = _first(model, ("context_length", "context_window", "max_model_len")) or _first(meta, ("n_ctx",))
    maximum = _first(model, ("max_output_tokens", "max_completion_tokens"))
    default = _first(model, ("default_output_tokens", "default_max_output_tokens", "default_max_tokens"))
    args = status.get("args")
    if default is None and isinstance(args, list):
        for index, arg in enumerate(args[:-1]):
            if arg == "--default-max-tokens":
                value = args[index + 1]
                if isinstance(value, str) and value.isascii() and value.isdigit() and len(value) <= 18:
                    value = int(value)
                default = _positive(value)
                break
    return context, maximum, default


def discover(config):
    provider = config.llm_provider.lower()
    endpoint = config.backend_url
    result = {"models": [], "endpoint": endpoint, "checked_at": datetime.now(timezone.utc).isoformat()}

    def answer(status, message, data=None):
        for role, name in (("deep", config.deep_think_llm), ("quick", config.quick_think_llm)):
            model = next((item for item in data or [] if isinstance(item, dict) and item.get("id") == name), None)
            context, maximum, default = _limits(model) if model else (None, None, None)
            item_status, item_message = status, message
            if data is not None:
                if model is None:
                    item_status, item_message = "unknown", "The selected model was not listed by the server."
                elif any(value is not None for value in (context, maximum, default)):
                    item_status, item_message = "available", "Limits advertised by the server."
                else:
                    item_status, item_message = "unknown", "The server did not advertise limits for this model."
            result["models"].append({"role": role, "model": name, "context_tokens": context,
                                     "max_output_tokens": maximum, "default_output_tokens": default,
                                     "status": item_status, "message": item_message})
        return result

    if not is_openai_compatible(provider):
        return answer("unknown", "Limit discovery is unavailable for this provider.")
    if not endpoint:
        return answer("unknown", "Enter a model endpoint to discover its limits.")

    key_name = get_api_key_env(provider)
    key = os.getenv(key_name) if key_name else None
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    retry_status = {408, 429, 500, 502, 503, 504}
    for timeout in (10, 20, 30, 30):
        try:
            with httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False) as client:
                with client.stream("GET", endpoint + "/models", headers=headers) as response:
                    if response.status_code in retry_status:
                        continue
                    if response.status_code != 200:
                        return answer("error", f"Model endpoint returned HTTP {response.status_code}.")
                    chunks, size = [], 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > 4 * 1024 * 1024:
                            return answer("error", "Model metadata exceeded the supported size.")
                        chunks.append(chunk)
            payload = json.loads(b"".join(chunks))
            if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
                return answer("error", "Model endpoint returned invalid metadata.")
            return answer("unknown", "", payload["data"])
        except (httpx.TimeoutException, httpx.NetworkError):
            continue
        except (httpx.HTTPError, httpx.InvalidURL, ValueError, UnicodeError):
            return answer("error", "Model endpoint returned invalid or unavailable metadata.")
    return answer("error", "Model endpoint was unavailable after four attempts.")
