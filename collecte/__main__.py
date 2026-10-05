"""Collecte des sources brutes.

Usage :
    python -m collecte                      # toutes les étapes en parallèle, puis vérification
    python -m collecte actuelles cima       # seulement certaines étapes
    python -m collecte verification         # contrôle de complétude, sans téléchargement
"""
import argparse
from concurrent.futures import ThreadPoolExecutor

from . import cima, open_medic, sources_actuelles, verification, wayback
from .commun import creer_session

COLLECTES = {
    "actuelles": sources_actuelles.collecter,
    "cima": cima.collecter,
    "open_medic": open_medic.collecter,
    "wayback": wayback.collecter,
}
ETAPES = [*COLLECTES, "verification"]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("etapes", nargs="*", help=f"parmi : {', '.join(ETAPES)} (défaut : toutes)")
    args = parser.parse_args()
    etapes = args.etapes or ETAPES
    inconnues = set(etapes) - set(ETAPES)
    if inconnues:
        parser.error(f"étapes inconnues : {', '.join(sorted(inconnues))}")

    # Les collectes visent des serveurs différents : elles tournent en même temps.
    session = creer_session()
    collectes = [COLLECTES[e] for e in etapes if e in COLLECTES]
    with ThreadPoolExecutor(max_workers=len(COLLECTES)) as executeur:
        for future in [executeur.submit(collecte, session) for collecte in collectes]:
            future.result()  # fait remonter une éventuelle erreur

    if "verification" in etapes:
        print("== vérification")
        verification.verifier()


if __name__ == "__main__":
    main()
