import re
import urllib.parse
import urllib.request
import urllib.error
import socket
import json
from typing import Any, Dict, Tuple

from common.provider_catalog import resolve_model_name


class GeminiModelError(Exception):
    pass


def _http_get_json(url: str, timeout: int = 60) -> Dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "ModelResolver/1.0 (+desktop)",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise GeminiModelError(f"HTTP {exc.code}: {body}") from exc
    except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
        raise GeminiModelError(f"Network error while listing Gemini models: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise GeminiModelError(f"Invalid JSON returned by Gemini models endpoint: {exc}") from exc


def _normalize_model_id(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def list_gemini_models(api_key: str, timeout: int = 60) -> Dict[str, Dict[str, Any]]:
    encoded_key = urllib.parse.quote(api_key, safe="")
    list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={encoded_key}"
    payload = _http_get_json(list_url, timeout=timeout)
    models = payload.get("models", [])
    return {str(item.get("name", "")).split("/")[-1]: item for item in models if isinstance(item, dict)}


def check_gemini_model_support(model: str, api_key: str, timeout: int = 60) -> Tuple[bool, str]:
    requested = resolve_model_name(model).strip()
    if not requested:
        return False, "Please choose or enter a Gemini model name."

    names = list_gemini_models(api_key, timeout=timeout)
    if not names:
        return False, "No Gemini models were returned for this API key/project."

    if requested not in names:
        suggestions = [name for name in names if ("flash" in name and "gemini" in name and "live" not in name and "tts" not in name)]
        suggestions = suggestions[:8] if suggestions else sorted(names.keys())[:8]
        return False, (
            f"Model `{requested}` is not available in Gemini Developer API v1beta for this key/project. "
            f"Try one of: {', '.join(suggestions)}"
        )

    actions = names[requested].get("supportedGenerationMethods", [])
    if actions and "generateContent" not in actions:
        return False, f"Model `{requested}` exists but does not support generateContent."
    return True, ""


def resolve_gemini_model_id(model: str, api_key: str, timeout: int = 60) -> Tuple[str, str]:
    requested = resolve_model_name(model).strip()
    if not requested:
        raise GeminiModelError("Please choose or enter a Gemini model name.")

    names = list_gemini_models(api_key, timeout=timeout)
    if not names:
        raise GeminiModelError("No Gemini models were returned for this API key/project.")

    def supports_generate_content(name: str) -> bool:
        actions = names.get(name, {}).get("supportedGenerationMethods", [])
        if not actions:
            return True
        return "generateContent" in actions

    if requested in names:
        if not supports_generate_content(requested):
            raise GeminiModelError(f"Model `{requested}` exists but does not support generateContent.")
        return requested, ""

    dash_variant = requested.replace(".", "-")
    candidate_ids = [requested, f"{requested}-preview", dash_variant, f"{dash_variant}-preview"]
    for candidate in candidate_ids:
        if candidate in names:
            if not supports_generate_content(candidate):
                raise GeminiModelError(f"Model `{candidate}` exists but does not support generateContent.")
            hint = ""
            if candidate != requested:
                hint = f"Model `{requested}` auto-mapped to available model `{candidate}`."
            return candidate, hint

    normalized = _normalize_model_id(requested)
    fuzzy = [name for name in names if _normalize_model_id(name) == normalized]
    if len(fuzzy) == 1:
        matched = fuzzy[0]
        if not supports_generate_content(matched):
            raise GeminiModelError(f"Model `{matched}` exists but does not support generateContent.")
        return matched, f"Model `{requested}` auto-mapped to available model `{matched}`."

    suggestions = [name for name in names if ("flash" in name and "gemini" in name and "live" not in name and "tts" not in name)]
    suggestions = suggestions[:8] if suggestions else sorted(names.keys())[:8]
    raise GeminiModelError(
        f"Model `{requested}` is not available for Gemini v1beta generateContent in this key/project. "
        f"Available text model examples: {', '.join(suggestions)}"
    )
