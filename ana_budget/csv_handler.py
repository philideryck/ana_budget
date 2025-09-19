"""CSV import/export helpers for banking operations."""
from __future__ import annotations

import csv
import re
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from .models import OperationBancaire
from .utils import detect_dialect, normalize_header

_HEADER_NORMALIZER = normalize_header

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
    "libelle_operation": {"libelle_operation", "details", "intitule_complet"},
    "reference": {"reference", "ref", "id_operation", "numero_operation"},
    "informations_complementaires": {
        "informations_complementaires",
        "infos",
        "information",
        "note",
        "memo",
    },
    "type_operation": {"type_operation", "type", "mode", "categorie_banque"},
    "categorie": {"categorie", "category"},
    "sous_categorie": {"sous_categorie", "sous_categ", "subcategory"},
    "debit": {"debit", "montant_debit", "sortie", "amount_out", "montant_negatif"},
    "credit": {"credit", "montant_credit", "entree", "amount_in", "montant_positif"},
    "montant": {"montant", "amount", "valeur"},
}

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

_AMOUNT_SPACES = re.compile(r"[ \u00A0]")


def map_headers_to_fields(norm_headers: Iterable[str]) -> Dict[str, str]:
    """Build mapping from internal field names to CSV columns."""
    headers_set = set(norm_headers)
    mapping: Dict[str, str] = {}
    for internal, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            normalized_alias = _HEADER_NORMALIZER(alias)
            if normalized_alias in headers_set:
                mapping[internal] = normalized_alias
                break
    return mapping


def _parse_date(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue

    cleaned = re.sub(r"[ T].*$", "", value)
    if cleaned != value:
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(cleaned, fmt).date().isoformat()
            except ValueError:
                continue
    try:
        return datetime.fromisoformat(cleaned).date().isoformat()
    except ValueError:
        return value  # Keep original if unrecognized


def _parse_amount(raw: str | float | None) -> Optional[float]:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None

    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]

    text = _AMOUNT_SPACES.sub("", text)

    if "," in text and text.count(",") == 1 and "." not in text:
        text = text.replace(",", ".")
    if "," in text and "." in text and text.rfind(",") > text.rfind("."):
        text = text.replace(".", "")
        text = text.replace(",", ".")

    text = re.sub(r"[^0-9.+-]", "", text)
    if text in {"", "+", "-"}:
        return None

    try:
        amount = float(text)
    except ValueError:
        return None
    return -abs(amount) if negative else amount


def import_operations_from_csv(path: str) -> List[OperationBancaire]:
    operations: List[OperationBancaire] = []
    dialect = detect_dialect(path)
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle, dialect=dialect)
        if not reader.fieldnames:
            raise ValueError("Aucune colonne détectée (vérifie le fichier).")

        norm_headers = [_HEADER_NORMALIZER(name) for name in reader.fieldnames]
        field_map = map_headers_to_fields(norm_headers)

        for idx, raw_row in enumerate(reader, start=2):
            try:
                normalized_row = {
                    _HEADER_NORMALIZER(key): (value or "").strip()
                    for key, value in raw_row.items()
                }

                date_val = normalized_row.get(field_map.get("date_comptabilisation", ""), "")
                lib_simpl = normalized_row.get(field_map.get("libelle_simplifie", ""), "")
                lib_op = normalized_row.get(field_map.get("libelle_operation", ""), "")
                ref = normalized_row.get(field_map.get("reference", ""), "")
                infos = normalized_row.get(field_map.get("informations_complementaires", ""), "")
                typ = normalized_row.get(field_map.get("type_operation", ""), "")
                cat = normalized_row.get(field_map.get("categorie", ""), "")
                scat = normalized_row.get(field_map.get("sous_categorie", ""), "")
                debit_raw = normalized_row.get(field_map.get("debit", ""), "")
                credit_raw = normalized_row.get(field_map.get("credit", ""), "")
                montant_raw = normalized_row.get(field_map.get("montant", ""), "")

                date_iso = _parse_date(date_val)
                debit_val = _parse_amount(debit_raw) if debit_raw else None
                credit_val = _parse_amount(credit_raw) if credit_raw else None

                if debit_val is None and credit_val is None and montant_raw:
                    montant_val = _parse_amount(montant_raw)
                    if montant_val is not None:
                        if montant_val < 0:
                            debit_val = abs(montant_val)
                            credit_val = None
                        elif montant_val > 0:
                            credit_val = montant_val
                            debit_val = None
                        else:
                            debit_val = credit_val = 0.0

                libelle_simplifie = lib_simpl or lib_op

                operations.append(
                    OperationBancaire(
                        date_comptabilisation=date_iso,
                        libelle_simplifie=libelle_simplifie,
                        libelle_operation=lib_op,
                        reference=ref,
                        informations_complementaires=infos,
                        type_operation=typ,
                        categorie=cat,
                        sous_categorie=scat,
                        debit=debit_val,
                        credit=credit_val,
                    )
                )
            except Exception as exc:  # pragma: no cover - defensive path
                preview = {key: (value or "") for key, value in (raw_row or {}).items()}
                raise RuntimeError(
                    f"Erreur à la ligne {idx}: {exc}\n  Aperçu: {preview}"
                ) from exc

    return operations


def export_operations_to_csv(operations: Iterable[OperationBancaire], path: str) -> None:
    fieldnames = [
        "date_comptabilisation",
        "libelle_simplifie",
        "libelle_operation",
        "reference",
        "informations_complementaires",
        "type_operation",
        "categorie",
        "sous_categorie",
        "debit",
        "credit",
    ]
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for operation in operations:
            writer.writerow(operation.to_dict_export())
