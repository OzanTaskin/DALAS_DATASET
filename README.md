# Les pénuries de médicaments en France : prévisibles, contagieuses, importées ?

Projet de data science du cours **DALAS** (Sorbonne Université, 2026-2027).
L'objectif du cours : choisir une question sur le monde réel, construire nous-mêmes un dataset
pour y répondre, puis appliquer les méthodes vues en cours.

| Document | Contenu |
|---|---|
| **README.md** (ce fichier) | Le projet, les questions, les directions possibles, comment lancer le code |
| [DONNEES.md](DONNEES.md) | La méthode en niveaux (brut → nettoyé → final) et le rôle de **chaque** source brute |
| [QUESTIONS.md](QUESTIONS.md) | Les questions de recherche, formulées précisément |
| [FAISABILITE.md](FAISABILITE.md) | L'étude de faisabilité : sources testées, risques, lien avec le programme du cours |

---

## 1. Le problème

Les pénuries de médicaments ont fortement augmenté en Europe depuis 2021 (amoxicilline, paracétamol
pédiatrique, Ozempic…). Les agences publient la liste des pénuries **en cours**, mais personne ne
publie de prévision. On veut savoir si les données publiques permettent d'**anticiper** les pénuries
et de comprendre **comment elles se propagent**.

## 2. Les questions de recherche

> Version préliminaire (05/10/2026), qui pourra évoluer pendant le semestre (l'énoncé l'autorise).

### Question principale : prévisibilité

**Peut-on anticiper les pénuries de médicaments en France, et quels facteurs rendent une substance vulnérable ?**

Concrètement : pour une substance active (code ATC niveau 5) au mois *t*, quelle est la probabilité
qu'une nouvelle pénurie soit déclarée en France dans les **3 mois suivants** ?

