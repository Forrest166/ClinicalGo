from typing import Dict, List

MODEL_CATALOG: Dict[str, List[Dict[str, str]]] = {
    "Gemini": [
        {
            "name": "gemini-2.5-flash",
            "display_name": "Gemini 2.5 Flash",
            "recommended": "Recommended",
            "reason": "Best primary choice for structured text extraction in your current setup.",
            "group": "Primary extraction",
        },
        {
            "name": "gemini-3-flash-preview",
            "display_name": "Gemini 3 Flash",
            "recommended": "Alternative",
            "reason": "Alternative text extraction model when available in your account.",
            "group": "Primary extraction",
        },
        {
            "name": "gemini-3.1-flash-lite-preview",
            "display_name": "Gemini 3.1 Flash Lite",
            "recommended": "High-throughput",
            "reason": "Useful for lighter extraction with higher request headroom.",
            "group": "Lightweight / high-throughput",
        },
        {
            "name": "gemini-2.5-flash-lite",
            "display_name": "Gemini 2.5 Flash Lite",
            "recommended": "Budget",
            "reason": "Lower-cost fallback for structured extraction.",
            "group": "Lightweight / high-throughput",
        },
        {
            "name": "gemma-3-27b-it",
            "display_name": "Gemma 3 27B",
            "recommended": "Local-style fallback",
            "reason": "Good larger open model fallback, but its free-tier token-per-minute quota is much tighter.",
            "group": "Gemma fallback",
        },
        {
            "name": "gemma-3-12b-it",
            "display_name": "Gemma 3 12B",
            "recommended": "Smaller fallback",
            "reason": "Smaller Gemma fallback, still best used with small request batches.",
            "group": "Gemma fallback",
        },
    ],
    "Groq": [
        {"name": "openai/gpt-oss-120b", "recommended": "Recommended", "reason": "Good balance of extraction quality and speed."},
        {"name": "llama-3.3-70b-versatile", "recommended": "Faster", "reason": "Good for larger batch runs."},
        {"name": "moonshotai/kimi-k2-instruct-0905", "recommended": "Long context", "reason": "Useful when single batches are larger."},
    ],
    "NVIDIA NIM": [
        {"name": "qwen/qwen3-next-80b-a3b-instruct", "recommended": "Recommended", "reason": "Best fit among current NIM Qwen options for long-context literature extraction without extra thinking traces.", "group": "Qwen"},
        {"name": "qwen/qwen3-next-80b-a3b-thinking", "recommended": "Hard cases", "reason": "Reasoning-oriented Qwen model for difficult extraction cases.", "group": "Qwen"},
        {"name": "qwen/qwen3.5-122b-a10b", "recommended": "Qwen3.5 122B", "reason": "Strong newer Qwen3.5 model currently available on NVIDIA NIM.", "group": "Qwen"},
        {"name": "qwen/qwen3.5-397b-a17b", "recommended": "Qwen3.5 397B", "reason": "Largest Qwen3.5 option available on your NVIDIA NIM account.", "group": "Qwen"},
        {"name": "openai/gpt-oss-120b", "recommended": "Open reasoning", "reason": "Verified callable on your NVIDIA NIM account with fast responses and strong instruction following.", "group": "Reasoning"},
        {"name": "moonshotai/kimi-k2-instruct-0905", "recommended": "Long context", "reason": "Verified callable on your NVIDIA NIM account and robust for longer evidence-heavy extraction prompts.", "group": "Reasoning"},
        {"name": "meta/llama-3.1-70b-instruct", "recommended": "Llama 3.1", "reason": "Reliable general-purpose Llama 3.1 text model.", "group": "Llama"},
        {"name": "meta/llama-3.3-70b-instruct", "recommended": "Llama 3.3", "reason": "Stronger Llama 3.3 instruction model for multilingual text extraction.", "group": "Llama"},
        {"name": "nvidia/llama-3.3-nemotron-super-49b-v1.5", "recommended": "Nemotron Super", "reason": "Verified callable on your NVIDIA NIM account with low-latency structured extraction performance.", "group": "Nemotron"},
        {"name": "nvidia/llama-3.1-nemotron-ultra-253b-v1", "recommended": "Nemotron Ultra", "reason": "Top-end Nemotron reasoning model.", "group": "Nemotron"},
    ],
    "GitHub Models": [
        {"name": "openai/gpt-4.1-mini", "recommended": "Recommended", "reason": "Strong quality/speed trade-off for structured extraction."},
        {"name": "openai/gpt-4.1", "recommended": "High quality", "reason": "Higher extraction consistency for complex multi-arm abstracts."},
        {"name": "openai/o4-mini", "recommended": "Hard cases", "reason": "Reasoning-focused option for ambiguous or conflict-heavy extraction batches."},
        {"name": "openai/o3-mini", "recommended": "Reasoning budget", "reason": "Lower-cost reasoning model for tougher normalization and evidence mapping cases."},
        {"name": "openai/o3", "recommended": "Top reasoning", "reason": "Higher-capability reasoning model for the most difficult reconciliation tasks."},
        {"name": "deepseek/deepseek-v3-0324", "recommended": "Budget", "reason": "Cost-effective long-context alternative for bulk extraction."},
        {"name": "meta/llama-3.3-70b-instruct", "recommended": "Open fallback", "reason": "Reliable open-model fallback with strong instruction following."},
    ],
    "Mistral": [
        {"name": "mistral-small-latest", "recommended": "Recommended", "reason": "Best speed/quality trade-off for high-volume extraction."},
        {"name": "mistral-large-latest", "recommended": "High quality", "reason": "Higher ceiling for difficult or noisy abstracts."},
        {"name": "mistral-medium-2508", "recommended": "Balanced", "reason": "Pinned medium-tier model for stable quality and predictable behavior."},
        {"name": "mistral-small-2506", "recommended": "Pinned fallback", "reason": "Version-pinned small model for reproducible runs."},
        {"name": "ministral-8b-2512", "recommended": "Budget", "reason": "Low-cost fallback when throughput is prioritized over peak quality."},
    ],
    "OpenAI-Compatible": [
        {"name": "gpt-4.1-mini", "recommended": "Example", "reason": "Solid default for compatible endpoints."},
        {"name": "deepseek-chat", "recommended": "Budget", "reason": "Often cheaper for bulk extraction."},
    ],
}


