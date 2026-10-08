"""France — page ANSM « Disponibilité des produits de santé » → `ansm_observations`.

Une ligne = une fiche ANSM vue dans une photo de la page (archive Wayback ou photo du jour).
Le passage aux épisodes de pénurie (début, fin) se fait dans `episodes.py`.

Structure de la page, stable de 2021 à 2026 : un tableau, une ligne <tr class="product-item">
par fiche, avec les colonnes
    statut | date | spécialité | remise à disposition | (domaines médicaux, depuis 2025)
Points d'attention :
- la colonne de date s'appelle « Publication » en 2021, puis « Mise à jour » : ce n'est pas
  la date de début de la pénurie ;
- la spécialité s'écrit « NOM dose, forme (substance) » en 2021,
  puis « Nom dose, forme – [substance] » ;
- dans la colonne « remise à disposition », l'attribut data-value est rempli même quand la
  cellule est vide : seule la date affichée compte.
"""
import re
from datetime import datetime

import pandas as pd
from bs4 import BeautifulSoup

from .commun import RAW, date_du_fichier, enregistrer, source_du_fichier

STATUTS = {
    "Rupture de stock": "rupture",
    "Tension d'approvisionnement": "tension",
    "Risque de rupture de stock": "risque_rupture",
    "Remise à disposition": "remise_a_disposition",
    "Arrêt de commercialisation": "arret_commercialisation",
}
MOIS = {"janv": 1, "févr": 2, "mars": 3, "avr": 4, "mai": 5, "juin": 6, "juil": 7,
        "août": 8, "sept": 9, "oct": 10, "nov": 11, "déc": 12}


def lire_date(texte):
    """« 22 sept. 2022 », « 05/10/2026 » ou « 2022/10/06 » → date (None si vide)."""
    texte = (texte or "").strip().rstrip(".")
    if not texte:
        return None
    for format_ in ("%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(texte, format_).date()
        except ValueError:
            pass
    # Quelques dates sont saisies avec l'année sur deux chiffres (« 3 oct. 22 »).
    jour, mois, annee = re.match(r"(\d{1,2})\s+([^\s.]+)\.?\s+(\d{4}|\d{2})$", texte).groups()
    annee = int(annee) + (2000 if len(annee) == 2 else 0)
    return datetime(annee, MOIS[mois], int(jour)).date()


def decouper_specialite(texte):
    """Sépare le nom du médicament et la substance active."""
    texte = re.sub(r"\s+", " ", texte).strip()
    crochets = re.match(r"^(.*?)\s*[–-]?\s*\[(.+)\]\s*$", texte)
    if crochets:
        return crochets.group(1).strip(" –-"), crochets.group(2).strip()
    # Format 2021 : substance dans la dernière parenthèse de premier niveau.
    if texte.endswith(")"):
        profondeur = 0
        for i in range(len(texte) - 1, -1, -1):
            profondeur += {")": 1, "(": -1}.get(texte[i], 0)
            if profondeur == 0:
                return texte[:i].strip(), texte[i + 1:-1].strip()
    return texte, None


def lire_page(chemin):
    soupe = BeautifulSoup(chemin.read_text(encoding="utf-8", errors="replace"), "lxml")
    lignes = []
    for tr in soupe.select("tr.product-item"):
        cellules = tr.find_all("td")
        statut_brut = cellules[0].get_text(strip=True)
        medicament, substance = decouper_specialite(cellules[2].get_text(" ", strip=True))
        lignes.append({
            "date_photo": date_du_fichier(chemin),
            "origine_photo": source_du_fichier(chemin),
            "fiche": tr["data-href"].rstrip("/").split("/")[-1],
            "statut": STATUTS.get(statut_brut, statut_brut),
            "date_mise_a_jour": lire_date(cellules[1].get("data-value")),
            "medicament": medicament,
            "substance": substance,
            "date_remise_a_disposition": lire_date(cellules[3].get_text(strip=True)),
            "domaine_medical": cellules[4].get_text(" ", strip=True) if len(cellules) > 4 else None,
        })
    return lignes


def construire():
    pages = sorted((RAW / "wayback" / "ansm_disponibilites").glob("2*.html"))
    pages += sorted((RAW / "ansm" / "actuel").glob("*.html"))
    lignes = [ligne for page in pages for ligne in lire_page(page)]
    table = pd.DataFrame(lignes)
    for colonne in ("date_photo", "date_mise_a_jour", "date_remise_a_disposition"):
        table[colonne] = pd.to_datetime(table[colonne])

    inconnus = set(table["statut"]) - set(STATUTS.values())
    if inconnus:
        raise ValueError(f"Statuts ANSM inconnus : {inconnus}")
    enregistrer(table, "ansm_observations")
    return table
