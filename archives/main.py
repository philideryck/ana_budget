import csv
import os
from datetime import datetime

class OperationBancaire:
    def __init__(self, date_comptabilisation, libelle_simplifie, libelle_operation, 
                 reference, informations_complementaires, type_operation, 
                 categorie, sous_categorie, debit, credit):
        
        self.date_comptabilisation = date_comptabilisation
        self.libelle_simplifie = libelle_simplifie
        self.libelle_operation = libelle_operation
        self.reference = reference
        self.informations_complementaires = informations_complementaires
        self.type_operation = type_operation
        self.categorie = categorie
        self.sous_categorie = sous_categorie
        self.debit = debit
        self.credit = credit
    
    def __str__(self):
        return f"{self.date_comptabilisation} - {self.libelle_simplifie} - Débit: {self.debit} - Crédit: {self.credit}"
    
    @classmethod
    def export_to_csv(cls, operations, filename):
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['date_comptabilisation', 'libelle_simplifie', 'libelle_operation', 
                         'reference', 'informations_complementaires', 'type_operation', 
                         'categorie', 'sous_categorie', 'debit', 'credit']
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for op in operations:
                writer.writerow({
                    'date_comptabilisation': op.date_comptabilisation,
                    'libelle_simplifie': op.libelle_simplifie,
                    'libelle_operation': op.libelle_operation,
                    'reference': op.reference,
                    'informations_complementaires': op.informations_complementaires,
                    'type_operation': op.type_operation,
                    'categorie': op.categorie,
                    'sous_categorie': op.sous_categorie,
                    'debit': op.debit,
                    'credit': op.credit
                })
        print(f"✅ Export terminé: {filename}")
    
    @classmethod
    def import_from_csv(cls, filename):
        operations = []
        try:
            with open(filename, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                # DEBUG: Afficher les colonnes originales
                print(f"📋 Colonnes trouvées dans le fichier:")
                for i, col in enumerate(reader.fieldnames, 1):
                    print(f"  {i}. '{col}'")
                
                # Remplacer les espaces par des underscores dans les noms de colonnes
                original_fieldnames = reader.fieldnames.copy()
                reader.fieldnames = [col.replace(' ', '_').strip() for col in reader.fieldnames]
                
                print(f"\n🔄 Colonnes après normalisation:")
                for i, col in enumerate(reader.fieldnames, 1):
                    print(f"  {i}. '{col}'")
                
                for row_num, row in enumerate(reader, 1):
                    try:
                        # DEBUG: Afficher la première ligne pour voir la structure
                        if row_num == 1:
                            print(f"\n📄 Première ligne de données:")
                            for key, value in row.items():
                                print(f"  '{key}': '{value}'")
                        
                        # Créer un nouveau dictionnaire avec les colonnes renommées
                        new_row = {key.replace(' ', '_').strip(): value for key, value in row.items()}
                        
                        # Essayer de mapper les colonnes de façon flexible
                        def get_value(possible_names):
                            for name in possible_names:
                                if name in new_row:
                                    return new_row[name]
                            return ""
                        
                        op = cls(
                            date_comptabilisation=get_value(['date_comptabilisation', 'Date_de_comptabilisation', 'date', 'Date']),
                            libelle_simplifie=get_value(['libelle_simplifie', 'Libelle_simplifie', 'libelle', 'Libelle']),
                            libelle_operation=get_value(['libelle_operation', 'Libelle_operation']),
                            reference=get_value(['reference', 'Reference', 'ref', 'Ref']),
                            informations_complementaires=get_value(['informations_complementaires', 'Informations_complementaires', 'info', 'Info']),
                            type_operation=get_value(['type_operation', 'Type_operation', 'type', 'Type']),
                            categorie=get_value(['categorie', 'Categorie']),
                            sous_categorie=get_value(['sous_categorie', 'Sous_categorie']),
                            debit=get_value(['debit', 'Debit']),
                            credit=get_value(['credit', 'Credit'])
                        )
                        operations.append(op)
                        
                    except Exception as e:
                        print(f"❌ Erreur ligne {row_num}: {e}")
                        continue
                
                print(f"\n✅ {len(operations)} opérations traitées")
                
            return operations
        except Exception as e:
            print(f"❌ Erreur: {e}")
            import traceback
            traceback.print_exc()
            return []

class MenuImport:
    def __init__(self):
        self.operations = []
    
    def afficher_menu(self):
        print("\n" + "="*50)
        print("    GESTIONNAIRE D'IMPORTS - OPERATIONS BANCAIRES")
        print("="*50)
        print("1. Importer un fichier CSV")
        print("2. Lister les fichiers CSV disponibles")
        print("3. Afficher les opérations chargées")
        print("4. Exporter les opérations")
        print("5. Vider les opérations")
        print("0. Quitter")
        print("-"*50)
    
    def lister_fichiers_csv(self):
        print("\n📁 Fichiers CSV trouvés:")
        fichiers = [f for f in os.listdir('.') if f.endswith('.csv')]
        if fichiers:
            for i, fichier in enumerate(fichiers, 1):
                taille = os.path.getsize(fichier)
                print(f"  {i}. {fichier} ({taille} bytes)")
        else:
            print("  Aucun fichier CSV trouvé dans le répertoire courant")
        return fichiers
    
    def importer_fichier(self):
        print("\n📥 IMPORT DE FICHIER")
        fichiers = self.lister_fichiers_csv()
        
        if not fichiers:
            input("\nAppuyez sur Entrée pour continuer...")
            return
        
        try:
            choix = input("\nNom du fichier à importer (ou numéro): ").strip()
            
            # Si c'est un numéro
            if choix.isdigit():
                index = int(choix) - 1
                if 0 <= index < len(fichiers):
                    nom_fichier = fichiers[index]
                else:
                    print("❌ Numéro invalide")
                    return
            else:
                nom_fichier = choix
                if not nom_fichier.endswith('.csv'):
                    nom_fichier += '.csv'
            
            if os.path.exists(nom_fichier):
                nouvelles_operations = OperationBancaire.import_from_csv(nom_fichier)
                if nouvelles_operations:
                    self.operations.extend(nouvelles_operations)
                    print(f"✅ {len(nouvelles_operations)} opérations importées depuis {nom_fichier}")
                    print(f"📊 Total: {len(self.operations)} opérations en mémoire")
                else:
                    print("❌ Aucune opération importée")
            else:
                print(f"❌ Fichier '{nom_fichier}' non trouvé")
                
        except Exception as e:
            print(f"❌ Erreur lors de l'import: {e}")
        
        input("\nAppuyez sur Entrée pour continuer...")
    
    def afficher_operations(self):
        print(f"\n📋 OPÉRATIONS CHARGÉES ({len(self.operations)})")
        if not self.operations:
            print("Aucune opération en mémoire")
        else:
            choix_affichage = input("\nAffichage: (1) Aperçu (10 premières) | (2) Toutes | (3) Détail complet : ").strip()
            
            if choix_affichage == '2':
                # Afficher toutes les opérations en format compact
                print("\n" + "="*100)
                print(f"{'DATE':<12} | {'LIBELLÉ':<25} | {'CATÉGORIE':<15} | {'DÉBIT':<10} | {'CRÉDIT':<10}")
                print("="*100)
                
                for i, op in enumerate(self.operations, 1):
                    date_str = str(op.date_comptabilisation)[:10] if op.date_comptabilisation else "N/A"
                    libelle = (op.libelle_simplifie[:22] + "...") if len(str(op.libelle_simplifie)) > 25 else str(op.libelle_simplifie)
                    categorie = (op.categorie[:12] + "...") if len(str(op.categorie)) > 15 else str(op.categorie)
                    
                    print(f"{date_str:<12} | {libelle:<25} | {categorie:<15} | {str(op.debit):<10} | {str(op.credit):<10}")
                
                print("="*100)
                print(f"Total: {len(self.operations)} opérations")
                
            elif choix_affichage == '3':
                # Affichage détaillé avec pagination
                operations_par_page = 5
                page = 0
                
                while True:
                    debut = page * operations_par_page
                    fin = min(debut + operations_par_page, len(self.operations))
                    
                    print(f"\n📄 Page {page + 1} - Opérations {debut + 1} à {fin}")
                    print("-" * 80)
                    
                    for i in range(debut, fin):
                        op = self.operations[i]
                        print(f"\n🔹 Opération {i + 1}:")
                        print(f"   Date: {op.date_comptabilisation}")
                        print(f"   Libellé: {op.libelle_simplifie}")
                        print(f"   Catégorie: {op.categorie} / {op.sous_categorie}")
                        print(f"   Montant: Débit: {op.debit} | Crédit: {op.credit}")
                        print(f"   Type: {op.type_operation}")
                        print(f"   Référence: {op.reference}")
                    
                    # Navigation
                    if fin < len(self.operations):
                        navigation = input(f"\n(s)uivant | (p)récédent | (q)uitter | Page: ").strip().lower()
                        if navigation == 's' and fin < len(self.operations):
                            page += 1
                        elif navigation == 'p' and page > 0:
                            page -= 1
                        elif navigation == 'q':
                            break
                        elif navigation.isdigit():
                            nouvelle_page = int(navigation) - 1
                            if 0 <= nouvelle_page < (len(self.operations) + operations_par_page - 1) // operations_par_page:
                                page = nouvelle_page
                    else:
                        break
                
            else:
                # Aperçu par défaut
                print("-"*80)
                for i, op in enumerate(self.operations[:10], 1):
                    print(f"{i:2d}. {op}")
                
                if len(self.operations) > 10:
                    print(f"... et {len(self.operations) - 10} autres opérations")
                
                print("-"*80)
                print(f"Total: {len(self.operations)} opérations")
        
        input("\nAppuyez sur Entrée pour continuer...")
    
    def exporter_operations(self):
        if not self.operations:
            print("\n❌ Aucune opération à exporter")
            input("Appuyez sur Entrée pour continuer...")
            return
        
        print(f"\n📤 EXPORT ({len(self.operations)} opérations)")
        nom_fichier = input("Nom du fichier de sortie (sans .csv): ").strip()
        
        if not nom_fichier:
            nom_fichier = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        nom_fichier += ".csv"
        
        try:
            OperationBancaire.export_to_csv(self.operations, nom_fichier)
            print(f"✅ Export réussi vers {nom_fichier}")
        except Exception as e:
            print(f"❌ Erreur lors de l'export: {e}")
        
        input("\nAppuyez sur Entrée pour continuer...")
    
    def vider_operations(self):
        if self.operations:
            confirmation = input(f"\n⚠️  Vider les {len(self.operations)} opérations en mémoire? (oui/non): ")
            if confirmation.lower() in ['oui', 'o', 'yes', 'y']:
                self.operations.clear()
                print("✅ Opérations supprimées")
            else:
                print("❌ Annulé")
        else:
            print("\n💡 Aucune opération en mémoire")
        
        input("Appuyez sur Entrée pour continuer...")
    
    def executer(self):
        while True:
            self.afficher_menu()
            choix = input("Votre choix: ").strip()
            
            if choix == '1':
                self.importer_fichier()
            elif choix == '2':
                self.lister_fichiers_csv()
                input("\nAppuyez sur Entrée pour continuer...")
            elif choix == '3':
                self.afficher_operations()
            elif choix == '4':
                self.exporter_operations()
            elif choix == '5':
                self.vider_operations()
            elif choix == '0':
                print("\n👋 Au revoir!")
                break
            else:
                print("\n❌ Choix invalide")
                input("Appuyez sur Entrée pour continuer...")

# Lancement du programme
if __name__ == "__main__":
    menu = MenuImport()
    menu.executer()