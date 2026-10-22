"""Collecte des sources brutes.

Usage :
    python -m collecte                      # toutes les étapes en parallèle
    python -m collecte actuelles wayback    # seulement certaines étapes

Chaque étape renvoie la liste de ses téléchargements en échec. S'il y en a, la collecte se
termine en erreur : relancer la commande, les fichiers déjà présents ne sont pas retéléchargés.
Sinon, on vérifie que chaque fichier brut correspond à son empreinte dans le manifeste.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor

from . import ansm_signalements, open_medic, sources_actuelles, verification, wayback
from .commun import creer_session

COLLECTES = {
    "actuelles": sources_actuelles.collecter,
    "ansm_signalements": ansm_signalements.collecter,
    "open_medic": open_medic.collecter,
    "wayback": wayback.collecter,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("etapes", nargs="*", help=f"parmi : {', '.join(COLLECTES)} (défaut : toutes)")
    args = parser.parse_args()
    etapes = args.etapes or list(COLLECTES)
    inconnues = set(etapes) - set(COLLECTES)
    if inconnues:
        parser.error(f"étapes inconnues : {', '.join(sorted(inconnues))}")

    # Les collectes visent des serveurs différents : elles tournent en même temps.
    session = creer_session()
    with ThreadPoolExecutor(max_workers=len(COLLECTES)) as executeur:
        futures = [executeur.submit(COLLECTES[e], session) for e in etapes]
        echecs = [echec for future in futures for echec in future.result()]

    if echecs:
        raise SystemExit(f"{len(echecs)} téléchargement(s) en échec : {echecs[:10]}. Relancer la collecte.")
    verification.verifier()
    print("Collecte complète.")


if __name__ == "__main__":
    main()
