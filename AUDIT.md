# Audit du projet avant le rendu final (22/10/2026)

Périmètre : le dépôt (`main`, commit `05a23d7`), la branche `Belkacemi-data-collection` (3 commits, `3f7d940`),
lus à la lumière des deux derniers cours : *Building a Dataset from a Warehouse* (28/09) et
*Data Families, Storage Formats and Databases* (05/10).

Méthode : lecture de tout le code et de la documentation, puis **exécution complète de la branche** sur nos données
brutes (copie isolée, `python -m collecte ansm_signalements` puis `python -m nettoyage`, 24 s), puis contrôles chiffrés
reprenant les vérifications du cours (grain, NULL, totaux réconciliés, fuite temporelle, taux de positifs).
Tous les chiffres ci-dessous viennent de cette exécution, sauf mention contraire.

---

## Suivi (22/10/2026, après la fusion)

La branche `Belkacemi-data-collection` a été fusionnée dans `main` (fast-forward), puis :

| Point de l'audit | État |
|---|---|
| B1 codes ATC de niveau 4 | ✅ corrigé (`produits.py`), contrôlé dans toutes les tables |
| B2 `publication` manquante (248 épisodes FR) | ✅ corrigé (`ansm_episodes.py`, `evenements.py`) |
| B3 chiffres non reproductibles | ✅ `data/clean/manifeste.json` (lignes, colonnes, commit, empreinte du brut) ; la doc date ses chiffres |
| B4 épisodes déjà en cours comptés comme nouveaux | ✅ `censure_gauche` dans `shortage_events` (3 pays), exclu des nouvelles pénuries |
| B5 dernier mois partiel | ✅ le panel mensuel s'arrête au dernier mois complet |
| Vérification des empreintes du brut | ✅ remise en version légère (`collecte/verification.py`), à la fin de la collecte et au début du nettoyage |
| Liste critique de l'UE | ✅ gardée seule : `ue_liste_critique`, avec la date d'inscription (pas de fuite) |
| BDPM du jour pour décrire le passé (fuite) | ✅ `bdpm_*_historique` (SCD type 2, jointure as-of). **Découverte** : 51 des 121 archives sont tronquées à 1 Mio par la Wayback Machine ; elles sont écartées, l'historique a des trous entre 06/2020 et 05/2024 |
| Contrôles automatiques | ✅ `nettoyage/controles.py` : 24 contrôles (grain, ATC5, intervalles, réconciliation, publication) |
| `CHANGELOG_DATA.md`, `matplotlib` dans `requirements.txt` | ✅ |
| Docs (README, DONNEES, QUESTIONS, FAISABILITE) | ✅ mises à jour : cible, cohorte, variables avec leur date de disponibilité, découpage temporel corrigé |
| Rapport TME4 | inchangé : livrable rendu, photo du 05/10 |
| Cohorte MITM, `panel_fr`, modèles | ⏳ à faire : décision de cohorte à prendre à deux, puis § 6 |

Les sections ci-dessous sont l'audit tel qu'écrit avant la fusion.

---

## 0. En bref

1. **Le niveau 2 est solide** : sources tracées (SHA-256), couche brute jamais modifiée, une étape par fichier, choix
   documentés, clés uniques vérifiées. C'est déjà la démarche « niveaux » attendue par le cours.
2. **La branche de Rahim est à fusionner.** Elle apporte la pièce qui manquait (l'historique **officiel** des
   signalements ANSM 2019-2025) et corrige deux vrais bugs (faux épisodes italiens et allemands). Fusion sans conflit
   (fast-forward). Deux choix sont à rediscuter : la suppression de `verification.py` et celle de la liste critique de l'UE.
3. **Le niveau 3 (`panel_fr`) n'existe pas encore**, et c'est lui que le cours 1 évalue : cohorte → variables
   (*t* < *d*) → jointure as-of → label (*t* ≥ *d*) → contrôles → manifeste. C'est la priorité.
