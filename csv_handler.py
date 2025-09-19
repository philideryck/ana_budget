import csv
import re
from datetime import datetime
from typing import Dict, List, Optional

from models import OperationBancaire
from utils import normalize_header, detect_dialect

_DATE_FORMATS = [
    "%d/%m/%Y",
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%d %m %Y",
    "%d %b %Y",
    "%d %B %Y",
    "%Y/%m/%d",
]


def parse_date(raw: str) -> str:
    """Convertit une date brute en format ISO (yyyy-mm-dd) si possible."""

    value = (raw or "").strip()
    if not value:
        return ""

    candidates = [value]
    short = re.sub(r"[ T].*$", "", value)
    if short and short not in candidates:
        candidates.append(short)

    for candidate in candidates:
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(candidate, fmt).date().isoformat()
            except Exception:
                pass

        try:
            return datetime.fromisoformat(candidate).date().isoformat()
        except Exception:
            pass

    return value  # On conserve la valeur d'origine si non reconnue.


_AMOUNT_SEP_RE = re.compile(r"[ \u00A0]")


def parse_amount(raw: str) -> Optional[float]:
    """Nettoie et convertit un montant vers un float."""

    if raw is None:
        return None

    value = str(raw).strip()
    if not value:
        return None

    negative = False
    if value.startswith("(") and value.endswith(")"):
        negative = True
        value = value[1:-1]

    value = _AMOUNT_SEP_RE.sub("", value)

    # Gestion des décimales à la française.
    if "," in value and value.count(",") == 1 and "." not in value:
        value = value.replace(",", ".")
    if "," in value and "." in value and value.rfind(",") > value.rfind("."):
        value = value.replace(".", "")
        value = value.replace(",", ".")

    value = re.sub(r"[^\d\.\-+]", "", value)
    if value in {"", "-", "+"}:
        return None

    try:
        number = float(value)
        return -abs(number) if negative else number
    except ValueError:
        return None


HEADER_ALIASES: Dict[str, set[str]] = {
    "date_comptabilisation": {
        "date_comptabilisation",
        "date",
        "date_operation",
        "date_valeur",
        "date_de_comptabilisation",
    },
    "libelle_simplifie": {
        "libelle_simplifie",
        "libelle_simplifiee",
        "libelle",
        "intitule",
        "description",
    },
    "libelle_operation": {
        "libelle_operation",
        "details",
        "intitule_complet",
    },
    "reference": {
        "reference",
        "ref",
        "id_operation",
        "numero_operation",
    },
    "informations_complementaires": {
        "informations_complementaires",
        "infos",
        "information",
        "note",
        "memo",
    },
    "type_operation": {
        "type_operation",
        "type",
        "mode",
        "categorie_banque",
    },
    "categorie": {"categorie", "category"},
    "sous_categorie": {"sous_categorie", "sous_categ", "subcategory"},
    "debit": {
        "debit",
        "montant_debit",
        "sortie",
        "amount_out",
        "montant_negatif",
    },
    "credit": {
        "credit",
        "montant_credit",
        "entree",
        "amount_in",
        "montant_positif",
    },
    "montant": {"montant", "amount", "valeur"},
}


def map_headers_to_fields(norm_headers: List[str]) -> Dict[str, str]:
    """Associe les colonnes normalisées aux champs internes."""

    found: Dict[str, str] = {}
    available = set(norm_headers)
    for internal, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            normalized = normalize_header(alias)
            if normalized in available:
                found[internal] = normalized
                break
    return found

def import_operations_from_csv(path: str) -> List[OperationBancaire]:
    operations: List[OperationBancaire] = []
    dialect = detect_dialect(path)
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f, dialect=dialect)
        if not reader.fieldnames:
            raise ValueError("Aucune colonne détectée (vérifie le fichier).")
        original_headers = reader.fieldnames[:]
        norm_headers = [normalize_header(h) for h in original_headers]
        field_map = map_headers_to_fields(norm_headers)

        def get_value(field: str) -> str:
            key = field_map.get(field)
            return row_norm.get(key, "") if key else ""

        for idx, raw_row in enumerate(reader, start=2):
            try:
                row_norm = {
                    normalize_header(k): (v or "").strip()
                    for k, v in (raw_row or {}).items()
                }

                date_iso = parse_date(get_value("date_comptabilisation"))
                libelle_simpl = get_value("libelle_simplifie")
                libelle_op = get_value("libelle_operation")
                reference = get_value("reference")
                infos = get_value("informations_complementaires")
                type_operation = get_value("type_operation")
                categorie = get_value("categorie")
                sous_categorie = get_value("sous_categorie")
                debit_val = parse_amount(get_value("debit"))
                credit_val = parse_amount(get_value("credit"))
                montant_raw = get_value("montant")

                if debit_val is not None and debit_val < 0:
                    debit_val = abs(debit_val)
                if credit_val is not None and credit_val < 0:
                    credit_val = abs(credit_val)

                if debit_val is None and credit_val is None and montant_raw:
                    montant_val = parse_amount(montant_raw)
                    if montant_val is not None:
                        if montant_val < 0:
                            debit_val = abs(montant_val)
                            credit_val = None
                        elif montant_val > 0:
                            credit_val = montant_val
                            debit_val = None
                        else:
                            debit_val = credit_val = 0.0

                libelle_simpl = libelle_simpl or libelle_op

                operations.append(
                    OperationBancaire(
                        date_comptabilisation=date_iso,
                        libelle_simplifie=libelle_simpl,
                        libelle_operation=libelle_op,
                        reference=reference,
                        informations_complementaires=infos,
                        type_operation=type_operation,
                        categorie=categorie,
                        sous_categorie=sous_categorie,
                        debit=debit_val,
                        credit=credit_val,
                    )
                )
            except Exception as exc:
                preview = {
                    k: (v if v is not None else "")
                    for k, v in (raw_row or {}).items()
                }
                raise RuntimeError(
                    f"Erreur à la ligne {idx}: {exc}\n  Aperçu: {preview}"
                ) from exc
    return operations

def export_operations_to_csv(operations: List[OperationBancaire], path: str):
    fieldnames = [
        "date_comptabilisation", "libelle_simplifie", "libelle_operation",
        "reference", "informations_complementaires", "type_operation",
        "categorie", "sous_categorie", "debit", "credit"
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for op in operations:
            writer.writerow(op.to_dict_export())
