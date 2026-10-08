"""Niveau 2 : construit les tables nettoyées (data/clean/*.parquet) à partir de data/raw.

Usage :
    python -m nettoyage              # toutes les étapes, dans l'ordre
    python -m nettoyage ansm bdpm    # seulement certaines étapes
"""
import argparse

from . import ansm, ansm_episodes, ansm_fiches, bdpm, europe, evenements, open_medic, produits

# L'ordre compte : une étape peut lire les tables produites par les précédentes.
ETAPES = {
    "bdpm": bdpm.construire,
    "open_medic": open_medic.construire,
    "produits": produits.construire,
    "ansm": ansm.construire,
    "ansm_fiches": ansm_fiches.construire,
    "ansm_episodes": ansm_episodes.construire,
    "europe": europe.construire,
    "evenements": evenements.construire,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("etapes", nargs="*", help=f"parmi : {', '.join(ETAPES)} (défaut : toutes)")
    etapes = parser.parse_args().etapes or list(ETAPES)
    inconnues = set(etapes) - set(ETAPES)
    if inconnues:
        parser.error(f"étapes inconnues : {', '.join(sorted(inconnues))}")
    for etape in ETAPES:
        if etape in etapes:
            print(f"== {etape}")
            ETAPES[etape]()


if __name__ == "__main__":
    main()