4. **Trois risques de fuite d'information** sont aujourd'hui dans les tables : BDPM du jour utilisée pour décrire le
   passé (alors que 121 archives BDPM sont collectées et jamais lues), `debut` au lieu de `publication`, et consommation
   Open Medic de l'année en cours.
5. **Le choix de la cible est à trancher** : les signalements officiels donnent 9,6 % de mois positifs (substance × mois),
   la page ANSM 1,1 %. Ce ne sont pas la même chose, et les signalements ne couvrent que les MITM.

---

## 1. Grille de lecture : ce que les deux cours demandent

| Cours | Exigence | Où on en est |
|---|---|---|
| Warehouse 1 | Savoir ce que représente **une ligne** de chaque table, et le vérifier (`COUNT(*)` contre `COUNT(DISTINCT clé)`) | ✅ documenté dans DONNEES.md ; clés vérifiées uniques (§ 4.1) |
| Warehouse 1 | Les 5 erreurs silencieuses : sens d'une ligne, additivité, fan-out, troncature de jointure, fuite temporelle | ⚠️ voir § 4 : deux sont présentes |
| Warehouse 1 | Historisation des dimensions et **jointure as-of** : l'état d'un attribut à la date *d* | ❌ les dimensions (BDPM, MITM) sont la photo de 2026 |
| Warehouse 1 | Table labellisée en 4 étapes, avec fenêtres relatives à *d* et contrôles avant Python | ❌ à faire (`panel_fr`) |
| Warehouse 1 | Découpage temporel avec un **trou** de la longueur de la fenêtre du label | ❌ à faire ; le plan actuel ne tient plus (§ 6.4) |
| Warehouse 1 | **Manifeste d'extraction** (requête versionnée, nb de lignes, sommes, empreinte du code) | ⚠️ manifeste pour le brut seulement, rien pour les tables nettoyées |
| Stockage 2 | Choisir le format avec l'arbre de décision (volume, relations, collaboration, structure) | ✅ Parquet + pandas est le bon choix (§ 5) |
| Stockage 2 | Couche brute en lecture seule, traçabilité de la provenance des données | ✅ |
| Stockage 2 | Déclarer les types explicitement à la lecture (dtype, `na_values`, `parse_dates`), entiers nullables | ✅ en grande partie (§ 5) |
| Stockage 2 | Arborescence `raw / processed / features / outputs / models`, nommage `{couche}_{desc}_v{n}_{date}` | ⚠️ `raw` et `clean` seulement, pas de versions |
| Stockage 2 | `CHANGELOG_DATA.md` : une ligne par changement (date, auteur, quoi, pourquoi) | ❌ absent, alors que la branche en est pleine |
| Stockage 2 | Modèles sérialisés avec joblib dans `models/` | à faire avec le ML |

---

## 2. État de `main`

**Ce qui est bien fait** (à garder et à mettre en avant dans le rapport final) :

- couche brute réellement immuable, manifeste avec URL, date, code HTTP et SHA-256 ; écriture atomique (`.part` puis
  renommage) ; reprise sans retéléchargement ;
- lecteurs robustes et commentés : encodages par fichier (BDPM, AIFA en cp1252), deux versions de la page ANSM,
  casse variable des en-têtes Open Medic, lecture par morceaux de 500 000 lignes (le *chunked reading* du cours 2) ;
- rapprochements ATC en plusieurs voies, **avec la voie utilisée gardée en colonne** (`source_atc`,
  `methode_rapprochement`) : c'est exactement la traçabilité que demande le cours ;
- épisodes français avec leurs incertitudes explicites (`debut_connu`, `censure_gauche`, `debut_au_plus_tot`) au lieu
  de valeurs inventées.

**Ce qui manque ou est daté sur `main`** :

- `rapport_tme4.tex` contient encore `[Nom 1], [Nom 2]`, et des chiffres que la branche rend faux (292 fichiers,
  17 343 épisodes, Espagne et EMA dans le tableau des sources, « vérification automatique »).
- `FAISABILITE.md` § 4.4 prévoit « test 2026 », ce qui est incompatible avec la nouvelle cible (§ 6.4).
- `analyse/figures_tme4.py` importe `matplotlib`, absent de `requirements.txt`.

