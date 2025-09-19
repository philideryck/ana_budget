#!/usr/bin/env python3
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
- Aggregation by category and subcategory.
"""

import argparse
import csv
import os
import re
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Optional, Tuple

# ---------------------- Utils ----------------------

def strip_accents(s: str) -> str:
    if s is None:
        return ""
    return "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn")

def normalize_header(h: str) -> str:
    h = strip_accents(h).lower().strip()
    h = re.sub(r"[^\w]+", "_", h)  # spaces/punct -> underscore
    h = re.sub(r"_+", "_", h).strip("_")
    return h

def detect_dialect(path: str) -> csv.Dialect:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        sample = f.read(4096)
    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample, delimiters=";,|\t,")
        dialect.doublequote = True
        dialect.skipinitialspace = True
        return dialect
    except Exception:
        class SemiColon(csv.Dialect):
            delimiter = ";"
            quotechar = '"'
            doublequote = True
            skipinitialspace = True
            lineterminator = "\n"
            quoting = csv.QUOTE_MINIMAL
        return SemiColon

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

# ---------------------- Aggregation ----------------------

def agreger_par_categorie(operations):
    """Agrège les montants par catégorie (ex: Carrefour, PAYPAL...)"""
    agregation = defaultdict(lambda: {'total_debit': 0.0, 'total_credit': 0.0, 'nombre': 0})
    
    for op in operations:
        categorie = op.categorie or "Non catégorisé"
        
        if op.debit:
            agregation[categorie]['total_debit'] += op.debit
        if op.credit:
            agregation[categorie]['total_credit'] += op.credit
            
        agregation[categorie]['nombre'] += 1
    
    return dict(agregation)

def agreger_par_sous_categorie(operations):
    """Agrège les montants par sous-catégorie"""
    agregation = defaultdict(lambda: {'total_debit': 0.0, 'total_credit': 0.0, 'nombre': 0})
    
    for op in operations:
        sous_categorie = op.sous_categorie or "Non spécifié"
        
        if op.debit:
            agregation[sous_categorie]['total_debit'] += op.debit
        if op.credit:
            agregation[sous_categorie]['total_credit'] += op.credit
            
        agregation[sous_categorie]['nombre'] += 1
    
    return dict(agregation)

def afficher_agregation(operations):
    """Affiche l'agrégation par catégorie"""
    if not operations:
        print("Aucune opération")
        return
        
    agregation = agreger_par_categorie(operations)
    
    print("\nAGRÉGATION PAR CATÉGORIE")
    print("=" * 80)
    print(f"{'CATÉGORIE':<25} | {'NOMBRE':>8} | {'DÉBIT':>12} | {'CRÉDIT':>12} | {'SOLDE':>12}")
    print("-" * 80)
    
    # Tri par solde décroissant
    items = sorted(agregation.items(), key=lambda x: x[1]['total_credit'] - x[1]['total_debit'], reverse=True)
    
    total_debit = total_credit = 0
    
    for categorie, data in items:
        solde = data['total_credit'] - data['total_debit']
        
        debit_str = f"{data['total_debit']:.2f}" if data['total_debit'] > 0 else ""
        credit_str = f"{data['total_credit']:.2f}" if data['total_credit'] > 0 else ""
        solde_str = f"{solde:+.2f}"
        
        print(f"{categorie[:24]:<25} | {data['nombre']:>8} | {debit_str:>12} | {credit_str:>12} | {solde_str:>12}")
        
        total_debit += data['total_debit']
        total_credit += data['total_credit']
    
    print("=" * 80)
    total_solde = total_credit - total_debit
    print(f"{'TOTAL':<25} | {len(operations):>8} | {total_debit:>12.2f} | {total_credit:>12.2f} | {total_solde:>+12.2f}")

def afficher_agregation_sous_categorie(operations):
    """Affiche l'agrégation par sous-catégorie"""
    if not operations:
        print("Aucune opération")
        return
        
    agregation = agreger_par_sous_categorie(operations)
    
    print("\nAGRÉGATION PAR SOUS-CATÉGORIE")
    print("=" * 80)
    print(f"{'SOUS-CATÉGORIE':<25} | {'NOMBRE':>8} | {'DÉBIT':>12} | {'CRÉDIT':>12} | {'SOLDE':>12}")
    print("-" * 80)
    
    # Tri par solde décroissant
    items = sorted(agregation.items(), key=lambda x: x[1]['total_credit'] - x[1]['total_debit'], reverse=True)
    
    total_debit = total_credit = 0
    
    for sous_categorie, data in items:
        solde = data['total_credit'] - data['total_debit']
        
        debit_str = f"{data['total_debit']:.2f}" if data['total_debit'] > 0 else ""
        credit_str = f"{data['total_credit']:.2f}" if data['total_credit'] > 0 else ""
        solde_str = f"{solde:+.2f}"
        
        print(f"{sous_categorie[:24]:<25} | {data['nombre']:>8} | {debit_str:>12} | {credit_str:>12} | {solde_str:>12}")
        
        total_debit += data['total_debit']
        total_credit += data['total_credit']
    
    print("=" * 80)
    total_solde = total_credit - total_debit
    print(f"{'TOTAL':<25} | {len(operations):>8} | {total_debit:>12.2f} | {total_credit:>12.2f} | {total_solde:>+12.2f}")

