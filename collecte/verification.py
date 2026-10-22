"""Vérifie que la couche brute est intacte : chaque fichier de data/raw est tracé dans le
manifeste avec la même empreinte SHA-256, et aucun téléchargement interrompu (.part) ne traîne.

Lancée à la fin de `python -m collecte` et au début de `python -m nettoyage` : un fichier brut
modifié à la main ou abîmé est détecté avant de construire les tables.
"""
from .commun import MANIFESTE, RAW, lire_manifeste, sha256

# .DS_Store : fichiers créés par le Finder de macOS à l'ouverture d'un dossier.
IGNORES = {MANIFESTE.name, "_captures.json", ".DS_Store"}


def verifier():
    # En cas de retéléchargement, la dernière ligne d'un fichier fait foi.
    empreintes = {ligne["fichier"]: ligne["sha256"] for ligne in lire_manifeste()}
    problemes, nb_fichiers = [], 0
    for chemin in sorted(RAW.rglob("*")):
        if not chemin.is_file() or chemin.name in IGNORES:
            continue
        nb_fichiers += 1
        relatif = str(chemin.relative_to(RAW))
        if chemin.suffix == ".part":
            problemes.append(f"téléchargement interrompu : {relatif}")
        elif relatif not in empreintes:
            problemes.append(f"absent du manifeste : {relatif}")
        elif sha256(chemin.read_bytes()) != empreintes[relatif]:
            problemes.append(f"empreinte différente du manifeste : {relatif}")
    if problemes:
        raise SystemExit(f"Couche brute non conforme ({len(problemes)} problème(s)) :\n  "
                         + "\n  ".join(problemes[:20]))
    print(f"  couche brute intacte : {nb_fichiers} fichiers, empreintes conformes au manifeste")
