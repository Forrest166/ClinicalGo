from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

from common.structured_llm import JsonBatchLLMClient, JsonUsage

from population_rescue_prompt import DEFAULT_POPULATION_RESCUE_PROMPT


@dataclass
class RawPopulationRescueResponse:
    rows: List[Dict[str, Any]]
    usage: JsonUsage
    raw_text: str


def _render_batch_payload(record_texts: Sequence[str], record_ids: Sequence[int]) -> str:
    parts: List[str] = []
    for record_text, record_id in zip(record_texts, record_ids):
        parts.append(f"=== RECORD {int(record_id)} ===")
        parts.append(str(record_text or "").strip())
        parts.append(f"=== END RECORD {int(record_id)} ===")
    return "\n".join(parts).strip()


class Step2APopulationRescueClient(JsonBatchLLMClient):
    def __init__(self, *, prompt_template: str = DEFAULT_POPULATION_RESCUE_PROMPT, **kwargs) -> None:
        super().__init__(**kwargs)
        self.prompt_template = str(prompt_template or DEFAULT_POPULATION_RESCUE_PROMPT).strip()

    def run_batch(self, record_texts: Sequence[str], record_ids: Sequence[int]) -> RawPopulationRescueResponse:
        prompt = (
            f"{self.prompt_template}\n\n"
            f"Batch records:\n{_render_batch_payload(record_texts, record_ids)}\n\n"
            "Return JSON now."
        )
        parsed, usage, raw_text = self.run_json_prompt(prompt)
        return RawPopulationRescueResponse(rows=list(parsed.get("rows", [])), usage=usage, raw_text=raw_text)
