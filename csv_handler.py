import csv
from typing import List
from models import OperationBancaire
from utils import normalize_header, detect_dialect

def import_operations_from_csv(path: str) -> List[OperationBancaire]:
    operations: List[OperationBancaire] = []
    dialect = detect_dialect(path)
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f, dialect=dialect)
        if not reader.fieldnames:
            raise ValueError("Aucune colonne détectée (vérifie le fichier).")
        original_headers = reader.fieldnames[:]
        norm_headers = [normalize_header(h) for h in original_headers]
        # Le mapping des champs doit être importé ou dupliqué ici
        # ...
        # La logique d'import doit être complétée selon le mapping
        # ...
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
