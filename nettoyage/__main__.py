"""Niveau 2 : construit les tables nettoyées (data/clean/*.parquet) à partir de data/raw.

Usage :
    python -m nettoyage              # toutes les étapes, dans l'ordre
    python -m nettoyage ansm bdpm    # seulement certaines étapes

Avant de construire : vérification des empreintes de la couche brute. En dernière étape :
contrôles des tables (grain, codes ATC5, intervalles, totaux), voir `controles.py`.
Chaque table est tracée dans data/clean/manifeste.json.
"""
import argparse

from collecte import verification

from . import (ansm, ansm_episodes, ansm_fiches, ansm_signalements, bdpm, bdpm_historique, controles,
               europe, evenements, france_mensuel, open_medic, produits, ue_liste_critique)

# L'ordre compte : une étape peut lire les tables produites par les précédentes.
ETAPES = {
    "bdpm": bdpm.construire,
    "bdpm_historique": bdpm_historique.construire,
    "ue_liste_critique": ue_liste_critique.construire,
    "open_medic": open_medic.construire,
    "produits": produits.construire,
    "ansm": ansm.construire,
    "ansm_fiches": ansm_fiches.construire,
    "ansm_episodes": ansm_episodes.construire,
    "ansm_signalements": ansm_signalements.construire,
    "europe": europe.construire,
    "evenements": evenements.construire,
    "france_mensuel": france_mensuel.construire,
    "controles": controles.construire,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("etapes", nargs="*", help=f"parmi : {', '.join(ETAPES)} (défaut : toutes)")
    etapes = parser.parse_args().etapes or list(ETAPES)
    inconnues = set(etapes) - set(ETAPES)
    if inconnues:
        parser.error(f"étapes inconnues : {', '.join(sorted(inconnues))}")
    print("== vérification de la couche brute")
    verification.verifier()
    for etape in ETAPES:
        if etape in etapes:
            print(f"== {etape}")
            ETAPES[etape]()


if __name__ == "__main__":
    main()
