from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

from common.structured_llm import JsonBatchLLMClient, JsonUsage

from prompt_templates import DEFAULT_PROMPT_TEMPLATE


@dataclass
class RawStep2BResponse:
    rows: List[Dict[str, Any]]
    usage: JsonUsage
    raw_text: str


def _render_batch_payload(items: Sequence[Dict[str, Any]]) -> str:
    return "\n".join(
        [
            f"ROW {item['row_id']}\n"
            f"Record ID: {item['record_id']}\n"
            f"PMID: {item['pmid']}\n"
            f"Population Raw: {item['population_raw']}\n"
            f"Population Focus: {item.get('population_focus', '')}\n"
            f"Treatment History: {item.get('treatment_history', '')}"
            for item in items
        ]
    )


class Step2BExtractionClient(JsonBatchLLMClient):
    def __init__(self, *, prompt_template: str = DEFAULT_PROMPT_TEMPLATE, **kwargs) -> None:
        super().__init__(**kwargs)
        self.prompt_template = str(prompt_template or DEFAULT_PROMPT_TEMPLATE).strip()

    def run_batch(self, items: Sequence[Dict[str, Any]]) -> RawStep2BResponse:
        prompt = (
            f"{self.prompt_template}\n\n"
            f"Input rows:\n{_render_batch_payload(items)}\n\n"
            "Return JSON now."
        )
        parsed, usage, raw_text = self.run_json_prompt(prompt)
        return RawStep2BResponse(rows=list(parsed.get("rows", [])), usage=usage, raw_text=raw_text)