def afficher_agregations_completes(operations):
    """Affiche les agrégations organisées par catégorie et sous-catégorie avec totaux cohérents"""
    if not operations:
        print("Aucune opération")
        return
    
    # Organiser les opérations par catégorie et sous-catégorie
    categories_data = defaultdict(lambda: {
        'operations': [],
        'sous_categories': defaultdict(list)
    })
    
    # Regrouper les opérations
    for op in operations:
        categorie = op.categorie or "Non catégorisé"
        sous_categorie = op.sous_categorie or "Non spécifié"
        
        categories_data[categorie]['operations'].append(op)
        categories_data[categorie]['sous_categories'][sous_categorie].append(op)
    
    # Calculer les agrégations
    def calculer_agregation(ops_list):
        total_debit = sum(op.debit or 0.0 for op in ops_list)
        total_credit = sum(op.credit or 0.0 for op in ops_list)
        return {
            'total_debit': total_debit,
            'total_credit': total_credit,
            'solde': total_credit - total_debit,
            'nombre': len(ops_list)
        }
    
    print("\nAGRÉGATION PAR CATÉGORIES ET SOUS-CATÉGORIES")
    print("=" * 90)
    print(f"{'CATÉGORIE / SOUS-CATÉGORIE':<35} | {'NOMBRE':>8} | {'DÉBIT':>12} | {'CRÉDIT':>12} | {'SOLDE':>12}")
    print("=" * 90)
    
    total_debit_global = total_credit_global = 0
    
    # Trier les catégories par solde décroissant
    categories_avec_soldes = []
    for categorie, data in categories_data.items():
        agregation_cat = calculer_agregation(data['operations'])
        categories_avec_soldes.append((categorie, agregation_cat, data))
    
    categories_avec_soldes.sort(key=lambda x: x[1]['solde'], reverse=True)
    
    for categorie, agregation_cat, data in categories_avec_soldes:
        # Afficher la catégorie principale
        debit_str = f"{agregation_cat['total_debit']:.2f}" if agregation_cat['total_debit'] > 0 else ""
        credit_str = f"{agregation_cat['total_credit']:.2f}" if agregation_cat['total_credit'] > 0 else ""
        solde_str = f"{agregation_cat['solde']:+.2f}"
        
        print(f"📁 {categorie[:30]:<33} | {agregation_cat['nombre']:>8} | {debit_str:>12} | {credit_str:>12} | {solde_str:>12}")
        
        # Afficher les sous-catégories
        if len(data['sous_categories']) > 0:
            # Trier les sous-catégories par solde
            sous_categories_avec_soldes = []
            for sous_cat, ops_sous in data['sous_categories'].items():
                agregation_sous = calculer_agregation(ops_sous)
                sous_categories_avec_soldes.append((sous_cat, agregation_sous))
            
            sous_categories_avec_soldes.sort(key=lambda x: x[1]['solde'], reverse=True)
            
            for sous_categorie, agregation_sous in sous_categories_avec_soldes:
                debit_str_sous = f"{agregation_sous['total_debit']:.2f}" if agregation_sous['total_debit'] > 0 else ""
                credit_str_sous = f"{agregation_sous['total_credit']:.2f}" if agregation_sous['total_credit'] > 0 else ""
                solde_str_sous = f"{agregation_sous['solde']:+.2f}"
                
                print(f"  ├─ {sous_categorie[:28]:<31} | {agregation_sous['nombre']:>8} | {debit_str_sous:>12} | {credit_str_sous:>12} | {solde_str_sous:>12}")
        
        print("-" * 90)
        
        total_debit_global += agregation_cat['total_debit']
        total_credit_global += agregation_cat['total_credit']
    
    print("=" * 90)
    total_solde_global = total_credit_global - total_debit_global
    print(f"{'TOTAL GÉNÉRAL':<35} | {len(operations):>8} | {total_debit_global:>12.2f} | {total_credit_global:>12.2f} | {total_solde_global:>+12.2f}")
    
    # Statistiques
    nb_categories = len(categories_data)
    nb_sous_categories = sum(len(data['sous_categories']) for data in categories_data.values())
    print(f"\n📊 {nb_categories} catégories, {nb_sous_categories} sous-catégories")

