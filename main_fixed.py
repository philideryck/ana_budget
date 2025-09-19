2#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bank CSV Importer — robust, tolerant parser + CLI & non-interactive modes.

Usage (interactive menu):
    python main_fixed.py

Usage (batch import + export):
    python main_fixed.py --in input.csv --out cleaned.csv

Key features:
- Auto-detect delimiter (",", ";", "|", TAB) with safe fallback.
- Normalize headers (lowercase, accents removed, spaces/punct -> "_").
- Flexible header aliases (date/libellé/montant/debit/credit/etc.).
- Multi-format date parsing -> ISO yyyy-mm-dd.
- Amount parsing tolerant to FR (comma decimal), thousand separators, parentheses negatives.
- Merges single "montant" column into debit/credit if needed.
- Clear errors with line numbers and a 1-line preview.
"""

import argparse
import csv
import os
import re
import sys
from dataclasses import asdict
from datetime import datetime
from typing import List, Optional, Tuple

# --- Import des fonctions utilitaires ---
from utils import strip_accents, normalize_header, detect_dialect

_DATE_FORMATS = [
    "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y",
    "%d %m %Y", "%d %b %Y", "%d %B %Y", "%Y/%m/%d",
]

def parse_date(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except Exception:
            pass
    s2 = re.sub(r"[ T].*$", "", s)
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s2, fmt).date().isoformat()
        except Exception:
            pass
    try:
        return datetime.fromisoformat(s2).date().isoformat()
    except Exception:
        return s  # keep raw if unknown

_AMOUNT_SEP_RE = re.compile(r"[ \u00A0]")

def parse_amount(raw: str) -> Optional[float]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]
    s = _AMOUNT_SEP_RE.sub("", s)
    if "," in s and s.count(",") == 1 and s.count(".") == 0:
        s = s.replace(",", ".")
    if "," in s and "." in s and s.rfind(",") > s.rfind("."):
        s = s.replace(".", "")
        s = s.replace(",", ".")
    s = re.sub(r"[^\d\.\-+]", "", s)
    if s in ("", "-", "+"):
        return None
    try:
        val = float(s)
        return -abs(val) if negative else val
    except ValueError:
        return None

# ---------------------- Model ----------------------

# --- Import de la dataclass ---
from models import OperationBancaire

# Header aliases
HEADER_ALIASES = {
    "date_comptabilisation": {"date_comptabilisation", "date", "date_operation", "date_valeur", "date_de_comptabilisation"},
    "libelle_simplifie": {"libelle_simplifie", "libelle_simplifiee", "libelle", "intitule", "description"},
    "libelle_operation": {"libelle_operation", "details", "intitule_complet"},
    "reference": {"reference", "ref", "id_operation", "numero_operation"},
    "informations_complementaires": {"informations_complementaires", "infos", "information", "note", "memo"},
    "type_operation": {"type_operation", "type", "mode", "categorie_banque"},
    "categorie": {"categorie", "category"},
    "sous_categorie": {"sous_categorie", "sous_categ", "subcategory"},
    "debit": {"debit", "montant_debit", "sortie", "amount_out", "montant_negatif"},
    "credit": {"credit", "montant_credit", "entree", "amount_in", "montant_positif"},
    "montant": {"montant", "amount", "valeur"},
}

def map_headers_to_fields(norm_headers: List[str]) -> dict:
    set_headers = set(norm_headers)
    mapping = {}
    for internal, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            n = normalize_header(alias)
            if n in set_headers:
                mapping[internal] = n
                break
    return mapping

# ---------------------- I/O ----------------------

# --- Import des fonctions d'I/O CSV ---
from csv_handler import import_operations_from_csv, export_operations_to_csv

# ---------------------- CLI ----------------------

class MenuImport:
    def __init__(self):
        self.operations: List[OperationBancaire] = []

    def afficher_menu(self):
        print("\n" + "="*64)
        print("    GESTIONNAIRE D'IMPORTS - OPÉRATIONS BANCAIRES")
        print("="*64)
        print("1. Importer un fichier CSV")
        print("2. Lister les fichiers CSV disponibles")
        print("3. Afficher les opérations chargées")
        print("4. Exporter les opérations")
        print("5. Vider les opérations")
        print("0. Quitter")
        print("-"*64)

    def lister_fichiers_csv(self):
        print("\n📁 Fichiers CSV trouvés:")
        fichiers = [f for f in os.listdir(".") if f.lower().endswith(".csv")]
        if fichiers:
            for i, f in enumerate(fichiers, 1):
                try:
                    taille = os.path.getsize(f)
                except Exception:
                    taille = 0
                print(f"  {i}. {f} ({taille} octets)")
        else:
            print("  Aucun fichier CSV trouvé dans le répertoire courant")
        return fichiers

    def importer_fichier(self):
        print("\n📥 IMPORT DE FICHIER")
        fichiers = self.lister_fichiers_csv()
        if not fichiers:
            input("\nAppuyez sur Entrée pour continuer..."); return

        choix = input("\nNom du fichier à importer (ou numéro): ").strip()
        if not choix:
            print("❌ Saisie vide"); input("\nAppuyez sur Entrée pour continuer..."); return

        if choix.isdigit():
            idx = int(choix) - 1
            if 0 <= idx < len(fichiers):
                nom = fichiers[idx]
            else:
                print("❌ Numéro invalide"); input("\nAppuyez sur Entrée pour continuer..."); return
        else:
            nom = choix if choix.lower().endswith(".csv") else choix + ".csv"

        if not os.path.exists(nom):
            print(f"❌ Fichier '{nom}' introuvable"); input("\nAppuyez sur Entrée pour continuer..."); return

        try:
            nouvelles = import_operations_from_csv(nom)
        except Exception as e:
            print(str(e)); input("\nAppuyez sur Entrée pour continuer..."); return

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

    def afficher_operations(self):
        n = len(self.operations)
        print(f"\n📋 OPÉRATIONS CHARGÉES ({n})")
        if n == 0:
            print("Aucune opération en mémoire")
            input("\nAppuyez sur Entrée pour continuer..."); return

        choix = input("\nAffichage: (1) Aperçu (10 premières) | (2) Toutes | (3) Détail paginé : ").strip()

        if choix == "2":
            print("\n" + "="*110)
            print(f"{'DATE':<12} | {'LIBELLÉ':<36} | {'CATÉGORIE':<18} | {'DÉBIT':>12} | {'CRÉDIT':>12}")
            print("-"*110)
            for op in self.operations:
                date_str = (op.date_comptabilisation or "")[:10]
                lib = op.libelle_simplifie or op.libelle_operation or ""
                lib = (lib[:33] + "...") if len(lib) > 36 else lib
                cat = op.categorie or ""
                cat = (cat[:15] + "...") if len(cat) > 18 else cat
                deb = f"{op.debit:,.2f}".replace(",", " ").replace(".", ",") if op.debit is not None else ""
                cre = f"{op.credit:,.2f}".replace(",", " ").replace(".", ",") if op.credit is not None else ""
                print(f"{date_str:<12} | {lib:<36} | {cat:<18} | {deb:>12} | {cre:>12}")
            print("="*110)
            d, c, s = self._totaux()
            fmt = lambda x: f"{x:,.2f}".replace(",", " ").replace(".", ",")
            print(f"Totaux  Débit={fmt(d)} | Crédit={fmt(c)} | Solde={fmt(s)}")

        elif choix == "3":
            per_page = 8
            page = 0
            while True:
                start = page * per_page
                end = min(start + per_page, n)
                print(f"\n📄 Page {page+1} — Opérations {start+1} à {end}/{n}")
                print("-"*80)
                for i in range(start, end):
                    op = self.operations[i]
                    print(f"\n🔹 #{i+1}")
                    print(f"   Date        : {op.date_comptabilisation}")
                    print(f"   Libellé     : {op.libelle_simplifie or op.libelle_operation}")
                    print(f"   Catégorie   : {op.categorie} / {op.sous_categorie}")
                    print(f"   Montant     : Débit={op.debit} | Crédit={op.credit}")
                    print(f"   Type        : {op.type_operation}")
                    print(f"   Référence   : {op.reference}")
                    if op.informations_complementaires:
                        print(f"   Informations: {op.informations_complementaires}")

                if end >= n and start == 0:
                    break
                nav = input("\n(s)uivant | (p)récédent | (q)uitter | (numéro de page): ").strip().lower()
                if nav == "s" and end < n:
                    page += 1
                elif nav == "p" and page > 0:
                    page -= 1
                elif nav == "q":
                    break
                elif nav.isdigit():
                    newp = int(nav) - 1
                    if 0 <= newp <= (n - 1) // per_page:
                        page = newp
        else:
            print("-"*80)
            for i, op in enumerate(self.operations[:10], 1):
                print(f"{i:2d}. {op.date_comptabilisation or 'N/A'} - {(op.libelle_simplifie or op.libelle_operation or '—')[:60]} "
                      f"- Débit: {op.debit if op.debit is not None else ''} - Crédit: {op.credit if op.credit is not None else ''}")
            if n > 10:
                print(f"... et {n - 10} autres opérations")
            d, c, s = self._totaux()
            fmt = lambda x: f"{x:,.2f}".replace(",", " ").replace(".", ",")
            print("-"*80)
            print(f"Totaux  Débit={fmt(d)} | Crédit={fmt(c)} | Solde={fmt(s)}")

        input("\nAppuyez sur Entrée pour continuer...")

    def exporter_operations(self):
        if not self.operations:
            print("\n❌ Aucune opération à exporter")
            input("Appuyez sur Entrée pour continuer..."); return

        print(f"\n📤 EXPORT ({len(self.operations)} opérations)")
        nom = input("Nom du fichier de sortie (sans .csv): ").strip()
        if not nom:
            nom = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        path = nom + ".csv"
        try:
            export_operations_to_csv(self.operations, path)
            print(f"✅ Export réussi vers {path}")
        except Exception as e:
            print(f"❌ Erreur lors de l'export: {e}")
        input("\nAppuyez sur Entrée pour continuer...")

    def vider_operations(self):
        if not self.operations:
            print("\n💡 Aucune opération en mémoire")
            input("Appuyez sur Entrée pour continuer..."); return
        confirmation = input(f"\n⚠️  Vider les {len(self.operations)} opérations en mémoire ? (oui/non): ").strip().lower()
        if confirmation in {"oui", "o", "yes", "y"}:
            self.operations.clear()
            print("✅ Opérations supprimées")
        else:
            print("❌ Annulé")
        input("Appuyez sur Entrée pour continuer...")

    def executer(self):
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
            elif choix == "0":
                print("\n👋 Au revoir!"); break
            else:
                print("\n❌ Choix invalide"); input("Appuyez sur Entrée pour continuer...")

def run_batch(input_path: str, output_path: str):
    ops = import_operations_from_csv(input_path)
    export_operations_to_csv(ops, output_path)
    print(f"✅ Import '{input_path}' -> Export '{output_path}' ({len(ops)} opérations)")

# ---------------------- Entry ----------------------

def main():
    parser = argparse.ArgumentParser(description="Import/clean bank CSVs.")
    parser.add_argument("--in", dest="input_path", help="Chemin du fichier CSV en entrée")
    parser.add_argument("--out", dest="output_path", help="Chemin du CSV nettoyé en sortie")
    args = parser.parse_args()

    if args.input_path and args.output_path:
        if not os.path.exists(args.input_path):
            print(f"❌ Fichier introuvable: {args.input_path}")
            sys.exit(1)
        try:
            run_batch(args.input_path, args.output_path)
        except Exception as e:
            print(f"❌ Erreur: {e}")
            sys.exit(2)
        sys.exit(0)

    # Interactive mode
    MenuImport().executer()

if __name__ == "__main__":
    main()
