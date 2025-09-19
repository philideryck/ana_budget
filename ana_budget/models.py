from dataclasses import dataclass, asdict
from typing import Optional

@dataclass
class OperationBancaire:
    date_comptabilisation: str = ""
    libelle_simplifie: str = ""
    libelle_operation: str = ""
    reference: str = ""
    informations_complementaires: str = ""
    type_operation: str = ""
    categorie: str = ""
    sous_categorie: str = ""
    debit: Optional[float] = None
    credit: Optional[float] = None

    def to_dict_export(self):
        d = asdict(self)
        if d["debit"] is not None:
            d["debit"] = f"{d['debit']:.2f}"
        if d["credit"] is not None:
            d["credit"] = f"{d['credit']:.2f}"
        return d
