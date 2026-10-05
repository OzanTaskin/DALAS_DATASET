"""Espagne — problèmes d'approvisionnement en cours, via l'API REST CIMA (AEMPS).

Deux défauts de l'API, constatés le 05/10/2026 :
- le total annoncé (`totalFilas`) dépend de la page demandée (893 ou 884) : il n'est pas fiable ;
- l'ordre des résultats change d'une requête à l'autre : en paginant, certaines lignes
  apparaissent sur deux pages et d'autres sur aucune.

On fait donc plusieurs passages complets (pages lues jusqu'à une page vide). On s'arrête
quand deux passages successifs n'ajoutent plus aucune ligne nouvelle à l'union.
Toutes les pages de tous les passages sont conservées telles quelles ; le dédoublonnage
se fera au nettoyage.
"""
import json
from datetime import date

from .commun import RAW, enregistrer

URL = "https://cima.aemps.es/cima/rest/psuministro?pagina={}"
PASSAGES_MAX = 10
PASSAGES_STABLES = 2  # passages consécutifs sans nouvelle ligne pour considérer l'union complète


def un_passage(session):
    reponses, numero = [], 1
    while True:
        reponse = session.get(URL.format(numero), timeout=120)
        reponse.raise_for_status()
        if not reponse.json()["resultados"]:
            return reponses
        reponses.append(reponse)
        numero += 1


def cles(reponses):
    return {json.dumps(ligne, sort_keys=True) for r in reponses for ligne in r.json()["resultados"]}


def collecter(session):
    jour = date.today().isoformat()
    if list((RAW / "cima" / "actuel").glob(f"{jour}_*.json")):
        print("  cima   photo du jour déjà présente")
        return

    union, stables = set(), 0
    for passage in range(1, PASSAGES_MAX + 1):
        reponses = un_passage(session)
        for numero, reponse in enumerate(reponses, start=1):
            enregistrer(reponse, f"cima/actuel/{jour}_passage{passage:02d}_p{numero:03d}.json", "cima")
        nouvelles = cles(reponses) - union
        union |= nouvelles
        stables = stables + 1 if not nouvelles else 0
        print(f"  cima   passage {passage} : {len(nouvelles)} nouvelles lignes, union = {len(union)}")
        if stables >= PASSAGES_STABLES:
            print(f"  cima   {len(union)} lignes distinctes (union stable)")
            return
    print(f"  cima   ATTENTION : union encore instable après {PASSAGES_MAX} passages")
