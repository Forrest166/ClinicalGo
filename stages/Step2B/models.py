from dataclasses import dataclass
from typing import Dict


@dataclass
class Step2BInputRow:
    record_id: str
    pmid: str
    population_raw: str
    treatment_history: str = ""
    population_focus: str = ""


@dataclass
class Step2BOutputRow:
    record_id: str
    pmid: str = ""
    age: str = ""
    gender: str = ""
    ethnicity: str = ""
    occupation: str = ""
    social_status: str = ""
    treatment_history: str = ""

    def to_export_dict(self) -> Dict[str, str]:
        return {
            "Record ID": self.record_id,
            "PMID": self.pmid,
            "Age": self.age,
            "Gender": self.gender,
            "Ethnicity": self.ethnicity,
            "Occupation": self.occupation,
            "Social Status": self.social_status,
            "Treatment History": self.treatment_history,
        }