# ---------------------- I/O ----------------------

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

        for idx, raw_row in enumerate(reader, start=2):  # start=2 accounts for header line
            try:
                row_norm = {normalize_header(k): (v or "").strip() for k, v in raw_row.items()}
                date_val = row_norm.get(field_map.get("date_comptabilisation", ""), "")
                lib_simpl = row_norm.get(field_map.get("libelle_simplifie", ""), "")
                lib_op = row_norm.get(field_map.get("libelle_operation", ""), "")
                ref = row_norm.get(field_map.get("reference", ""), "")
                infos = row_norm.get(field_map.get("informations_complementaires", ""), "")
                typ = row_norm.get(field_map.get("type_operation", ""), "")
                cat = row_norm.get(field_map.get("categorie", ""), "")
                scat = row_norm.get(field_map.get("sous_categorie", ""), "")
                debit_raw = row_norm.get(field_map.get("debit", ""), "")
                credit_raw = row_norm.get(field_map.get("credit", ""), "")
                montant_raw = row_norm.get(field_map.get("montant", ""), "")

                date_iso = parse_date(date_val)
                debit_val = parse_amount(debit_raw) if debit_raw else None
                credit_val = parse_amount(credit_raw) if credit_raw else None

                if (debit_val is None and credit_val is None) and montant_raw:
                    m = parse_amount(montant_raw)
                    if m is not None:
                        if m < 0:
                            debit_val = abs(m); credit_val = None
                        elif m > 0:
                            credit_val = m; debit_val = None
                        else:
                            debit_val = credit_val = 0.0

                libelle_simpl = lib_simpl or lib_op

                op = OperationBancaire(
                    date_comptabilisation=date_iso,
                    libelle_simplifie=libelle_simpl,
                    libelle_operation=lib_op,
                    reference=ref,
                    informations_complementaires=infos,
                    type_operation=typ,
                    categorie=cat,
                    sous_categorie=scat,
                    debit=debit_val,
                    credit=credit_val,
                )
                operations.append(op)

            except Exception as e:
                preview = {k: (v if v is not None else "") for k, v in (raw_row or {}).items()}
                raise RuntimeError(f"Erreur à la ligne {idx}: {e}\n  Aperçu: {preview}") from e

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
        print("6. Agrégation par catégories et sous-catégories")
        print("0. Quitter")
        print("-"*64)

    def lister_fichiers_csv(self):
        print("\n🔍 Fichiers CSV trouvés:")
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
            print("⚠️ Saisie vide"); input("\nAppuyez sur Entrée pour continuer..."); return

        if choix.isdigit():
            idx = int(choix) - 1
            if 0 <= idx < len(fichiers):
                nom = fichiers[idx]
            else:
                print("⚠️ Numéro invalide"); input("\nAppuyez sur Entrée pour continuer..."); return
        else:
            nom = choix if choix.lower().endswith(".csv") else choix + ".csv"

        if not os.path.exists(nom):
            print(f"⚠️ Fichier '{nom}' introuvable"); input("\nAppuyez sur Entrée pour continuer..."); return

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

    def menu_agregation(self):
        """Fonction pour l'agrégation par catégorie et sous-catégorie"""
        if not self.operations:
            print("\n⚠️ Aucune opération en mémoire")
        else:
            afficher_agregations_completes(self.operations)
        input("\nAppuyez sur Entrée pour continuer...")

    def exporter_operations(self):
        if not self.operations:
            print("\n⚠️ Aucune opération à exporter")
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
            print(f"⚠️ Erreur lors de l'export: {e}")
        input("\nAppuyez sur Entrée pour continuer...")

    def vider_operations(self):
        if not self.operations:
            print("\n💡 Aucune opération en mémoire")
            input("Appuyez sur Entrée pour continuer..."); return
        confirmation = input(f"\n⚠️ Vider les {len(self.operations)} opérations en mémoire ? (oui/non): ").strip().lower()
        if confirmation in {"oui", "o", "yes", "y"}:
            self.operations.clear()
            print("✅ Opérations supprimées")
        else:
            print("⚠️ Annulé")
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
            elif choix == "6":
                self.menu_agregation()
            elif choix == "0":
                print("\n👋 Au revoir!"); break
            else:
                print("\n⚠️ Choix invalide"); input("Appuyez sur Entrée pour continuer...")

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
            print(f"⚠️ Fichier introuvable: {args.input_path}")
            sys.exit(1)
        try:
            run_batch(args.input_path, args.output_path)
        except Exception as e:
            print(f"⚠️ Erreur: {e}")
            sys.exit(2)
        sys.exit(0)

    # Interactive mode
    MenuImport().executer()

if __name__ == "__main__":
    main()