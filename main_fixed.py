#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gestionnaire d'import pour relevés bancaires."""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from typing import Tuple

from ana_budget import (
    OperationBancaire,
    afficher_agregations_completes,
    export_operations_to_csv,
    import_operations_from_csv,
)


def _format_float(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")


class MenuImport:
    """Menu interactif pour l'import, l'affichage et l'export."""

    def __init__(self) -> None:
        self.operations: list[OperationBancaire] = []

    def afficher_menu(self) -> None:
        print("\n" + "=" * 64)
        print("    GESTIONNAIRE D'IMPORTS - OPÉRATIONS BANCAIRES")
        print("=" * 64)
        print("1. Importer un fichier CSV")
        print("2. Lister les fichiers CSV disponibles")
        print("3. Afficher les opérations chargées")
        print("4. Exporter les opérations")
        print("5. Vider les opérations")
        print("6. Agrégations par catégories/sous-catégories")
        print("0. Quitter")
        print("-" * 64)

    def lister_fichiers_csv(self) -> list[str]:
        print("\n📁 Fichiers CSV trouvés:")
        fichiers = [f for f in os.listdir(".") if f.lower().endswith(".csv")]
        if fichiers:
            for i, fichier in enumerate(fichiers, 1):
                try:
                    taille = os.path.getsize(fichier)
                except OSError:
                    taille = 0
                print(f"  {i}. {fichier} ({taille} octets)")
        else:
            print("  Aucun fichier CSV trouvé dans le répertoire courant")
        return fichiers

    def importer_fichier(self) -> None:
        print("\n📥 IMPORT DE FICHIER")
        fichiers = self.lister_fichiers_csv()
        if not fichiers:
            input("\nAppuyez sur Entrée pour continuer...")
            return

        choix = input("\nNom du fichier à importer (ou numéro): ").strip()
        if not choix:
            print("❌ Saisie vide")
            input("\nAppuyez sur Entrée pour continuer...")
            return

        if choix.isdigit():
            idx = int(choix) - 1
            if 0 <= idx < len(fichiers):
                nom = fichiers[idx]
            else:
                print("❌ Numéro invalide")
                input("\nAppuyez sur Entrée pour continuer...")
                return
        else:
            nom = choix if choix.lower().endswith(".csv") else f"{choix}.csv"

        if not os.path.exists(nom):
            print(f"❌ Fichier '{nom}' introuvable")
            input("\nAppuyez sur Entrée pour continuer...")
            return

        try:
            nouvelles = import_operations_from_csv(nom)
        except Exception as exc:  # pragma: no cover - garde-fou
            print(str(exc))
            input("\nAppuyez sur Entrée pour continuer...")
            return

        if nouvelles:
            self.operations.extend(nouvelles)
            print(f"📊 Total en mémoire: {len(self.operations)} opérations")
        else:
            print("ℹ️ Aucune opération importée")

        input("\nAppuyez sur Entrée pour continuer...")

    def _totaux(self) -> Tuple[float, float, float]:
        debit = sum(op.debit or 0.0 for op in self.operations)
        credit = sum(op.credit or 0.0 for op in self.operations)
        solde = credit - debit
        return debit, credit, solde

    def afficher_operations(self) -> None:
        n = len(self.operations)
        print(f"\n📋 OPÉRATIONS CHARGÉES ({n})")
        if n == 0:
            print("Aucune opération en mémoire")
            input("\nAppuyez sur Entrée pour continuer...")
            return

        choix = input(
            "\nAffichage: (1) Aperçu (10 premières) | (2) Toutes | (3) Détail paginé : "
        ).strip()

        if choix == "2":
            self._afficher_table_complete()
        elif choix == "3":
            self._afficher_pagine()
        else:
            self._afficher_apercu()

        input("\nAppuyez sur Entrée pour continuer...")

    def _afficher_apercu(self) -> None:
        n = len(self.operations)
        print("-" * 80)
        for i, op in enumerate(self.operations[:10], 1):
            debit = op.debit if op.debit is not None else ""
            credit = op.credit if op.credit is not None else ""
            libelle = (op.libelle_simplifie or op.libelle_operation or "—")[:60]
            print(
                f"{i:2d}. {op.date_comptabilisation or 'N/A'} - {libelle} "
                f"- Débit: {debit} - Crédit: {credit}"
            )
        if n > 10:
            print(f"... et {n - 10} autres opérations")
        self._afficher_totaux()

    def _afficher_table_complete(self) -> None:
        print("\n" + "=" * 110)
        print(
            f"{'DATE':<12} | {'LIBELLÉ':<36} | {'CATÉGORIE':<18} | {'DÉBIT':>12} | {'CRÉDIT':>12}"
        )
        print("-" * 110)
        for op in self.operations:
            date_str = (op.date_comptabilisation or "")[:10]
            lib = op.libelle_simplifie or op.libelle_operation or ""
            lib = (lib[:33] + "...") if len(lib) > 36 else lib
            cat = op.categorie or ""
            cat = (cat[:15] + "...") if len(cat) > 18 else cat
            print(
                f"{date_str:<12} | {lib:<36} | {cat:<18} | {_format_float(op.debit):>12} | "
                f"{_format_float(op.credit):>12}"
            )
        print("=" * 110)
        self._afficher_totaux()

    def _afficher_pagine(self) -> None:
        n = len(self.operations)
        per_page = 8
        page = 0
        while True:
            start = page * per_page
            end = min(start + per_page, n)
            print(f"\n📄 Page {page + 1} — Opérations {start + 1} à {end}/{n}")
            print("-" * 80)
            for i in range(start, end):
                op = self.operations[i]
                print(f"\n🔹 #{i + 1}")
                print(f"   Date        : {op.date_comptabilisation}")
                print(
                    "   Libellé     : "
                    f"{op.libelle_simplifie or op.libelle_operation or ''}"
                )
                print(f"   Catégorie   : {op.categorie} / {op.sous_categorie}")
                print(f"   Montant     : Débit={op.debit} | Crédit={op.credit}")
                print(f"   Type        : {op.type_operation}")
                print(f"   Référence   : {op.reference}")
                if op.informations_complementaires:
                    print(f"   Informations: {op.informations_complementaires}")

            if end >= n and start == 0:
                break
            nav = input(
                "\n(s)uivant | (p)récédent | (q)uitter | (numéro de page): "
            ).strip().lower()
            if nav == "s" and end < n:
                page += 1
            elif nav == "p" and page > 0:
                page -= 1
            elif nav == "q":
                break
            elif nav.isdigit():
                new_page = int(nav) - 1
                if 0 <= new_page <= (n - 1) // per_page:
                    page = new_page

        self._afficher_totaux()

    def _afficher_totaux(self) -> None:
        debit, credit, solde = self._totaux()
        print("-" * 80)
        print(
            f"Totaux  Débit={_format_float(debit)} | Crédit={_format_float(credit)} | "
            f"Solde={_format_float(solde)}"
        )

    def exporter_operations(self) -> None:
        if not self.operations:
            print("\n❌ Aucune opération à exporter")
            input("Appuyez sur Entrée pour continuer...")
            return

        print(f"\n📤 EXPORT ({len(self.operations)} opérations)")
        nom = input("Nom du fichier de sortie (sans .csv): ").strip()
        if not nom:
            nom = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        path = f"{nom}.csv"
        try:
            export_operations_to_csv(self.operations, path)
            print(f"✅ Export réussi vers {path}")
        except Exception as exc:  # pragma: no cover - garde-fou
            print(f"❌ Erreur lors de l'export: {exc}")
        input("\nAppuyez sur Entrée pour continuer...")

    def vider_operations(self) -> None:
        if not self.operations:
            print("\n💡 Aucune opération en mémoire")
            input("Appuyez sur Entrée pour continuer...")
            return
        confirmation = input(
            f"\n⚠️  Vider les {len(self.operations)} opérations en mémoire ? (oui/non): "
        ).strip().lower()
        if confirmation in {"oui", "o", "yes", "y"}:
            self.operations.clear()
            print("✅ Opérations supprimées")
        else:
            print("❌ Annulé")
        input("Appuyez sur Entrée pour continuer...")

    def afficher_agregations(self) -> None:
        if not self.operations:
            print("\n💡 Aucune opération en mémoire")
        else:
            afficher_agregations_completes(self.operations)
        input("\nAppuyez sur Entrée pour continuer...")

    def executer(self) -> None:
        while True:
            self.afficher_menu()
            choix = input("Votre choix: ").strip()
            if choix == "1":
                self.importer_fichier()
            elif choix == "2":
                self.lister_fichiers_csv()
                input("\nAppuyez sur Entrée pour continuer...")
            elif choix == "3":
                self.afficher_operations()
            elif choix == "4":
                self.exporter_operations()
            elif choix == "5":
                self.vider_operations()
            elif choix == "6":
                self.afficher_agregations()
            elif choix == "0":
                print("\n👋 Au revoir !")
                break
            else:
                print("\n❌ Choix invalide")
                input("Appuyez sur Entrée pour continuer...")


def run_batch(input_path: str, output_path: str) -> None:
    operations = import_operations_from_csv(input_path)
    export_operations_to_csv(operations, output_path)
    print(
        f"✅ Import '{input_path}' -> Export '{output_path}' ({len(operations)} opérations)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Import/clean bank CSVs.")
    parser.add_argument("--in", dest="input_path", help="Chemin du fichier CSV en entrée")
    parser.add_argument(
        "--out", dest="output_path", help="Chemin du CSV nettoyé en sortie"
    )
    args = parser.parse_args()

    if args.input_path and args.output_path:
        if not os.path.exists(args.input_path):
            print(f"❌ Fichier introuvable: {args.input_path}")
            sys.exit(1)
        try:
            run_batch(args.input_path, args.output_path)
        except Exception as exc:  # pragma: no cover - garde-fou
            print(f"❌ Erreur: {exc}")
            sys.exit(2)
        sys.exit(0)

    MenuImport().executer()


if __name__ == "__main__":
    main()
