# Les pénuries de médicaments en France : prévisibles, contagieuses, importées ?

Projet de data science du cours **DALAS** (Sorbonne Université, 2026-2027) — Ozan Taskin, Rahim Belkacemi.
Choisir une question sur le monde réel, construire nous-mêmes un dataset pour y répondre, puis appliquer
les méthodes vues en cours.

| Document | Contenu |
|---|---|
| **README.md** (ce fichier) | le projet en bref, comment lancer le code |
| [Rapport-DALAS-Deliverable1/build/Rapport-DALAS-Deliverable1.pdf](Rapport-DALAS-Deliverable1/build/Rapport-DALAS-Deliverable1.pdf) | **le rapport du livrable 1** (2 pages) : questions, collecte, description quantitative, prétraitement |
| [EXPLICATIONS.md](EXPLICATIONS.md) | **l'explication détaillée** : chaque source, chaque table, chaque choix, et pourquoi, au regard des cours ; la suite du projet |
| [CHANGELOG_DATA.md](CHANGELOG_DATA.md) | une ligne par changement des données : date, auteur, quoi, pourquoi |
| `manifestes/` | l'état exact des tables à chaque construction de référence (lignes, sommes, empreintes) |

## Les questions

- **Question principale** : peut-on anticiper les pénuries en France ? Pour une substance (code ATC5) au
  mois *t*, quelle est la probabilité d'au moins un signalement de rupture à l'ANSM entre *t*+1 et *t*+3 ?
- **Q1, effet cascade** : une pénurie se propage-t-elle aux substituts (même classe ATC4) ?
- **Q2, pénuries importées** : une pénurie en Italie ou en Allemagne annonce-t-elle une pénurie en France ?

La France est au centre : c'est le seul pays dont on a l'univers complet des médicaments, y compris ceux
qui ne sont jamais en pénurie. L'Italie et l'Allemagne servent de signaux. Détails dans
[EXPLICATIONS.md](EXPLICATIONS.md), section 1.

## Avancement

| Étape | Statut |
|---|---|
| Niveau 1 : collecte des sources brutes | ✅ 272 fichiers, environ 500 Mo, empreintes vérifiées |
| Niveau 2 : tables nettoyées | ✅ 22 tables, dont `shortage_events` (16 769 épisodes FR/IT/DE) et `ansm_signalements` (22 501 signalements 2019-2025) ; 34 contrôles automatiques |
| Livrable 1 : rapport de 2 pages | ✅ `Rapport-DALAS-Deliverable1/` |
| Niveau 3 : table d'entraînement `panel_fr` | ⏳ plan dans [EXPLICATIONS.md](EXPLICATIONS.md), section 6 |
| TME6 : dashboard | ⏳ |
| TME9 : rapport final | ⏳ |

## Lancer le code

Les données ne sont **pas** sur GitHub (environ 500 Mo) : elles se régénèrent avec le code. Il faut
Python 3.11 ou plus récent (pandas 3 l'exige). Testé avec Python 3.14 et pandas 3.0 et 3.1.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m collecte              # niveau 1 : télécharge tout dans data/raw/ (environ 10 min)
.venv/bin/python -m nettoyage             # niveau 2 : tables dans data/clean/ (environ 30 s)
.venv/bin/python -m analyse.figures_rapport  # figures du rapport
.venv/bin/python -m analyse.diagnostics    # graphiques de contrôle des données (data/diagnostics/)
```

- Étapes isolées : `python -m collecte actuelles wayback`, `python -m nettoyage controles`.
- La collecte peut être relancée : les fichiers déjà présents ne sont pas retéléchargés. Si un
  téléchargement échoue, elle s'arrête avec la liste des fichiers manquants.
- Fin de la collecte et début du nettoyage : chaque fichier brut est comparé à son empreinte dans
  `data/raw/manifeste.csv`. Un fichier modifié ou abîmé arrête tout.
- Fin du nettoyage : contrôles des tables, puis copie du manifeste dans `manifestes/` (à commiter).
- Les sources évoluent : relancer plus tard donne une photo du jour plus récente, donc des chiffres
  légèrement différents. Le manifeste dit si un écart vient du code ou des données.
- Particularités : Open Medic refuse les téléchargements simultanés (années téléchargées une par une) ;
  une partie des archives BDPM est tronquée par la Wayback Machine (gardées dans le brut, écartées au
  nettoyage).

## Organisation

```
collecte/                 niveau 1
├── __main__.py           lance les étapes en parallèle, puis vérifie les empreintes
├── commun.py             session HTTP, téléchargement, manifeste
├── sources_actuelles.py  photo du jour : BDPM, ANSM, AIFA, BfArM, liste critique de l'UE
├── ansm_signalements.py  signalements de rupture, un classeur par an (2019-2025)
├── open_medic.py         consommation 2019-2025
├── wayback.py            archives mensuelles de la Wayback Machine
└── verification.py       empreintes de la couche brute conformes au manifeste

nettoyage/                niveau 2 : une étape par fichier, lancées dans l'ordre
├── commun.py             chemins, normalisation des textes, écriture + manifeste des tables
├── bdpm.py               BDPM du jour → bdpm_*
├── bdpm_historique.py    archives BDPM → bdpm_*_historique (versions datées)
├── ue_liste_critique.py  liste critique de l'UE
├── open_medic.py         → atc, cip_atc, consommation
├── produits.py           ATC5 de chaque médicament français
├── ansm.py               page ANSM → ansm_observations
├── ansm_fiches.py        chaque fiche ANSM reliée à un médicament et un ATC5
├── ansm_episodes.py      observations → épisodes de pénurie
├── ansm_signalements.py  classeurs → ansm_signalements
├── europe.py             Italie, Allemagne → europe_observations, europe_episodes
├── evenements.py         table centrale shortage_events
├── france_mensuel.py     → penuries_fr_mensuel (substance × mois)
└── controles.py          contrôles des tables (dernière étape)

analyse/figures_rapport.py figures du rapport
analyse/diagnostics.py    graphiques de contrôle : tailles des archives, lignes lues, cohérence des sources, durées…
Rapport-DALAS-Deliverable1/ rapport du livrable 1 (LaTeX et PDF)
```

Données (non versionnées) : `data/raw/` (brut, lecture seule), `data/clean/` (tables Parquet), puis, avec
le niveau 3, `data/final/`, `models/` et `outputs/`.

L'historique complet du travail (audit, notes de conception, étude de faisabilité) est sur la branche
[`ozan`](https://github.com/OzanTaskin/DALAS_DATASET/tree/ozan).