Facteurs qu'on pense tester :
- nombre de laboratoires et de génériques sur le marché (peu de fournisseurs = fragile ?) ;
- forme (injectable ou orale) ;
- volume consommé ;
- criticité officielle (MITM, liste critique de l'UE) ;
- classe thérapeutique, saison ;
- pénuries passées.

### Question 1 : contagion entre substituts (« effet cascade »)

**Quand un médicament manque, ses substituts manquent-ils ensuite ?**
Exemple : pénurie d'amoxicilline → report des prescriptions sur l'amoxicilline/acide clavulanique
→ pénurie de celle-ci. On le mesure à l'intérieur d'une même classe thérapeutique (ATC niveau 4).

### Question 2 : pénuries « importées » d'Europe

**Une pénurie chez nos voisins (Italie, Allemagne, Espagne) annonce-t-elle une pénurie en France ?**
Si oui, les listes étrangères sont un signal d'alerte précoce.

### Pourquoi la France est au centre

Pour prédire, il faut aussi connaître les médicaments qui ne sont **jamais** en pénurie.
Seule la France publie la liste complète des médicaments commercialisés (la BDPM). Les autres pays
ne publient que leurs listes de pénuries : ils servent donc de **signaux**, pas de cibles.

### Comment on teste Q1 et Q2

On entraîne le modèle de prédiction avec et sans les variables « cascade » ou « Europe ».
Si la prédiction s'améliore, le signal existe.

## 3. Directions possibles pour la suite

Le cœur du projet (question principale + Q1 + Q2 sur la France) reste fixe. Selon le temps et les
résultats, on peut ajouter une de ces directions :

| Direction | Idée | Ce qu'il faudrait | Cours concerné |
|---|---|---|---|
| **A. Extension européenne** | Prédire aussi en Espagne et en Italie ; tester la propagation dans les deux sens | La liste complète des médicaments de ces pays (API CIMA pour l'Espagne, open data AIFA pour l'Italie, à vérifier) | ML Protocol |
| **B. Durée des pénuries** | Prédire non pas *si* mais *combien de temps* une pénurie va durer | Dates de début et de fin, déjà dans les données | ML Protocol |
| **C. Profils de pénuries** | Distinguer des familles : pénuries courtes et ponctuelles, chroniques, saisonnières | Le même historique | Clustering (16/11) |
| **D. Classes qui évoluent ensemble** | Quelles classes thérapeutiques entrent en pénurie en même temps ? | Matrice classe × mois | Réduction de dimension (23/11) |
| **E. Causes déclarées** | Les raisons de pénurie (production, demande, qualité…) diffèrent-elles par classe ? | Le champ « raison » de l'Allemagne (BfArM) | EDA, interprétabilité |
| **F. Biais de déclaration** | Quelle part de la hausse est réelle, et quelle part vient des nouvelles obligations de déclarer ? | Comparer pays et périodes | Interprétabilité et biais (30/11) |

## 4. Avancement

| Étape | Statut |
|---|---|
| Questions de recherche et faisabilité | ✅ fait |
| **Niveau 1 : collecte des sources brutes** | ✅ fait (297 fichiers, 484 Mo au 13/10/2026, vérification complète) |
| **Niveau 2 : tables nettoyées** | ✅ fait (18 tables, dont `shortage_events` : 16 842 épisodes FR/IT/DE, `ansm_signalements` : 22 501 signalements officiels 2019-2025, et leur jointure `penuries_fr_mensuel`) |
| Niveau 3 : datasets finaux (`panel_fr`) | ⏳ à faire, après le cours ML Protocol |
| TME4 : rapport de 2 pages | ⏳ |
| TME6 : dashboard | ⏳ |
| TME9 : rapport final | ⏳ |

## 5. Lancer le code

Les données ne sont **pas** sur GitHub : elles sont trop lourdes (483 Mo) et se régénèrent avec le
script. Il faut Python 3.10 ou plus récent et environ 500 Mo d'espace disque.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m collecte                 # niveau 1 : tout, en parallèle (≈ 10 min), puis vérification
.venv/bin/python -m nettoyage                # niveau 2 : tables nettoyées dans data/clean/ (≈ 30 s)
.venv/bin/python -m collecte actuelles cima  # seulement certaines étapes
.venv/bin/python -m collecte verification    # contrôle de complétude, sans téléchargement
```

- La collecte peut être relancée : les fichiers déjà présents ne sont pas retéléchargés.
- La vérification finale contrôle que chaque fichier attendu est présent, au bon format et tracé dans
  le manifeste avec la même empreinte ; elle échoue sinon.
- Les sources évoluent : relancer plus tard donnera une photo du jour plus récente. Les archives
  passées, elles, ne changent pas.

### Organisation du code

```
collecte/
├── __main__.py           point d'entrée : lance les étapes en parallèle, puis la vérification
├── commun.py             session HTTP, téléchargement, manifeste (traçabilité)
├── sources_actuelles.py  photo du jour : BDPM, ANSM, AIFA, BfArM, EMA
├── ansm_signalements.py  signalements officiels de rupture, un classeur par année (2019-2025)
├── cima.py               API espagnole (plusieurs passages, voir DONNEES.md)
├── open_medic.py         consommation française 2019-2025
├── wayback.py            historique via les archives de la Wayback Machine
└── verification.py       contrôle de complétude de data/raw

nettoyage/                niveau 2 : une étape par fichier, lancées dans l'ordre
├── bdpm.py               base des médicaments → bdpm_* (+ signalements archivés)
├── open_medic.py         → atc (libellés), cip_atc, consommation
├── produits.py           ATC5 de chaque médicament français
├── ansm.py               page ANSM (59 photos) → ansm_observations
├── ansm_fiches.py        chaque fiche ANSM reliée à un médicament et un ATC5
├── ansm_episodes.py      observations mensuelles → épisodes de pénurie (début, fin)
├── ansm_signalements.py  classeurs annuels → ansm_signalements (avec ATC5)
├── europe.py             Italie, Allemagne → europe_observations, europe_episodes
├── evenements.py         table centrale shortage_events (FR + IT + DE)
└── france_mensuel.py     signalements + épisodes → penuries_fr_mensuel (substance × mois)
```

Le détail des tables et des règles de construction est dans [DONNEES.md](DONNEES.md).

### Particularités des sources (constatées le 05/10/2026)

- **Open Medic** refuse les téléchargements simultanés et renvoie alors un message d'erreur au lieu
  de l'archive : les années sont téléchargées une par une et chaque ZIP est contrôlé.
- **CIMA (Espagne)** : le total annoncé par l'API dépend de la page et l'ordre des résultats n'est pas
  stable. La liste est lue plusieurs fois jusqu'à ce que l'union des lignes ne change plus ; les
  doublons seront retirés au nettoyage.
