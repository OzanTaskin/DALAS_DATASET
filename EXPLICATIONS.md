# Explications détaillées

Ce document accompagne le code et le rapport TME4
([rapport_tme4/rapport_tme4.pdf](rapport_tme4/rapport_tme4.pdf)). Il explique **ce que contient le
dataset, comment il est construit et pourquoi**, en s'appuyant sur les cours *Building a Dataset from a
Warehouse* (28/09) et *Data Families, Storage Formats and Databases* (05/10). Pour lancer le code, voir le
[README](README.md) ; pour l'historique des changements de données, [CHANGELOG_DATA.md](CHANGELOG_DATA.md).

Les chiffres viennent de l'exécution du 22/10/2026 (`manifestes/niveau2_2026-10-22.json`).

**Sommaire**
1. [Le projet et les questions](#1-le-projet-et-les-questions)
2. [Les sources](#2-les-sources)
3. [Du brut aux tables : trois niveaux](#3-du-brut-aux-tables--trois-niveaux)
4. [Les choix de construction](#4-les-choix-de-construction)
5. [Pourquoi ainsi : ce que les cours disent de notre cas](#5-pourquoi-ainsi--ce-que-les-cours-disent-de-notre-cas)
6. [La suite : la table d'entraînement](#6-la-suite--la-table-dentraînement)
7. [Limites](#7-limites)

---

## 1. Le projet et les questions

Depuis 2021, les pénuries de médicaments se multiplient en Europe. Les agences publient la liste des
pénuries **en cours**, mais personne ne publie de prévision.

- **Question principale (prévisibilité).** Peut-on anticiper les pénuries en France, et quels facteurs
  rendent une substance vulnérable ? Formellement : pour une substance active (code ATC niveau 5) au mois
  *t*, quelle est la probabilité qu'au moins un **signalement de rupture** soit déclaré à l'ANSM entre
  *t*+1 et *t*+3 ? Facteurs envisagés : nombre de laboratoires et de génériques, forme, volume consommé,
  criticité officielle (MITM, liste critique de l'UE), classe thérapeutique, saison, pénuries passées.
- **Q1 (contagion entre substituts).** Le risque d'une substance augmente-t-il quand d'autres substances
  de la même classe thérapeutique (ATC niveau 4) sont en pénurie ? Exemple attendu : amoxicilline →
  amoxicilline/acide clavulanique.
- **Q2 (pénuries importées).** Une pénurie de la même substance en Italie ou en Allemagne annonce-t-elle
  une pénurie en France ? Quels pays signalent en premier ?

**Pourquoi la France est au centre.** C'est le seul pays dont nous avons l'univers complet des
médicaments commercialisés (la BDPM), donc aussi ceux qui ne sont **jamais** en pénurie. Sans eux, un
modèle ne verrait que des cas positifs. L'Italie et l'Allemagne ne publient que leurs listes de pénuries :
elles servent de **signaux**, en colonnes du panel français.

**Comment on teste Q1 et Q2.** On entraîne le modèle avec et sans les variables « cascade » ou « Europe »,
sur le même jeu de test. Si la prédiction s'améliore, le signal existe.

**Ce qu'on ne prétend pas faire** : prédire la date exacte d'une pénurie, prédire les pénuries des autres
pays (leur univers de médicaments n'est pas disponible), expliquer les causes industrielles précises.

---

## 2. Les sources

Toutes sont publiques et officielles, collectées par `python -m collecte` (05/10/2026, signalements le
22/10/2026) : 272 fichiers, environ 500 Mo.

### France : ce qu'on prédit

| Source | Contenu | Rôle |
|---|---|---|
| **Signalements ANSM** (`ansm_signalements/`, classeurs Excel) | Les déclarations de rupture ou de risque de rupture envoyées par les laboratoires : 22 501 lignes de 2019 à 2025 (1 504, 2 446, 2 167, 3 761, 4 925, 3 809, 3 889 par an), avec date, laboratoire, médicament, substance, et le code CIP13 depuis 2022 | **La cible.** C'est l'historique officiel, immuable. Limites : médicaments d'intérêt thérapeutique majeur (MITM) seulement ; ni date de fin ni statut ; publié une fois par an |
| **Page ANSM** « Disponibilité des produits de santé » (`ansm/actuel/`, HTML) | Les pénuries publiées aujourd'hui (environ 300 fiches) : statut (rupture, tension, remise à disposition), date, médicament, substance | Historique récent (via les archives), gravité, durée |
| **BDPM** (`bdpm/actuel/`, fichiers texte) | L'univers complet : 15 883 médicaments (CIS), 20 923 boîtes (CIP13), 32 439 lignes de composition, 10 737 lignes de groupes génériques, 7 710 médicaments MITM avec leur ATC, les pénuries en cours | Univers de prédiction, structure du marché, criticité |
| **Open Medic** (`open_medic/`, CSV zippés) | Boîtes remboursées par an, 2019-2025 (environ 1,9 million de lignes par an), avec la classification ATC complète | La demande, et les codes ATC (l'export de l'OMS est payant) |

### Europe : les signaux (Q2)

| Source | Contenu |
|---|---|
| **AIFA** (Italie, CSV) | environ 2 500 pénuries, avec code ATC, dates, raison et équivalents |
| **BfArM** (Allemagne, CSV) | 963 déclarations, avec ATC, dates et **raison** de la pénurie |
| **Liste critique de l'UE** (EMA, XLSX) | 299 substances critiques, avec code ATC5 et **date d'inscription** (12/2023 → 2025) |

**Sources écartées.** L'Espagne (API CIMA) ne donne ni historique ni code ATC ; les 85 pénuries suivies par
l'EMA n'apportaient rien. Collectées au début, elles ont été retirées le 15/10/2026. Seule la liste
critique de l'UE a été gardée, parce que sa date d'inscription la rend utilisable sans fuite.

### L'historique : les archives de la Wayback Machine (`wayback/`)

Le problème central du projet : une pénurie terminée **disparaît** des listes. Nous avons récupéré une
archive par mois des listes, ce qui permet de reconstruire ce qui était publié à chaque date passée.

| Archives | Nombre | Période | Usage |
|---|---:|---|---|
| Page ANSM | 58 | 04/2021 → 09/2026 | épisodes de pénurie en France |
| Liste italienne | 47 | 10/2021 → 09/2026 | épisodes en Italie |
| Liste allemande | 12 | 07/2024 → 09/2026 | épisodes en Allemagne (historique court) |
| Disponibilité BDPM | 11 | 12/2023 → 03/2026 | date de début exacte des pénuries françaises |
| BDPM : médicaments, boîtes, génériques | 41 + 39 + 41 | 02/2015 → 03/2026 | le marché **tel qu'il était** à chaque date |

**Archives tronquées.** La Wayback Machine a coupé à exactement 1 Mio (1 048 576 octets) 51 des 121
archives de la BDPM, surtout entre 2019 et 2025 : le fichier s'arrête au milieu d'une ligne, avec environ
5 300 médicaments au lieu de 14 000. Elles restent dans le brut (on n'y touche jamais) mais sont écartées
au nettoyage. Photos complètes des médicaments : 2015 → 06/2020, puis 05/2024 → 2026 (celle du 28/09/2022 fait 1 Mio pile et se termine par hasard sur une fin de ligne : elle est aussi écartée, d'où un test sur la taille exacte et pas seulement sur le dernier caractère). Les
archives ANSM, AIFA et BfArM ne sont pas touchées.

---

## 3. Du brut aux tables : trois niveaux

```
NIVEAU 1 : BRUT            NIVEAU 2 : NETTOYÉ              NIVEAU 3 : FINAL (à faire)
data/raw/                  data/clean/                     data/final/
fichiers tels que     →    tables reliées entre elles  →   table d'entraînement
téléchargés                (une ligne = un objet)          (une ligne = une substance × un mois)
```

| Niveau | Règle | Pourquoi |
|---|---|---|
| **Brut** | Les octets reçus sont écrits tels quels, chaque fichier est tracé dans `data/raw/manifeste.csv` (URL, date, taille, SHA-256), et les empreintes sont revérifiées avant chaque nettoyage | Preuve et reproductibilité : les sites changent, notre copie non. Une correction se fait dans le code, jamais dans le fichier |
| **Nettoyé** | Une table Parquet par objet, colonnes au même format pour toutes les sources, contrôles à chaque construction, chaque table tracée dans `data/clean/manifeste.json` | Chaque source a son format (HTML, CSV en latin-1, Excel…) : on règle ces différences une fois, ici |
| **Final** | Une table construite pour **une** question, sans fuite d'information | Voir la section 6 |

### Les 22 tables nettoyées (`python -m nettoyage`, environ 30 s)

**La table centrale**

| Table | Une ligne = | Lignes |
|---|---|---:|
| **`shortage_events`** | un épisode de pénurie dans un pays (FR, IT, DE) : substance, ATC5, ATC4, début, **publication**, fin, **fin connue le**, en cours, type, gravité, criticité, raison, `debut_connu`, `censure_gauche` | 16 769 |
| **`ansm_signalements`** | un signalement d'un laboratoire à l'ANSM, avec son ATC5 et la méthode de rapprochement | 22 501 |
| **`penuries_fr_mensuel`** | une substance × un mois : signalements, laboratoires signalants, pénuries affichées, nouvelles pénuries, gravité maximale | 146 475 |

**Les dimensions**

| Table | Une ligne = | Lignes |
|---|---|---:|
| `produits` | un médicament français (CIS) avec son ATC5 | 15 883 |
| `atc` | un code ATC5 avec ses niveaux 1 à 4 et leurs libellés | 1 333 |
| `consommation` | un ATC5 × une année : boîtes et montants remboursés | 8 045 |
| `cip_atc` | une boîte (CIP13) avec son ATC5 | 15 963 |
| `ue_liste_critique` | une substance critique pour l'UE, avec sa date d'inscription | 299 |
| `bdpm_specialites`, `bdpm_presentations`, `bdpm_compositions`, `bdpm_generiques`, `bdpm_mitm` | la BDPM du jour | 7 711 à 32 439 |
| `bdpm_specialites_historique` | une **version** d'un médicament, valable sur `[valid_from, valid_to)` | 36 200 |
| `bdpm_presentations_historique` | une version d'une boîte | 38 776 |
| `bdpm_generiques_historique` | une version de l'appartenance d'un médicament à un groupe générique | 15 810 |

**Les tables intermédiaires**, gardées pour vérifier chaque étape : `ansm_observations` (17 700 : une
fiche vue sur une photo), `ansm_fiches` (1 470), `ansm_episodes` (1 599), `bdpm_dispo_observations`
(10 807), `europe_observations` (171 552), `europe_episodes` (15 170).

### Les contrôles (`nettoyage/controles.py`, dernière étape)

34 contrôles, dont le premier en échec arrête la construction :

- **clé unique** dans 13 tables (sinon doublons, et jointures qui multiplient les lignes) ;
- **codes ATC5 valides** (7 caractères) dans 6 tables ;
- **intervalles** des tables historisées sans chevauchement, et une seule version en cours par objet ;
- **totaux conservés** : signalements avec ATC = total du panel mensuel ; épisodes français et européens
  tous présents dans `shortage_events` ;
- **part des lignes sans ATC5** mesurée et plafonnée : 1,4 % des signalements, 7,1 % des fiches ANSM,
  6,3 % des épisodes ;
- **dates de connaissance** : chaque épisode a une date de publication, chaque épisode terminé une date
  de fin connue, jamais avant sa publication.

---

## 4. Les choix de construction

| Problème | Choix | Conséquence |
|---|---|---|
| L'ANSM et la BDPM ne donnent pas l'ATC | ATC par Open Medic (8 220 médicaments commercialisés), puis la liste MITM (1 519), puis un médicament aux **mêmes substances** (1 272) | 81 % des 13 650 médicaments commercialisés ont un ATC (le reste : surtout de l'homéopathie), soit 1 514 substances |
| La liste MITM donne parfois un code de classe (« B05XC ») au lieu d'une substance | Seuls les codes à 7 caractères sont gardés | pas de fausse substance |
| Les fiches ANSM n'ont pas de code médicament | Rapprochement en 4 voies, de la plus sûre à la moins sûre : lien exact donné par la BDPM (800), nom identique (245), substance (126), marque (195) | 93 % des fiches ont un ATC5 ; la voie utilisée est gardée |
| Les signalements n'ont pas d'ATC, et pas de code avant 2022 | CIP13 → BDPM (16 162), nom (4 100), substance (1 651), marque (254), Open Medic (10) | 98,6 % des signalements ont un ATC5 |
| La date affichée par l'ANSM est une date de **mise à jour** | Début = date de mise à jour à la première apparition (elle tombe entre deux photos dans 98,5 % des cas), remplacée par la date exacte de la BDPM quand elle existe (556 épisodes) | début fiable au mois près |
| Une fiche peut repasser en pénurie | Chaque retour après une remise à disposition est un **nouvel épisode** | 1 599 épisodes pour 1 432 fiches |
| Pénurie apparue et résolue entre deux photos | Gardée, avec un début seulement borné (`debut_connu` = faux) | 189 épisodes |
| Épisode déjà en cours à la première archive | `censure_gauche` = vrai, dans les trois pays | exclu des durées et des nouvelles pénuries (FR 191, IT 1 224, DE 434) |
| Italie : l'AIFA révise la date de début d'une pénurie déjà listée | Un épisode = une présence continue sur la liste, pas « médicament + date de début » | 10 035 pénuries au lieu de 11 046 faux épisodes |
| Allemagne : déclaration initiale « N/A » pour un quart des lignes | « N/A » traité comme vide : la ligne est sa propre déclaration initiale | 2 000 pénuries au lieu de 1 323 (toutes ces lignes formaient un seul faux épisode) |
| Italie : « arrêt définitif de commercialisation » | Ce n'est pas une pénurie : `type_episode` = `arret_definitif` | 3 135 épisodes exclus de la cible |
| Italie : pas de colonne ATC avant fin 2024 | ATC repris du même code AIC, puis de la même substance | 94 % des épisodes italiens ont un ATC |
| Fin connue seulement entre deux photos | `fin` = dernière photo où l'épisode est publié, `fin_au_plus_tard` = photo suivante | 716 épisodes italiens commencent après leur `fin` : annonce retirée, ou pénurie plus courte que l'intervalle entre deux photos |
| La BDPM du jour ne décrit pas le passé | Dimensions historisées à partir des archives complètes | voir section 5 |
| Montants en euros | arrondis au centime | deux exécutions identiques donnent des tables identiques |

---

## 5. Pourquoi ainsi : ce que les cours disent de notre cas

### 5.1 Notre situation est l'inverse de celle du cours

Le cours 1 part d'un data scientist qui lit un entrepôt **déjà construit** par d'autres. Nous n'en avons
pas. Les « systèmes opérationnels » sont les sites des agences, qui écrasent l'état passé à chaque mise à
jour : une pénurie terminée disparaît. C'est le problème de l'`UPDATE` qui efface l'historique (diapo 10),
sauf qu'ici personne n'a prévu d'historiser.

Nous jouons donc les deux rôles : l'équipe qui construit l'entrepôt (collecte, nettoyage, historisation)
et le data scientist qui en extrait la table d'entraînement. Les archives Wayback jouent le rôle des
chargements successifs ; nos photos datées, jamais réécrites, donnent l'équivalent du *time travel* (diapo
66). Ce n'est pas vrai des sites : l'AIFA a retiré environ 1 500 entrées anciennes en 2026, un exemple
réel de données modifiées après chargement (diapo 64).

### 5.2 Ce que représente une ligne

Un nom de table ne dit pas ce qu'est une ligne (diapo 25), et le choix du grain est irréversible (diapo 24).
Nos tables de faits ne sont pas de même nature :

| Table | Nature | Conséquence |
|---|---|---|
| `ansm_signalements` | fait **transactionnel** : écrit une fois, jamais modifié | la source la plus sûre pour le label |
| `ansm_observations`, `europe_observations` | photos périodiques en **format long** (cours 2, diapo 31) | les épisodes se reconstituent par la présence sur les photos successives |
| `shortage_events` | fait **complété après coup** (*accumulating snapshot*, diapo 51) | la fin n'est pas connue quand l'épisode commence : voir 5.3 |
| `penuries_fr_mensuel` | photo mensuelle agrégée | mélange un **stock** et des **flux** |

- **Un signalement n'est pas une pénurie.** 250 lignes du classeur sont identiques, et 1 492 signalements
  portent sur un médicament déjà signalé le même mois. Compter des signalements mesure l'activité de
  déclaration, comme compter des lignes d'articles n'est pas compter des paniers. D'où une **cible
  binaire** : au moins un signalement dans la fenêtre.
- **Le grain du panel : une substance × un mois.** L'ATC5 est la seule clé commune aux trois pays, et
  c'est le niveau auquel la question est posée. On perd la distinction injectable / orale pour une même
  substance, sauf à en faire une variable agrégée.
- **Stock et flux.** Le nombre de pénuries affichées un mois donné est un stock : l'additionner sur douze
  mois compterait douze fois une pénurie longue (diapo 40). On le lit à une date ou on en prend la
  moyenne. Les signalements et les nouvelles pénuries sont des flux, qu'on additionne.

### 5.3 La règle de la date d'observation *d* : le cœur du projet

Un modèle de prédiction s'utilise à une date donnée pour parler d'un futur inconnu. Pour qu'il apprenne,
chaque exemple doit recréer **exactement la situation de quelqu'un placé à cette date** (diapos 1 à 3 et 11) :

```
                          d (date d'observation)
                          │
  ── ce qu'on voyait ─────┼──── ce qui s'est passé ensuite ──→ temps
     avant d              │     après d
     = variables (X)      │     = label (y)
```

Une ligne de la table d'entraînement sera **(une substance, un mois *d*)**. Pour l'amoxicilline au
1er novembre 2022, le **label** demande s'il y a eu au moins un signalement entre le 1er novembre 2022
et le 31 janvier 2023 ; les **variables** ne contiennent que ce qu'on pouvait savoir le 31 octobre au
soir.

Si une variable contient une information postérieure à *d*, le modèle s'entraîne avec la réponse sous
les yeux : excellent à l'entraînement, inutilisable en réalité. Dans le TP MegaStore, une seule variable
de ce type fait passer l'AUC de 0,86 à 1,00. Et **aucune erreur n'apparaît** : seul un raisonnement sur la
date à laquelle chaque colonne devient connue la détecte (diapo 48).

Notre réponse est structurelle : **chaque information porte deux dates, celle de l'événement et celle
où il devient connu**, et les variables ne lisent que la seconde.

| Date d'un épisode | Sens | Utilisable pour une variable à *d* ? |
|---|---|---|
| `debut` | début déclaré | **non** : en France, la date exacte vient parfois de la BDPM après coup (22 jours avant la publication en médiane) ; en Italie, 49 % des pénuries sont annoncées **avant** leur début |
| `publication` | première photo où l'épisode apparaît | **oui** |
| `fin` | fin de la pénurie | seulement si `fin_connue_le < d` |
| `fin_connue_le` | photo où l'on voit que l'épisode est terminé | autorise la lecture de `fin` et de la durée |

Deux exemples au 1er novembre 2022 : une pénurie française qui commence le 15 octobre selon la BDPM mais
n'apparaît sur la page ANSM que le 3 novembre était invisible au 31 octobre (lire `debut` serait une
**fuite**) ; une pénurie italienne prévue au 1er décembre et annoncée en octobre était déjà visible (lire
`debut` ferait **perdre** un signal réellement disponible, celui que Q2 cherche à mesurer).

**Les dimensions changent aussi : la BDPM historisée.** Décrire le marché de 2022 avec la BDPM de 2026
serait une fuite : un générique retiré *à cause* d'une pénurie aurait disparu du passé (diapo 48). Les
tables `bdpm_*_historique` donnent une ligne par version, valable sur `[valid_from, valid_to)` (dimension
de type 2, diapo 46), que la table d'entraînement joindra par une **jointure as-of** sur le médicament et
la date d'observation (diapo 49). Deux écarts avec le cours :

- **les versions sont déduites de photos**, pas d'un journal des modifications : `valid_from` est la
  photo où l'on voit le changement pour la première fois. La date est approchée par excès : on perd en
  précision, jamais dans le sens de la fuite ;
- **les archives tronquées sont écartées** : elles feraient disparaître puis réapparaître des milliers
  de médicaments. Entre 06/2020 et 05/2024, l'état du marché est celui de la dernière photo complète.

Pas de clé de substitution : dans le cours, elle relie un fait à l'état de la dimension au moment du
fait. Nos faits ne sont pas reliés à la BDPM ; c'est la cohorte qui le sera, par la date d'observation.

**La latence de publication (diapos 8 et 52).** Les signalements sont publiés en classeurs annuels, au
plus tôt au printemps suivant : ceux de 2024 et 2025 ont été mis en ligne le 1er avril 2026, ceux de 2021
à 2023 sont regroupés dans un classeur mis en ligne en octobre 2025. **Un signalement devient public au
moins trois mois après sa date, souvent plus d'un an.** Le cours distingue deux usages de la même donnée :

- **pour entraîner**, hors ligne, la latence ne gêne pas : les signalements font un très bon **label** ;
- **pour prédire** au mois courant, un signalement récent n'est pas encore publié. Une variable
  « signalements des trois derniers mois » serait remplie à l'entraînement et vide en production.

Conséquence : l'historique **récent** d'une substance viendra de la page ANSM (publiée en continu, datée
par `publication`) ; les variables tirées des signalements ne porteront que sur des années déjà publiées
à *d*. Même logique pour Open Medic (une année n'est complète qu'après sa fin : on utilise l'année
précédente) et pour la liste critique de l'UE (comptée à partir de sa date d'inscription). Reste la liste
MITM et les compositions, connues seulement à leur état de 2026 : risque faible (une substance devient
rarement MITM) mais réel, que nous signalons comme limite.

### 5.4 Jointures, valeurs manquantes et totaux

- **Agréger avant de joindre.** Le tableau mensuel agrège chaque source au grain substance × mois, puis
  les joint : joindre ligne à ligne aurait multiplié les lignes (diapos 41-42).
- **Jointures à gauche.** Toutes les jointures partent de la liste complète des substances avec
  `how="left"` : `pd.merge` fait par défaut une jointure interne (cours 2, diapo 14), qui aurait supprimé
  sans message les substances jamais en pénurie, c'est-à-dire la classe négative (cours 1, diapo 36).
- **Vide n'est pas zéro.** Un mois couvert sans signalement vaut 0 ; un mois que la source ne couvre pas
  reste vide (diapo 37). Remplacer ces vides par 0 dirait « pas de pénurie » là où l'on ne sait pas.
- **Lignes sans substance.** Le cours remplace une clé introuvable par une ligne « Unknown » (diapo 27).
  Nous ne le faisons pas : notre table est indexée par substance, et une ligne sans substance ne peut être
  rattachée à aucune ligne du panel. Nous appliquons l'autre moitié de la règle : **mesurer** la part
  perdue et la plafonner (section 3).
- **Totaux réconciliés.** Comparer un total avant et après une étape ne voit pas deux erreurs de sens
  opposé (diapo 44) : les contrôles vérifient à la fois des totaux et des nombres de lignes.

### 5.5 Des séries qui ne sont pas homogènes dans le temps

Un volume qui saute vient souvent d'un changement de source ou de périmètre (diapo 30). Les signalements
doublent entre 2021 (2 167) et 2023 (4 925) : crise réelle des antibiotiques, mais aussi obligations de
déclaration renforcées. L'Allemagne n'a d'archives qu'à partir de 07/2024. L'Italie a purgé ses anciennes
entrées en 2026. D'où : l'**année** comme variable, un indicateur « pays observé à *d* » avec chaque
variable européenne, et l'apport de Q2 mesuré sur la période où les signaux existent.

### 5.6 Stockage et formats (cours 2)

| Critère | Notre réponse | Conséquence |
|---|---|---|
| Volume | 500 Mo de brut, mais la plus grosse table nettoyée tient en 33 Mo de mémoire ; le panel final fera environ 10 Mo | pandas + Parquet ; seule Open Medic (1,9 million de lignes par an) est lue **par morceaux** de 500 000 lignes, car l'opération (une somme) se calcule par morceaux |
| Relations | les jointures sont faites une fois, à la construction | pas de base de données ; SQLite avec un index seulement si le dashboard refait les mêmes jointures à chaque interaction |
| Collaboration | deux personnes, jamais deux écrivains sur la même table : chacun régénère les données à partir du même code | git pour le code ; pas de PostgreSQL |
| Structure | schémas fixes, une fois la page HTML de l'ANSM aplatie en tableau | tables Parquet ; pas de base de documents |

- **Types déclarés, jamais devinés.** Les fichiers BDPM sont lus en texte : CIS et CIP sont des
  identifiants, pas des nombres. Dates lues avec leur format, encodage détecté fichier par fichier,
  comptages en entiers nullables (`Int64`) pour distinguer vide et zéro. Les colonnes à peu de valeurs
  sont en type `category` (mémoire divisée par 10) et la gravité est une catégorie **ordonnée** (risque <
  tension < rupture), ce qui rend son maximum significatif.
- **Brut en lecture seule et lignage** : empreintes revérifiées, corrections dans le code, changements
  journalisés dans `CHANGELOG_DATA.md` (diapo 33).

### 5.7 Pouvoir dire si un écart vient du code ou des données

C'est l'objet du manifeste (cours 1, diapo 65). Chaque table nettoyée y est décrite par son nombre de
lignes, ses valeurs vides, la somme de chaque colonne numérique et une empreinte de son contenu, et sa
provenance par deux empreintes : celle du **code** de nettoyage et celle du **manifeste brut**. Une copie
datée est gardée dans `manifestes/`, suivie par git (diapo 66).

Deux cas se sont produits. D'abord, le même code a donné 16 842 épisodes chez l'un et 16 769 chez
l'autre : les deux collectes n'avaient pas la même photo du jour (15/10 et 05/10), mais sans manifeste
on ne pouvait que le supposer. C'est ce qui nous a fait l'ajouter. Ensuite, deux exécutions sur les mêmes
données brutes et le même code ont donné deux tables différentes au dernier chiffre près : le manifeste
l'a révélé (mêmes empreintes de code et de brut, empreinte de contenu différente), et la cause (sommes en
virgule flottante, précision des dates selon la version de pandas) a été corrigée.

---

## 6. La suite : la table d'entraînement

Le plan suit l'ordre imposé par le cours 1 (diapos 53 à 63).

1. **Cohorte (fixe le grain).** Une ligne par substance et par mois *d*, pour les substances qui ont au
   moins un médicament commercialisé à *d* d'après la BDPM historisée. **Décision à prendre** : les
   signalements ne concernent que les MITM ; les substances qui en ont connaissent 12,1 % de mois avec un
   signalement, les autres 1,2 %. Nous proposons de restreindre la cohorte aux substances MITM (1 223 sur
   1 514), sinon le modèle apprendrait surtout « MITM ou pas ».
2. **Variables**, chacune avec sa date de disponibilité :

   | Famille | Exemples | Source | Règle temporelle |
   |---|---|---|---|
   | Marché | nb de médicaments, titulaires, génériques ; part injectable | `bdpm_*_historique` | version valable à *d* |
   | Criticité | MITM ; liste critique UE | `bdpm_mitm`, `ue_liste_critique` | UE : `date_inscription < d` ; MITM : limite |
   | Demande | boîtes remboursées, évolution sur un an | `consommation` | année précédente |
   | Historique récent | pénurie affichée sur 3 et 12 mois, gravité, durée des pénuries passées | `shortage_events` (FR) | `publication < d` ; durée si `fin_connue_le < d` |
   | Historique long | signalements par an, laboratoires signalants | `ansm_signalements` | années déjà publiées à *d* |
   | Cascade (Q1) | nb d'**autres** substances de la même ATC4 en pénurie sur 3 mois | `shortage_events` (FR) | `publication < d` |
   | Europe (Q2) | pénurie en Italie ou en Allemagne sur 3 mois ; pays observé ou non | `shortage_events` | `publication < d` |
   | Période | mois, hiver, année | *d* | — |

3. **Label** : au moins un signalement dans `[d, d + 3 mois)`. Les dates dont la fenêtre dépasse 12/2025
   sont exclues (diapos 59-60) : pour *d* = novembre 2025, la fenêtre irait jusqu'à fin janvier 2026, et
   la substance paraîtrait « sans pénurie » alors qu'on ne sait pas. Dernier *d* : octobre 2025.
4. **Assemblage** par jointures à gauche sur la cohorte, chaque étape agrégée à une ligne par (substance,
   *d*), puis contrôles : nombre de lignes = cohorte, pas de valeur vide sans raison, taux de positifs
   plausible, aucune variable n'ayant lu un événement daté de *d* ou après.
5. **Découpage temporel avec un écart de trois mois** (diapo 62) : entraînement 04/2019 → 09/2023,
   validation 01/2024 → 09/2024, test 01/2025 → 10/2025. Temporel parce que le modèle prédira l'avenir à
   partir du passé ; un écart parce que le label regarde trois mois en avant : sans lui, les mêmes
   signalements de fin 2023 serviraient de réponse à l'entraînement et au test.
6. **Référence à battre** (« signalée récemment → signalée bientôt »), puis modèles **avec et sans** les
   variables cascade et Europe : c'est ainsi que Q1 et Q2 sont testées. Métriques adaptées à des classes
   déséquilibrées (PR-AUC, rappel sur les k substances les plus à risque).
7. **Table de prédiction** : le même code, une seule date (le mois courant), sans l'étape du label (diapo
   63). Seules les variables disponibles au mois courant peuvent entrer dans le modèle (section 5.3).
8. **Rangement** (cours 2, diapos 32-34) : `data/final/panel_fr_v1_<date>.parquet` avec son manifeste,
   modèles sérialisés avec joblib dans `models/`, prédictions et métriques dans `outputs/`.

---

## 7. Limites

- La cible ne couvre que les MITM, seuls soumis à déclaration.
- L'état du marché entre 06/2020 et 05/2024 est approché par la dernière photo complète de la BDPM.
- La liste MITM et les compositions ne sont connues qu'à leur état de 2026.
- Les pénuries trop courtes pour apparaître entre deux archives sont invisibles côté page ANSM (pas côté
  signalements).
- Les archives sont irrégulières : 8 mois sans photo sur 67 pour la page ANSM, 13 sur 61 pour l'Italie,
  15 sur 28 pour l'Allemagne ; les dates de fin y sont approximatives.
- Les définitions de « pénurie » diffèrent entre pays : les signaux européens sont des indicateurs, pas des
  mesures comparables.
- Une partie de la hausse des signalements est un effet de déclaration, pas de pénurie.
- Les libellés ATC manquent pour environ un quart des codes des épisodes : la table `atc` vient d'Open
  Medic, qui ne couvre que les médicaments remboursés en ville. Les codes eux-mêmes sont bons.
