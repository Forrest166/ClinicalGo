from dataclasses import dataclass
from typing import Dict


@dataclass
class Step2ARow:
    source_index: str = ""
    pmid: str = ""
    nct_id: str = ""
    journal: str = ""
    year: str = ""
    indication: str = ""
    population_raw: str = ""
    severity: str = ""
    treatment_history: str = ""
    population_status: str = ""
    target: str = ""
    intervention: str = ""
    intervention_type: str = ""
    comparator: str = ""
    outcome_direction: str = ""
    phase: str = ""
    sample_size: str = ""
    follow_up_time: str = ""
    evidence_snippet: str = ""

    def to_export_dict(self, record_id: str) -> Dict[str, str]:
        return {
            "Record ID": record_id,
            "Record Index": self.source_index,
            "PMID": self.pmid,
            "NCT ID": self.nct_id,
            "Journal": self.journal,
            "Year": self.year,
            "Indication": self.indication,
            "Population Raw": self.population_raw,
            "Severity": self.severity,
            "Treatment History": self.treatment_history,
            "Population Status": self.population_status,
            "Target": self.target,
            "Intervention": self.intervention,
            "Intervention Type": self.intervention_type,
            "Comparator": self.comparator,
            "Outcome Direction": self.outcome_direction,
            "Phase": self.phase,
            "Sample Size": self.sample_size,
            "Follow-up Time": self.follow_up_time,
            "Evidence Snippet": self.evidence_snippet,
        }
