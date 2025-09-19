"""Utilities for aggregating and displaying banking operations."""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .models import OperationBancaire


def agreger_par_categorie(operations: Iterable[OperationBancaire]):
    """Agrège les montants par catégorie."""
    agregation = defaultdict(lambda: {"total_debit": 0.0, "total_credit": 0.0, "nombre": 0})

    for op in operations:
        categorie = op.categorie or "Non catégorisé"

        if op.debit:
            agregation[categorie]["total_debit"] += op.debit
        if op.credit:
            agregation[categorie]["total_credit"] += op.credit

        agregation[categorie]["nombre"] += 1

    return dict(agregation)


def agreger_par_sous_categorie(operations: Iterable[OperationBancaire]):
    """Agrège les montants par sous-catégorie."""
    agregation = defaultdict(lambda: {"total_debit": 0.0, "total_credit": 0.0, "nombre": 0})

    for op in operations:
        sous_categorie = op.sous_categorie or "Non spécifié"

        if op.debit:
            agregation[sous_categorie]["total_debit"] += op.debit
        if op.credit:
            agregation[sous_categorie]["total_credit"] += op.credit

        agregation[sous_categorie]["nombre"] += 1

    return dict(agregation)


def _fmt(value: float) -> str:
    return f"{value:.2f}" if value else ""


def _fmt_signed(value: float) -> str:
    return f"{value:+.2f}"


def afficher_agregation(operations: Iterable[OperationBancaire]):
    """Affiche l'agrégation par catégorie."""
    operations = list(operations)
    if not operations:
        print("Aucune opération")
        return

    agregation = agreger_par_categorie(operations)

    print("\nAGRÉGATION PAR CATÉGORIE")
    print("=" * 80)
    print(f"{'CATÉGORIE':<25} | {'NOMBRE':>8} | {'DÉBIT':>12} | {'CRÉDIT':>12} | {'SOLDE':>12}")
    print("-" * 80)

    items = sorted(
        agregation.items(),
        key=lambda item: item[1]["total_credit"] - item[1]["total_debit"],
        reverse=True,
    )

    total_debit = total_credit = 0.0

    for categorie, data in items:
        solde = data["total_credit"] - data["total_debit"]
        print(
            f"{categorie[:24]:<25} | {data['nombre']:>8} | {_fmt(data['total_debit']):>12} | "
            f"{_fmt(data['total_credit']):>12} | {_fmt_signed(solde):>12}"
        )
        total_debit += data["total_debit"]
        total_credit += data["total_credit"]

    print("=" * 80)
    total_solde = total_credit - total_debit
    print(
        f"{'TOTAL':<25} | {len(operations):>8} | {total_debit:>12.2f} | {total_credit:>12.2f} | "
        f"{total_solde:>+12.2f}"
    )


def afficher_agregation_sous_categorie(operations: Iterable[OperationBancaire]):
    """Affiche l'agrégation par sous-catégorie."""
    operations = list(operations)
    if not operations:
        print("Aucune opération")
        return

    agregation = agreger_par_sous_categorie(operations)

    print("\nAGRÉGATION PAR SOUS-CATÉGORIE")
    print("=" * 80)
    print(f"{'SOUS-CATÉGORIE':<25} | {'NOMBRE':>8} | {'DÉBIT':>12} | {'CRÉDIT':>12} | {'SOLDE':>12}")
    print("-" * 80)

    items = sorted(
        agregation.items(),
        key=lambda item: item[1]["total_credit"] - item[1]["total_debit"],
        reverse=True,
    )

    total_debit = total_credit = 0.0

    for sous_categorie, data in items:
        solde = data["total_credit"] - data["total_debit"]
        print(
            f"{sous_categorie[:24]:<25} | {data['nombre']:>8} | {_fmt(data['total_debit']):>12} | "
            f"{_fmt(data['total_credit']):>12} | {_fmt_signed(solde):>12}"
        )
        total_debit += data["total_debit"]
        total_credit += data["total_credit"]

    print("=" * 80)
    total_solde = total_credit - total_debit
    print(
        f"{'TOTAL':<25} | {len(operations):>8} | {total_debit:>12.2f} | {total_credit:>12.2f} | "
        f"{total_solde:>+12.2f}"
    )


def afficher_agregations_completes(operations: Iterable[OperationBancaire]):
    """Affiche les agrégations par catégorie et sous-catégorie."""
    operations = list(operations)
    if not operations:
        print("Aucune opération")
        return

    categories_data: dict[str, dict[str, object]] = defaultdict(
        lambda: {"operations": [], "sous_categories": defaultdict(list)}
    )

    for op in operations:
        categorie = op.categorie or "Non catégorisé"
        sous_categorie = op.sous_categorie or "Non spécifié"
        categories_data[categorie]["operations"].append(op)
        categories_data[categorie]["sous_categories"][sous_categorie].append(op)

    def calculer_agregation(ops_list):
        total_debit = sum(op.debit or 0.0 for op in ops_list)
        total_credit = sum(op.credit or 0.0 for op in ops_list)
        return {
            "total_debit": total_debit,
            "total_credit": total_credit,
            "solde": total_credit - total_debit,
            "nombre": len(ops_list),
        }

    print("\nAGRÉGATION PAR CATÉGORIES ET SOUS-CATÉGORIES")
    print("=" * 90)
    print(
        f"{'CATÉGORIE / SOUS-CATÉGORIE':<35} | {'NOMBRE':>8} | {'DÉBIT':>12} | "
        f"{'CRÉDIT':>12} | {'SOLDE':>12}"
    )
    print("=" * 90)

    total_debit_global = total_credit_global = 0.0

    categories_avec_soldes = []
    for categorie, data in categories_data.items():
        agregation_cat = calculer_agregation(data["operations"])
        categories_avec_soldes.append((categorie, agregation_cat, data))

    categories_avec_soldes.sort(key=lambda item: item[1]["solde"], reverse=True)

    for categorie, agregation_cat, data in categories_avec_soldes:
        print(
            f"📁 {categorie[:30]:<33} | {agregation_cat['nombre']:>8} | "
            f"{_fmt(agregation_cat['total_debit']):>12} | { _fmt(agregation_cat['total_credit']):>12} | "
            f"{_fmt_signed(agregation_cat['solde']):>12}"
        )

        sous_categories_avec_soldes = []
        for sous_cat, ops_sous in data["sous_categories"].items():
            sous_categories_avec_soldes.append((sous_cat, calculer_agregation(ops_sous)))

        sous_categories_avec_soldes.sort(key=lambda item: item[1]["solde"], reverse=True)

        for sous_categorie, agregation_sous in sous_categories_avec_soldes:
            print(
                f"  ├─ {sous_categorie[:28]:<31} | {agregation_sous['nombre']:>8} | "
                f"{_fmt(agregation_sous['total_debit']):>12} | { _fmt(agregation_sous['total_credit']):>12} | "
                f"{_fmt_signed(agregation_sous['solde']):>12}"
            )

        print("-" * 90)

        total_debit_global += agregation_cat["total_debit"]
        total_credit_global += agregation_cat["total_credit"]

    print("=" * 90)
    total_solde_global = total_credit_global - total_debit_global
    print(
        f"{'TOTAL GÉNÉRAL':<35} | {len(operations):>8} | {total_debit_global:>12.2f} | "
        f"{total_credit_global:>12.2f} | {total_solde_global:>+12.2f}"
    )

    nb_categories = len(categories_data)
    nb_sous_categories = sum(len(data["sous_categories"]) for data in categories_data.values())
    print(f"\n📊 {nb_categories} catégories, {nb_sous_categories} sous-catégories")
