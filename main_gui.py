#!/usr/bin/env python3
"""Interface graphique (Tkinter) pour l'import et l'analyse de relevés bancaires."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import Iterable
from tkinter import filedialog, messagebox, ttk

from ana_budget import (
    OperationBancaire,
    agreger_par_categorie,
    agreger_par_sous_categorie,
    export_operations_to_csv,
    import_operations_from_csv,
)


class BudgetApp(tk.Tk):
    """Application principale pour visualiser les opérations bancaires."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Analyse budgétaire - Import CSV")
        self.geometry("980x640")
        self.minsize(860, 540)

        self.operations: list[OperationBancaire] = []

        self._create_widgets()

    # ------------------------------------------------------------------ UI --
    def _create_widgets(self) -> None:
        toolbar = ttk.Frame(self, padding=(10, 8))
        toolbar.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(toolbar, text="📂 Ouvrir un CSV", command=self.open_csv).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        ttk.Button(toolbar, text="📤 Exporter", command=self.export_csv).pack(
            side=tk.LEFT
        )

        self.status_var = tk.StringVar(value="Aucun fichier chargé")
        ttk.Label(toolbar, textvariable=self.status_var).pack(side=tk.LEFT, padx=12)

        search_frame = ttk.Frame(self, padding=(10, 0))
        search_frame.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(search_frame, text="🔎 Filtrer :").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=40)
        search_entry.pack(side=tk.LEFT, padx=(4, 0))
        search_entry.bind("<KeyRelease>", self._on_search)

        notebook = ttk.Notebook(self)
        notebook.pack(expand=True, fill=tk.BOTH, padx=10, pady=(0, 10))

        self.tree_operations = self._build_tree(
            notebook,
            (
                ("date", "Date"),
                ("libelle", "Libellé simplifié"),
                ("categorie", "Catégorie"),
                ("sous_categorie", "Sous-catégorie"),
                ("debit", "Débit"),
                ("credit", "Crédit"),
            ),
        )
        notebook.add(self.tree_operations.master, text="Opérations")

        self.tree_categories = self._build_tree(
            notebook,
            (
                ("categorie", "Catégorie"),
                ("nombre", "Nombre"),
                ("debit", "Débit total"),
                ("credit", "Crédit total"),
                ("solde", "Solde"),
            ),
        )
        notebook.add(self.tree_categories.master, text="Par catégorie")

        self.tree_sous_categories = self._build_tree(
            notebook,
            (
                ("sous_categorie", "Sous-catégorie"),
                ("nombre", "Nombre"),
                ("debit", "Débit total"),
                ("credit", "Crédit total"),
                ("solde", "Solde"),
            ),
        )
        notebook.add(self.tree_sous_categories.master, text="Par sous-catégorie")

        bottom = ttk.Frame(self, padding=(10, 0, 10, 10))
        bottom.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Label(bottom, text="Totaux :").pack(side=tk.LEFT)
        self.total_var = tk.StringVar(value="Débit 0,00 € | Crédit 0,00 € | Solde 0,00 €")
        ttk.Label(bottom, textvariable=self.total_var).pack(side=tk.LEFT, padx=(8, 0))

    def _build_tree(self, parent: ttk.Notebook, columns: tuple[tuple[str, str], ...]) -> ttk.Treeview:
        frame = ttk.Frame(parent)
        tree = ttk.Treeview(
            frame,
            columns=[c[0] for c in columns],
            show="headings",
            height=16,
        )
        yscroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        xscroll = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, columnspan=2, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        for key, label in columns:
            tree.heading(key, text=label)
            tree.column(key, anchor=tk.W, width=140, stretch=True)

        return tree

    # ---------------------------------------------------------------- Actions --
    def open_csv(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("Fichiers CSV", "*.csv"), ("Tous les fichiers", "*.*")]
        )
        if not path:
            return

        try:
            self.operations = import_operations_from_csv(path)
        except FileNotFoundError:
            messagebox.showerror("Erreur", f"Fichier introuvable :\n{path}")
            return
        except ValueError as exc:
            messagebox.showerror("Erreur de format", f"Le fichier CSV est mal formé :\n{exc}")
            return
        except Exception as exc:
            messagebox.showerror("Erreur", f"Impossible de charger le fichier :\n{exc}")
            return

        self.status_var.set(f"{Path(path).name} — {len(self.operations)} opérations")
        self._refresh_operations()
        self._refresh_aggregations()
        self._update_totals()

    def export_csv(self) -> None:
        if not self.operations:
            messagebox.showinfo("Export", "Aucune opération à exporter.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("Fichiers CSV", "*.csv")],
            confirmoverwrite=True,
        )
        if not path:
            return

        try:
            export_operations_to_csv(self.operations, path)
        except PermissionError:
            messagebox.showerror("Export", f"Permission refusée pour écrire dans :\n{path}")
            return
        except Exception as exc:
            messagebox.showerror("Export", f"Impossible d'enregistrer le fichier :\n{exc}")
            return

        messagebox.showinfo(
            "Export",
            f"{len(self.operations)} opérations exportées vers :\n{Path(path).name}",
        )

    # ----------------------------------------------------------- Utilitaires --
    @staticmethod
    def _fmt_amount(value: float | None, *, signed: bool = False) -> str:
        if value is None:
            return ""
        formatted = f"{value:+.2f}" if signed else f"{value:.2f}"
        return formatted.replace(".", ",")

    def _filter_operations(
        self, operations: Iterable[OperationBancaire], query: str
    ) -> list[OperationBancaire]:
        query = query.lower().strip()
        if not query:
            return list(operations)
        filtered: list[OperationBancaire] = []
        for op in operations:
            libelle = (op.libelle_simplifie or op.libelle_operation or "").lower()
            categorie = (op.categorie or "").lower()
            sous_categorie = (op.sous_categorie or "").lower()
            if query in libelle or query in categorie or query in sous_categorie:
                filtered.append(op)
        return filtered

    # ------------------------------------------------------------ Rafraîchit --
    def _refresh_operations(self) -> None:
        tree = self.tree_operations
        tree.delete(*tree.get_children())
        filtered_ops = self._filter_operations(self.operations, self.search_var.get())
        for op in filtered_ops:
            tree.insert(
                "",
                tk.END,
                values=(
                    op.date_comptabilisation,
                    op.libelle_simplifie or op.libelle_operation,
                    op.categorie,
                    op.sous_categorie,
                    self._fmt_amount(op.debit),
                    self._fmt_amount(op.credit),
                ),
            )

    def _refresh_aggregations(self) -> None:
        cats = agreger_par_categorie(self.operations)
        self._fill_aggregation_tree(self.tree_categories, cats, key_label="categorie")

        sous = agreger_par_sous_categorie(self.operations)
        self._fill_aggregation_tree(
            self.tree_sous_categories, sous, key_label="sous_categorie"
        )

    def _fill_aggregation_tree(
        self,
        tree: ttk.Treeview,
        data: dict[str, dict[str, float]],
        *,
        key_label: str,
    ) -> None:
        tree.delete(*tree.get_children())
        for name, values in sorted(
            data.items(),
            key=lambda item: item[1]["total_credit"] - item[1]["total_debit"],
            reverse=True,
        ):
            tree.insert(
                "",
                tk.END,
                values=(
                    name,
                    values.get("nombre", 0),
                    self._fmt_amount(values.get("total_debit")),
                    self._fmt_amount(values.get("total_credit")),
                    self._fmt_amount(
                        values.get("total_credit", 0) - values.get("total_debit", 0),
                        signed=True,
                    ),
                ),
            )

    def _update_totals(self) -> None:
        debit = sum(op.debit or 0.0 for op in self.operations)
        credit = sum(op.credit or 0.0 for op in self.operations)
        solde = credit - debit
        self.total_var.set(
            f"Débit {self._fmt_amount(debit)} € | Crédit {self._fmt_amount(credit)} € | "
            f"Solde {self._fmt_amount(solde, signed=True)} €"
        )

    def _on_search(self, event: object | None = None) -> None:
        del event  # unused
        self._refresh_operations()


if __name__ == "__main__":  # pragma: no cover - manual invocation only
    app = BudgetApp()
    app.mainloop()
