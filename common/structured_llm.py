import json
import urllib.parse
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

from common.gemini_models import GeminiModelError, resolve_gemini_model_id
from common.http_transport import StopRequested, TransportError, http_post_json
from common.provider_catalog import resolve_model_name
from common.request_stability import RuntimeSettings, apply_runtime_guards
from common.text_utils import estimate_token_count


PARALLEL_GEMINI_MODELS = {
    "gemini-3.1-flash-lite",
    "gemini-3.1-flash-lite-preview",
    "gemma-3-27b-it",
    "gemma-3-12b-it",
}


class StructuredLLMError(Exception):
    pass


class MalformedModelOutputError(StructuredLLMError):
    pass


class UserCancelledError(StructuredLLMError):
    pass


@dataclass
class JsonUsage:
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    input_tokens_estimated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "prompt_tokens": int(self.prompt_tokens or 0),
            "completion_tokens": int(self.completion_tokens or 0),
            "total_tokens": int(self.total_tokens or 0),
            "input_tokens_estimated": bool(self.input_tokens_estimated),
        }


def provider_model_supports_parallel(provider: str, model: str) -> bool:
    resolved_provider = str(provider or "").strip()
    resolved_model = resolve_model_name(model)
    return resolved_provider in {"NVIDIA NIM", "GitHub Models", "Mistral"} or (
        resolved_provider == "Gemini" and resolved_model in PARALLEL_GEMINI_MODELS
    )


def build_runtime_settings(
    *,
    provider: str,
    model: str,
    timeout_seconds: int,
    retries: int,
    concurrency: int,
    progress: Optional[Callable[[str], None]] = None,
) -> RuntimeSettings:
    requested_concurrency = max(1, int(concurrency))
    if not provider_model_supports_parallel(provider, model):
        if requested_concurrency != 1 and progress:
            progress(
                f"Parallel execution is disabled for provider `{provider}` with model `{model}`; using concurrency=1."
            )
        requested_concurrency = 1
    else:
        requested_concurrency = min(100, requested_concurrency)
    return apply_runtime_guards(
        provider=provider,
        model=model,
        timeout_seconds=timeout_seconds,
        retries=retries,
        concurrency=requested_concurrency,
        progress=progress,
        label=f"Model-specific guard for {model}",
    )


def extract_json_block(text: str) -> str:
    stripped = str(text or "").strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    if stripped.startswith("[") and stripped.endswith("]"):
        return stripped
    object_start = stripped.find("{")
    object_end = stripped.rfind("}")
    array_start = stripped.find("[")
    array_end = stripped.rfind("]")
    if object_start != -1 and object_end > object_start:
        return stripped[object_start : object_end + 1]
    if array_start != -1 and array_end > array_start:
        return stripped[array_start : array_end + 1]
    raise MalformedModelOutputError("Model response did not contain a complete JSON object or array.")


def parse_json_payload(text: str) -> Dict[str, Any]:
    json_text = extract_json_block(text)
    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise MalformedModelOutputError(
            f"Model returned invalid JSON near line {exc.lineno}, column {exc.colno}."
        ) from exc
    if isinstance(parsed, list):
        return {"rows": [item for item in parsed if isinstance(item, dict)]}
    if not isinstance(parsed, dict):
        raise MalformedModelOutputError(
            f"Model JSON top-level type must be object or array, got {type(parsed).__name__}."
        )
    rows = parsed.get("rows", [])
    if isinstance(rows, dict):
        rows = [rows]
    elif not isinstance(rows, list):
        rows = []
    parsed["rows"] = [item for item in rows if isinstance(item, dict)]
    return parsed


