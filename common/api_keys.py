import json
import os
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple


def clean_api_key(value: str) -> str:
    key = str(value or "").strip()
    if not key or key.startswith("PASTE_"):
        return ""
    return key


def load_api_key_bundle(search_roots: Sequence[Path]) -> Tuple[Dict[str, str], Dict[str, str], Optional[Path]]:
    candidate_paths = []
    for root in search_roots:
        candidate_paths.append(Path(root) / "api_keys.local.json")
        candidate_paths.append(Path(root) / "api_keys.template.json")

    config_path = next((p for p in candidate_paths if p.exists()), None)
    payload = {}
    if config_path is not None:
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}

    provider_keys = {
        "Gemini": clean_api_key(payload.get("gemini_api_key", "")) or clean_api_key(os.environ.get("GEMINI_API_KEY", "")),
        "Groq": clean_api_key(payload.get("groq_api_key", "")) or clean_api_key(os.environ.get("GROQ_API_KEY", "")),
        "NVIDIA NIM": clean_api_key(payload.get("nvidia_nim_api_key", "")) or clean_api_key(os.environ.get("NVIDIA_API_KEY", "")),
        "GitHub Models": clean_api_key(payload.get("github_models_api_key", "")) or clean_api_key(os.environ.get("GITHUB_MODELS_API_KEY", "")) or clean_api_key(os.environ.get("GITHUB_TOKEN", "")),
        "Mistral": clean_api_key(payload.get("mistral_api_key", "")) or clean_api_key(os.environ.get("MISTRAL_API_KEY", "")),
        "OpenAI-Compatible": clean_api_key(payload.get("openai_api_key", "")) or clean_api_key(os.environ.get("OPENAI_API_KEY", "")),
    }
    base_urls = {
        "openai_base_url": str(payload.get("openai_base_url", "") or "https://api.openai.com/v1").strip(),
        "nvidia_nim_base_url": str(payload.get("nvidia_nim_base_url", "") or "https://integrate.api.nvidia.com/v1").strip(),
        "github_models_base_url": str(payload.get("github_models_base_url", "") or "https://models.github.ai/inference").strip(),
        "mistral_base_url": str(payload.get("mistral_base_url", "") or "https://api.mistral.ai/v1").strip(),
    }
    return provider_keys, base_urls, config_path
