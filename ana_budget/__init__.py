"""Core package for banking CSV analysis."""

from .models import OperationBancaire
from .csv_handler import (
    import_operations_from_csv,
    export_operations_to_csv,
    HEADER_ALIASES,
    map_headers_to_fields,
)
from .aggregations import (
    agreger_par_categorie,
    agreger_par_sous_categorie,
    afficher_agregation,
    afficher_agregation_sous_categorie,
    afficher_agregations_completes,
)

__all__ = [
    "OperationBancaire",
    "import_operations_from_csv",
    "export_operations_to_csv",
    "HEADER_ALIASES",
    "map_headers_to_fields",
    "agreger_par_categorie",
    "agreger_par_sous_categorie",
    "afficher_agregation",
    "afficher_agregation_sous_categorie",
    "afficher_agregations_completes",
]