class JsonBatchLLMClient:
    def __init__(
        self,
        *,
        provider: str,
        model: str,
        api_key: str,
        base_url: str = "",
        timeout_seconds: int = 180,
        retries: int = 2,
        should_stop: Optional[Callable[[], bool]] = None,
        user_agent: str = "ClinicalExtractor/1.0 (+desktop)",
    ) -> None:
        self.provider = str(provider or "").strip()
        self.model = resolve_model_name(model)
        self.api_key = str(api_key or "").strip()
        self.base_url = str(base_url or "").strip().rstrip("/")
        self.timeout_seconds = max(30, int(timeout_seconds))
        self.retries = max(0, int(retries))
        self.should_stop = should_stop
        self.user_agent = user_agent
        if not self.model:
            raise StructuredLLMError("Please choose or enter a model name.")
        if not self.api_key:
            raise StructuredLLMError("API key is required.")

    def resolve_runtime_model(self) -> str:
        if self.provider != "Gemini":
            return self.model
        try:
            resolved_model, _hint = resolve_gemini_model_id(
                self.model,
                api_key=self.api_key,
                timeout=min(60, self.timeout_seconds),
            )
        except GeminiModelError as exc:
            raise StructuredLLMError(str(exc)) from exc
        self.model = resolved_model
        return self.model

    def run_json_prompt(self, prompt: str) -> Tuple[Dict[str, Any], JsonUsage, str]:
        if self.provider == "Gemini":
            raw_text, usage = self._run_gemini(prompt)
        elif self.provider == "Groq":
            raw_text, usage = self._run_openai_compatible(prompt, "https://api.groq.com/openai/v1", "Groq")
        elif self.provider == "NVIDIA NIM":
            raw_text, usage = self._run_openai_compatible(
                prompt, "https://integrate.api.nvidia.com/v1", "NVIDIA NIM"
            )
        elif self.provider == "GitHub Models":
            raw_text, usage = self._run_openai_compatible(
                prompt, "https://models.github.ai/inference", "GitHub Models"
            )
        elif self.provider == "Mistral":
            raw_text, usage = self._run_openai_compatible(prompt, "https://api.mistral.ai/v1", "Mistral")
        elif self.provider == "OpenAI-Compatible":
            if not self.base_url:
                raise StructuredLLMError("Base URL is required for OpenAI-Compatible mode.")
            raw_text, usage = self._run_openai_compatible(prompt, self.base_url, "OpenAI-Compatible")
        else:
            raise StructuredLLMError(f"Unsupported provider: {self.provider}")
        return parse_json_payload(raw_text), usage, raw_text

    def _request_json(self, url: str, payload: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        try:
            return http_post_json(
                url=url,
                headers=headers,
                payload=payload,
                timeout=self.timeout_seconds,
                retries=self.retries,
                should_stop=self.should_stop,
                user_agent=self.user_agent,
                rate_limit_scope=f"{self.provider}:{self.model}",
            )
        except StopRequested as exc:
            raise UserCancelledError(str(exc)) from exc
        except TransportError as exc:
            raise StructuredLLMError(str(exc)) from exc

    def _run_gemini(self, prompt: str) -> Tuple[str, JsonUsage]:
        endpoint_root = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{urllib.parse.quote(self.model, safe='')}"
        )
        headers = {"Content-Type": "application/json; charset=utf-8"}
        usage = JsonUsage(
            provider="Gemini",
            model=self.model,
            prompt_tokens=estimate_token_count(prompt),
            input_tokens_estimated=True,
        )

        if self.model.startswith("gemma-"):
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {
                                "text": (
                                    "Return only valid JSON matching the requested schema.\n\n"
                                    f"{prompt}"
                                )
                            }
                        ],
                    }
                ],
                "generationConfig": {"temperature": 0.1},
            }
        else:
            payload = {
                "systemInstruction": {
                    "parts": [{"text": "Return only valid JSON matching the requested schema."}]
                },
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
            }

        response = self._request_json(
            f"{endpoint_root}:generateContent?key={urllib.parse.quote(self.api_key, safe='')}",
            payload,
            headers,
        )
        usage_meta = response.get("usageMetadata", {})
        usage.prompt_tokens = int(usage_meta.get("promptTokenCount", usage.prompt_tokens))
        usage.completion_tokens = int(usage_meta.get("candidatesTokenCount", 0))
        usage.total_tokens = int(
            usage_meta.get("totalTokenCount", usage.prompt_tokens + usage.completion_tokens)
        )
        usage.input_tokens_estimated = False

        candidates = response.get("candidates", [])
        if not candidates:
            raise StructuredLLMError("Gemini returned no candidates.")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(str(part.get("text", "")) for part in parts if isinstance(part, dict)).strip()
        if not text:
            raise StructuredLLMError("Gemini returned empty content.")
        return text, usage

    def _run_openai_compatible(
        self,
        prompt: str,
        base_url: str,
        provider_name: str,
    ) -> Tuple[str, JsonUsage]:
        endpoint = f"{base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.model,
            "temperature": 0.1,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {self.api_key}",
        }
        if provider_name == "GitHub Models":
            headers["Accept"] = "application/vnd.github+json"
            headers["X-GitHub-Api-Version"] = "2022-11-28"

        response = self._request_json(endpoint, payload, headers)
        choices = response.get("choices", [])
        if not choices:
            raise StructuredLLMError(f"{provider_name} returned no choices.")
        text = str(choices[0].get("message", {}).get("content", "")).strip()
        if not text:
            raise StructuredLLMError(f"{provider_name} returned empty content.")

        usage_obj = response.get("usage", {})
        usage = JsonUsage(
            provider=provider_name,
            model=self.model,
            prompt_tokens=int(usage_obj.get("prompt_tokens", estimate_token_count(prompt))),
            completion_tokens=int(usage_obj.get("completion_tokens", estimate_token_count(text))),
            total_tokens=int(
                usage_obj.get(
                    "total_tokens",
                    int(usage_obj.get("prompt_tokens", estimate_token_count(prompt)))
                    + int(usage_obj.get("completion_tokens", estimate_token_count(text))),
                )
            ),
            input_tokens_estimated="prompt_tokens" not in usage_obj,
        )
        return text, usage