MODEL_ALIASES = {
    "Gemini 2.5 Flash": "gemini-2.5-flash",
    "Gemini 3 Flash": "gemini-3-flash-preview",
    "Gemini 3.1 Flash Lite": "gemini-3.1-flash-lite-preview",
    "Gemini 2.5 Flash Lite": "gemini-2.5-flash-lite",
    "Gemma 3 27B": "gemma-3-27b-it",
    "Gemma 3 12B": "gemma-3-12b-it",
    "gemini-3-flash": "gemini-3-flash-preview",
    "gemini-3.1-flash-lite": "gemini-3.1-flash-lite-preview",
    "GPT-OSS 120B (NIM)": "openai/gpt-oss-120b",
    "Kimi K2 Instruct 0905 (NIM)": "moonshotai/kimi-k2-instruct-0905",
    "Qwen3 Next 80B A3B Instruct (NIM)": "qwen/qwen3-next-80b-a3b-instruct",
    "Qwen3 Next 80B A3B Thinking (NIM)": "qwen/qwen3-next-80b-a3b-thinking",
    "Qwen3.5 122B A10B (NIM)": "qwen/qwen3.5-122b-a10b",
    "Qwen3.5 397B A17B (NIM)": "qwen/qwen3.5-397b-a17b",
    "Llama 3.1 70B Instruct (NIM)": "meta/llama-3.1-70b-instruct",
    "Llama 3.3 70B Instruct (NIM)": "meta/llama-3.3-70b-instruct",
    "Nemotron Super 49B v1.5 (NIM)": "nvidia/llama-3.3-nemotron-super-49b-v1.5",
    "Nemotron Ultra 253B (NIM)": "nvidia/llama-3.1-nemotron-ultra-253b-v1",
    "GPT-4.1 Mini (GitHub Models)": "openai/gpt-4.1-mini",
    "GPT-4.1 (GitHub Models)": "openai/gpt-4.1",
    "o4-mini (GitHub Models)": "openai/o4-mini",
    "o3-mini (GitHub Models)": "openai/o3-mini",
    "o3 (GitHub Models)": "openai/o3",
    "DeepSeek V3 (GitHub Models)": "deepseek/deepseek-v3-0324",
    "Llama 3.3 70B (GitHub Models)": "meta/llama-3.3-70b-instruct",
    "Mistral Small Latest": "mistral-small-latest",
    "Mistral Large Latest": "mistral-large-latest",
    "Mistral Medium 2508": "mistral-medium-2508",
    "Mistral Small 2506": "mistral-small-2506",
    "Ministral 8B 2512": "ministral-8b-2512",
}


def recommended_summary(provider: str) -> str:
    items = MODEL_CATALOG.get(provider, [])
    if provider not in {"Gemini", "NVIDIA NIM"}:
        return " | ".join(f"{item['name']} ({item['recommended']}: {item['reason']})" for item in items)

    if provider == "Gemini":
        groups = ["Primary extraction", "Lightweight / high-throughput", "Gemma fallback"]
    else:
        groups = ["Qwen", "Reasoning", "Llama", "Nemotron"]
    parts: List[str] = []
    for group in groups:
        group_items = [item.get("display_name", item["name"]) for item in items if item.get("group") == group]
        if group_items:
            parts.append(f"{group}: {', '.join(group_items)}")
    return " | ".join(parts)


def get_models(provider: str) -> List[str]:
    return [item["name"] for item in MODEL_CATALOG.get(provider, [])]


def resolve_model_name(model: str) -> str:
    return MODEL_ALIASES.get(model.strip(), model.strip())