---

## 3. La branche `Belkacemi-data-collection`, commit par commit

### `cb7f72a` : signalements officiels ANSM et jointure mensuelle → **excellent apport**

- Nouvelle source : les classeurs annuels des signalements de rupture et de risque de rupture (2019 → 2025,
  **22 501 lignes**, reproduit à l'identique chez nous). C'est un historique **officiel**, plus long (dès 2019) que la
  reconstruction Wayback (dès 04/2021) : cela change la cible possible du projet.
- ATC5 pour **98,8 %** des lignes (vérifié : 22 234 sur 22 501), la voie de rapprochement est gardée comme pour les fiches.
- Bonne réutilisation du code : `reperes_atc()` extrait de `ansm_fiches.py` au lieu d'être copié.
- `penuries_fr_mensuel` (substance × mois) : grain vérifié unique (150 306 lignes = 1 599 substances × 94 mois),
  entiers nullables `Int64`, et surtout **la distinction vide / zéro** (« mois non couvert » ≠ « aucun signalement »),
  exactement le point du cours sur `COALESCE` et le sens de NULL.
- Totaux réconciliés : somme de `nb_signalements` = 22 234 = signalements avec ATC. ✅

### `9550db1` : épisodes européens → **corrections de vrais bugs**

- **Italie** : la clé « médicament + date de début » créait un faux épisode à chaque révision de date par l'AIFA.
  Le passage à la « présence continue » est le bon choix et rend l'Italie cohérente avec la France.
- **Allemagne** : « N/A » dans la déclaration initiale regroupait un quart des lignes en un seul faux épisode. Bien vu.
- **Colonne `publication`** (première photo où l'épisode apparaît) : c'est la date à laquelle on **sait**, donc la
  bonne date pour les variables (cours 1, *observation date*). 49 % des pénuries italiennes sont annoncées avant leur
  début : utiliser `debut` comme variable aurait fait fuir de l'information.
- `fin_au_plus_tard` : encadre honnêtement la fin entre deux photos.

### `3f7d940` : retrait de l'Espagne, de l'EMA et de la vérification → **à discuter**

- **Espagne (CIMA) : d'accord.** Ni historique ni ATC : inutilisable pour Q2.
- **EMA : à moitié d'accord.** Les 85 pénuries EMA n'apportent rien, mais `union_list_critical_medicines.xlsx` est
  annoncée comme variable (« criticité officielle (MITM, liste critique de l'UE) ») dans le README, QUESTIONS.md et le
  rapport TME4. Proposition : garder ce seul fichier (une ligne dans `sources_actuelles.py`), ou retirer explicitement la
  variable des questions.
- **`verification.py` : je ne suis pas d'accord tel quel.** La nouvelle règle (la collecte échoue si un téléchargement
  échoue) est utile, mais elle ne contrôle plus que les fichiers présents correspondent au manifeste (empreinte, format).
  Or le cours 1 (manifeste, reproductibilité) et le cours 2 (couche brute en lecture seule, contrôle des empreintes)
  insistent précisément sur ce contrôle. Proposition : garder une vérification **légère** des empreintes du manifeste
  (≈ 20 lignes), lancée au début de `python -m nettoyage`.

### Problèmes trouvés en exécutant la branche

| # | Problème | Mesure | Gravité | Correction proposée |
|---|---|---|---|---|
| B1 | Codes ATC à 5 caractères (niveau 4) pris pour des substances (liste MITM) | 115 médicaments, 96 signalements, **25 fausses substances = 2 350 lignes** du panel mensuel | Moyenne (déjà signalé dans FAISABILITE.md, non corrigé) | Dans `produits.py` et `ansm_signalements.py`, ne garder que les ATC5 à 7 caractères (`str.len() == 7`, déjà fait pour Open Medic) |
| B2 | `publication` vide pour 248 épisodes français, dont 59 avec un début connu | 248 / 1 599 | Faible mais touche la cible | Pour un épisode vu seulement à sa remise à disposition, `publication` = la photo où il apparaît |
| B3 | Les chiffres écrits dans la doc ne se reproduisent pas | doc : 16 842 épisodes / 15 239 européens ; chez nous : **16 769 / 15 170** (photo du jour différente) | Faible, mais c'est l'objet du cours sur la reproductibilité | Manifeste des tables nettoyées (§ 4.6) ; dans la doc, citer les chiffres « au JJ/MM » |
| B4 | Épisodes déjà en cours en avril 2021 (`censure_gauche`, 191) comptés comme « nouvelles pénuries » le mois de leur date de mise à jour quand elle tombe dans la période | quelques dizaines | Faible | Exclure `censure_gauche` de `nb_nouvelles_penuries_affichees` |
| B5 | Le dernier mois (10/2026) est partiel : 2 nouvelles pénuries contre ~20 d'habitude | 1 mois | Faible | Couper au dernier mois complet |
| B6 | 20 épisodes FR, 716 IT, 30 DE avec `debut` > `fin` | — | Documenté, normal en IT/DE | Pour les durées, utiliser `fin_au_plus_tard` et exclure ces cas |
| B7 | Les données espagnoles et EMA restent dans `data/raw` en local (non suivies) | — | Aucune | Les supprimer à la main ou les laisser, sans impact |

**Verdict : fusionner la branche dans `main` (fast-forward), puis corriger B1, B2 et B4, et trancher la question de
`verification.py` et de la liste critique de l'UE.**

---

## 4. Audit avec la grille du cours 1 (Warehouse → Dataset)

### 4.1 Sens d'une ligne et grain ✅ (avec une nuance importante)

- Clés uniques vérifiées : `shortage_events` (pays, id_episode) 16 769 = 16 769 ; `penuries_fr_mensuel` (atc5, mois)
  150 306 = 150 306.
- **Nuance sur `ansm_signalements`** : une ligne n'est **pas** une pénurie. 250 lignes sont strictement identiques
  (gardées volontairement, c'est documenté), et **1 492** signalements concernent un médicament déjà signalé le même
  mois. Le cours (« Wrong grain », p. 25) : `nb_signalements` mesure l'activité de déclaration, pas le nombre de
  pénuries. → **La cible doit être binaire** (au moins un signalement dans la fenêtre), pas un comptage.

### 4.2 Additivité ⚠️ (important pour le dashboard)

- `nb_signalements` et `nb_nouvelles_penuries_affichees` sont des **flux** : on peut les additionner sur les mois.
- `nb_penuries_affichees` est un **stock** (pénuries en cours) : semi-additif. Le sommer sur 12 mois donne
  ~12 fois le nombre de pénuries. Sur le dashboard, utiliser la valeur du dernier mois ou la moyenne de la période
  (cours p. 40). À écrire dans le docstring de `france_mensuel.py`.

### 4.3 Troncature de jointure : comptée ✅

Contrôle « total de base contre total joint » (p. 43) :

| Passage | Entrée | Sortie | Perdu |
|---|---:|---:|---:|
| signalements → panel mensuel (`dropna(atc5)`) | 22 501 | 22 234 | 267 (1,2 %) |
| épisodes FR → panel (`dropna(atc5, debut)`) | 1 599 | 1 444 | 155 (9,7 %) |
| épisodes FR avec ATC → nouvelles pénuries dans la période | 1 444 | 1 361 | 83 (début avant 04/2021) |

Les pertes sont faibles et expliquées. Ce tableau mérite d'aller tel quel dans le rapport final : c'est la preuve
qu'on a vérifié les jointures.

### 4.4 Fuite temporelle ❌ : le point le plus important pour le ML

Règle du cours : une variable de la ligne (substance, *d*) ne lit **que** ce qui était publié avant *d*.

| Variable prévue | Problème | Solution |
|---|---|---|
| Nb de laboratoires, de génériques, de présentations ; forme ; statut de commercialisation | Calculés sur la **BDPM de 2026**. Un générique retiré **à cause** d'une pénurie disparaît du passé (exactement l'exemple écrit dans DONNEES.md). | Les archives existent déjà : `wayback/bdpm_cis` (41), `bdpm_cip` (39), `bdpm_gener` (41), soit **121 fichiers collectés et jamais lus**. Construire une dimension historisée `bdpm_*_historique` avec `valid_from` / `valid_to` (SCD type 2, p. 46) et faire une jointure as-of (p. 49) |
| MITM (criticité) | Photo de 2026 seulement | Accepter et documenter la limite, ou chercher des archives de la liste MITM |
| Rapprochement ATC des signalements et des fiches | Fait avec la BDPM du jour | Acceptable : l'ATC d'une substance ne change pas. À écrire dans les limites |
| Pénuries passées, signal européen | `debut` peut précéder la publication : en France, médiane **20 jours**, maximum 2 672 jours (date exacte BDPM connue plus tard) ; 49 % des pénuries italiennes annoncées en avance | Variables : **toujours `publication`**. Label : `date_signalement` (connue le jour même) |
| Consommation Open Medic de l'année *t* | Une année Open Medic n'est publiée que l'année suivante (date de mise en ligne à vérifier) | Utiliser l'année *t*−1 (ou *t*−2 pour les premiers mois de l'année) : c'est l'« audit de colonne » du cours (p. 52) |
| Cascade (Q1) | Doit compter les pénuries de la même ATC4 **publiées** avant *d*, en excluant la substance elle-même | Fenêtre `[d − 3 mois, d)` sur `publication` |

**Test automatique à écrire** (p. 57) : dans chaque étape de variables, avant l'agrégation, compter les lignes dont la
date d'événement est `>= d`. Le résultat doit être 0. Faire le test inverse sur l'étape du label.

### 4.5 Rupture de structure ⚠️ (p. 30, « two populations »)

Signalements par an : 1 504 (2019), 2 446, 2 167, **3 761 (2022), 4 925 (2023)**, 3 809, 3 889. La pénurie
d'antibiotiques de l'hiver 2022-2023 est réelle, mais une partie de la hausse vient des règles de déclaration
(direction F du README). Côté Europe, l'Allemagne n'a d'archives que depuis 07/2024 et l'Italie a retiré ~1 500 entrées
en 2026. Conséquences :

- ajouter l'**année** (ou une tendance) comme variable, et le dire dans le rapport ;
- pour Q2, ne comparer qu'avec et sans variables européennes **sur la même période** où elles existent.

### 4.6 Reproductibilité et manifeste ⚠️

On a un manifeste pour le brut, mais pas pour les tables construites. Le cours (p. 65) demande, à côté de chaque
dataset : date d'exécution, nombre de lignes, une ou deux sommes de contrôle, empreinte du code. Le constat B3 montre
pourquoi : deux exécutions donnent 16 842 et 16 769 épisodes, et rien ne permet de dire si c'est le code ou les
données qui ont changé (réponse : la photo du jour).

Proposition : `nettoyage/commun.enregistrer()` complète un `data/clean/manifeste.json` avec `{table, lignes, colonnes,
commit git, empreinte du manifeste brut, date}`. Même chose pour `panel_fr`. Une vingtaine de lignes.

---

## 5. Audit avec la grille du cours 2 (formats et stockage)

**Q1 Volume.** Plus grosse table : `europe_observations`, 33 Mo en mémoire (`memory_usage(deep=True)`) ; le panel
mensuel 12 Mo ; `panel_fr` fera ~100 000 lignes. Tout tient très largement en RAM. → **Parquet + pandas**, la
« single-read policy » est déjà appliquée (on lit le brut une fois, on écrit du Parquet typé). Les seules lectures
lourdes (Open Medic, 1,9 M lignes par an) sont déjà faites par morceaux.

**Q2 Relations.** Les jointures sont faites une fois à la construction, pas à chaque lecture. → Pas besoin d'un SGBD.
DuckDB (cité dans FAISABILITE.md) ou SQLite ne se justifient que si le dashboard (TME6) refait les mêmes jointures à
chaque interaction. Si c'est le cas : SQLite avec un index sur `(atc5, mois)`.

**Q3 Collaboration.** Deux personnes, mais **jamais deux écrivains en même temps** sur la même table : chacun régénère
`data/` avec le code. Pas de PostgreSQL. Le partage se fait par le code (git), ce qui est le bon choix.

**Q4 Structure.** Tous nos enregistrements ont un schéma fixe après aplatissement. Pas de base documents.

**Points d'amélioration, par ordre d'utilité** :

1. **`CHANGELOG_DATA.md`** (p. 33) : une ligne par changement des données. Les premières lignes sont déjà écrites
   dans les messages de commit de Rahim (Italie, N/A allemand, sources abandonnées, cible). C'est rapide et ça
   montre au correcteur qu'on a suivi le cours.
2. **Arborescence** (p. 32) : ajouter `data/final/` (ou `data/features/`) pour `panel_fr`, `models/` pour les modèles
   joblib, `outputs/` pour les prédictions et métriques. Nommer les versions :
   `panel_fr_v1_2026-11-xx.parquet`. Les dossiers `raw/` et `clean/` peuvent garder leurs noms.
3. **Types** : déjà bien fait (`dtype=str` à la lecture, dates parsées, `Int64` nullable dans le panel). Deux
   retouches : `shortage_events` mélange `datetime64[ms]` et `[us]` (harmoniser) ; `pays`, `statut`, `type_episode`,
   `gravite` en `category` (gain mémoire faible ici, mais c'est un point du cours).
4. **joblib** pour les modèles : ne charger que nos propres fichiers, et noter la version de scikit-learn
   dans `requirements.txt` (p. 34).

---

## 6. Le rendu final : proposition pour le niveau 3 (`panel_fr`)

On applique à la lettre la construction de la table labellisée du cours 1 (p. 53 à 63). Écrire chaque étape comme une
fonction séparée qui renvoie **une ligne par (substance, mois)**, puis tout assembler par `merge(how="left")`.
Attention : `pd.merge` fait par défaut une jointure interne, qui perd des lignes sans prévenir (p. 38).

### 6.1 Cohorte (fixe le grain)

- Une ligne = une substance ATC5 (**7 caractères**) × un mois *d* (1er du mois).
- Substances : celles qui ont au moins un médicament commercialisé à la date *d*, **d'après la BDPM archivée la plus
  récente avant *d*** (as-of).
- **Décision à prendre (MITM)** : les signalements ne concernent que les MITM. Mesuré : 1 223 des 1 514 substances
  commercialisées ont au moins un MITM ; taux de mois positifs **12,1 %** chez elles contre **1,2 %** chez les autres.
  Sans restriction, le modèle apprend surtout « MITM ou pas ». → Restreindre la cohorte aux substances MITM, ou garder
  tout le monde avec `est_mitm` en variable et des résultats donnés séparément. Je recommande la restriction, plus
  simple à défendre.

### 6.2 Label

- `y = 1` si au moins un signalement ANSM daté dans `[d, d + 3 mois)` (intervalle semi-ouvert, comme dans le cours),
  sinon 0. L'intervalle `[d+1, d+3]` des questions actuelles revient à décaler d'un mois : choisir l'un des deux et
  l'écrire partout pareil.
- Exclure les *d* dont la fenêtre dépasse la fin des signalements (12/2025) : dernier *d* = 2025-10-01 (p. 60).
- Variante pour la robustesse : même label construit à partir des nouvelles pénuries de la page ANSM (1,1 % de
  positifs, depuis 04/2021). Si les conclusions tiennent sur les deux, c'est un argument fort.

### 6.3 Variables (toutes avec une date de disponibilité < *d*)

| Famille | Variables | Source, règle temporelle |
|---|---|---|
| Historique | signalements sur `[d−3m, d)`, `[d−12m, d)` ; mois depuis le dernier ; nb de laboratoires signalants | `ansm_signalements`, `date_signalement < d` |
| Page ANSM | pénurie affichée en cours à *d*−1 ; gravité | `shortage_events` FR, sur `publication` |
| Cascade (Q1) | nb d'**autres** substances de la même ATC4 signalées sur `[d−3m, d)` | même table, en excluant la substance |
| Europe (Q2) | pénurie publiée en IT / DE sur `[d−3m, d)` ; indicateur « pays couvert à *d* » | `shortage_events`, sur `publication` |
| Marché | nb de CIS, de titulaires, de génériques, part injectable | BDPM **archivée**, as-of *d* |
| Demande | boîtes remboursées *t*−1, évolution sur un an | `consommation`, année *t*−1 |
| Criticité | MITM ; liste critique UE (si on la garde) | photo du jour, **limite à écrire** |
| Calendrier | mois, hiver, année | *d* |

### 6.4 Découpage temporel (à corriger dans FAISABILITE.md)

Le plan actuel (« entraînement ≤ 2024, validation 2025, test 2026 ») ne fonctionne plus : les signalements s'arrêtent à
12/2025. Proposition, avec le **trou de 3 mois** demandé par le cours (p. 62) :

- entraînement : *d* de 2019-04 à 2023-09 ;
- validation : *d* de 2024-01 à 2024-09 ;
- test : *d* de 2025-01 à 2025-10.

Lignes de base à battre : « signalée sur les 3 derniers mois → signalée sur les 3 prochains », puis une régression
logistique. Métriques : PR-AUC, rappel@k (classes déséquilibrées).

### 6.5 Contrôles avant d'entraîner (p. 61), écrits en code et lancés à chaque construction

1. nombre de lignes du panel = nombre de lignes de la cohorte ;
2. aucun NULL non prévu (un compteur vide devient 0 ; une source non couverte reste vide, comme dans
   `penuries_fr_mensuel`) ;
3. taux de positifs plausible (ni 0 % ni 100 %, autour de 10-12 % sur la cohorte MITM) ;
4. aucune date d'événement `>= d` dans les étapes de variables, aucune `< d` dans l'étape du label ;
5. manifeste écrit à côté du panel.

### 6.6 Table de prédiction (« scoring », p. 63)

Même code, une seule date *d* = le mois en cours, sans l'étape du label. Utile pour le dashboard : « substances les
plus à risque dans les 3 prochains mois ».

---

## 7. Plan d'action proposé

| Priorité | Tâche | Taille |
|---|---|---|
| 1 | Fusionner la branche de Rahim dans `main` | immédiat |
| 1 | Corriger B1 (ATC à 7 caractères) et B2 (`publication` des épisodes FR) | petit |
| 1 | Trancher : vérification des empreintes (je propose de la garder en version légère) ; liste critique UE (garder ou retirer la variable) | discussion |
| 2 | Dimension BDPM historisée à partir des 121 archives + jointure as-of | moyen, le plus important pour éviter la fuite |
| 2 | `panel_fr` : cohorte, variables, label, contrôles, manifeste (§ 6) | gros |
| 2 | Corriger le découpage temporel dans FAISABILITE.md | petit |
| 3 | `CHANGELOG_DATA.md`, manifeste des tables nettoyées, `matplotlib` dans `requirements.txt` | petit |
| 3 | Mettre à jour README, rapport (noms, chiffres, sources) | petit |
| 3 | Corriger B4 et B5 dans `france_mensuel.py`, écrire dans le docstring que `nb_penuries_affichees` est un stock | petit |

Répartition possible : une personne sur la dimension BDPM historisée et les variables « marché », l'autre sur le label,
les variables historique / cascade / Europe et les contrôles. Les deux parties se rejoignent dans l'assemblage du panel.

---

## Annexe : reproduire les contrôles

Les contrôles du § 4 ont été lancés sur les tables produites par la branche (`3f7d940`) à partir de nos données brutes
du 05/10/2026, avec les classeurs ANSM téléchargés le 22/10/2026. Ils peuvent devenir le module de contrôle
(`nettoyage/controles.py`) proposé au § 6.5.
