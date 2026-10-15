# Les données : méthode en niveaux et rôle de chaque source

Ce document explique **comment** on construit le dataset et **pourquoi** chaque source est là.
Pour les questions de recherche, voir le [README](README.md).

---

## 1. La méthode en trois niveaux

On ne passe jamais directement des sites web au modèle. Les données traversent trois niveaux,
chacun avec un rôle précis :

```
NIVEAU 1 : BRUT              NIVEAU 2 : NETTOYÉ             NIVEAU 3 : FINAL
data/raw/                    data/clean/                    data/final/  (à faire)

Fichiers tels que      →     Tables propres, reliées   →    Tableaux prêts pour
téléchargés                  entre elles                    l'analyse et le ML
(HTML, CSV, JSON, ZIP)       (une ligne = une chose)        (une ligne = une observation)
```

### Pourquoi trois niveaux plutôt qu'un seul script ?

| Niveau | Règle | Pourquoi |
|---|---|---|
| **1. Brut** | On ne modifie **rien** : les octets reçus sont écrits tels quels. Chaque fichier est tracé dans `data/raw/manifeste.csv` (URL, date, taille, empreinte SHA-256). | **Preuve et reproductibilité.** Si on se trompe au nettoyage, on recommence à partir du brut sans retélécharger. Les sites changent et les pages disparaissent ; notre copie, non. L'empreinte prouve qu'un fichier n'a pas été modifié. |
| **2. Nettoyé** | Une table par type d'objet (pénuries, médicaments, substances…), des colonnes en format uniforme (dates, codes ATC, noms de pays), sans doublons. | **Séparer les problèmes.** Chaque source a son format (HTML ANSM, CSV italien en latin-1, JSON espagnol…). On règle ces différences une seule fois, ici. Ensuite, toutes les sources « parlent la même langue ». |
| **3. Final** | Des tableaux construits pour répondre à **une** question, sans fuite d'information (une variable au mois *t* n'utilise que ce qu'on savait au mois *t*). | **Répondre aux questions.** Le format dépend de la méthode : un panel mensuel pour le ML, un résumé agrégé pour le dashboard. |

C'est la démarche du cours *Building a Dataset from a Warehouse*. Le niveau 2 forme un
**schéma en étoile** : une table centrale de faits (les pénuries) entourée de tables qui la
décrivent (médicaments, substances, consommation…).

### Niveau 2 : les tables nettoyées (fait, `python -m nettoyage`)

Format **Parquet** : colonnes typées (dates, nombres), compressé, lu en une ligne avec pandas ou DuckDB.

**La table centrale**

| Table | Une ligne = | Lignes | Contenu |
|---|---|---:|---|
| **`shortage_events`** | un épisode de pénurie dans un pays | 16 842 | pays, médicament, substance, ATC5, ATC4, début, fin, publication, en cours, type (pénurie / arrêt définitif), gravité (FR), criticité (DE), raison (IT, DE) |

**Les tables qui la décrivent**

| Table | Une ligne = | Lignes | Sert à |
|---|---|---:|---|
| `produits` | un médicament français (CIS) avec son ATC5 | 15 883 | univers de prédiction, structure du marché |
| `atc` | un code ATC5 avec ses niveaux 1 à 4 et leurs libellés | 1 333 | classes thérapeutiques (substituts pour Q1) |
| `consommation` | un ATC5 × une année : boîtes et montants remboursés | 8 045 | demande |
| `bdpm_presentations`, `bdpm_compositions`, `bdpm_generiques`, `bdpm_mitm` | boîte, substance, groupe générique, médicament critique | 7 700 à 32 400 | variables du marché, criticité |
| `cip_atc` | une boîte (CIP13) avec son ATC5 | 15 963 | lien Open Medic ↔ BDPM |

**Les tables intermédiaires** (gardées pour vérifier chaque étape)

| Table | Une ligne = | Lignes |
|---|---|---:|
| `ansm_observations` | une fiche ANSM vue dans une photo de la page | 17 700 |
| `ansm_fiches` | une fiche ANSM reliée à ses médicaments et à un ATC5 | 1 470 |
| `ansm_episodes` | un épisode de pénurie en France, avec ses règles de début et de fin | 1 599 |
| `ansm_signalements` | un signalement officiel d'un laboratoire à l'ANSM (2019-2025), avec ATC5 | 22 501 |
| `bdpm_dispo_observations` | un signalement BDPM vu dans une photo | 10 807 |
| `europe_observations`, `europe_episodes` | idem pour l'Italie et l'Allemagne | 171 533 / 15 239 |

**La jointure des deux vues françaises**

| Table | Une ligne = | Lignes | Contenu |
|---|---|---:|---|
| `penuries_fr_mensuel` | une substance (ATC5) × un mois | 150 494 | nombre de signalements officiels et de laboratoires qui signalent ; nombre de pénuries affichées sur la page ANSM, nouvelles pénuries, gravité maximale |

Les deux sources viennent de l'ANSM et se recouvrent (453 des 462 substances affichées sur la page ont aussi
un signalement) : on ne les empile pas, on les met côte à côte. Une valeur vide veut dire « mois non
couvert par la source » (signalements : 2019 → 2025 ; page : 04/2021 → aujourd'hui), pas zéro.
Pour prédire, les colonnes de la page au mois *t* ne doivent expliquer que des signalements **postérieurs** à *t*.

### Les choix de construction importants

| Problème | Choix | Conséquence |
|---|---|---|
| L'ANSM et la BDPM ne donnent pas l'ATC | ATC obtenu par Open Medic, puis la liste MITM, puis un médicament aux **mêmes substances** | 81 % des médicaments commercialisés ont un ATC (le reste : surtout de l'homéopathie) |
| Les fiches ANSM n'ont pas de code médicament | Rapprochement en 4 voies : lien exact donné par la BDPM (808 fiches), nom identique (246), substance (126), marque (203) | **94 % des fiches** ont un ATC ; la voie utilisée est gardée (`methode_rapprochement`) |
| La date affichée par l'ANSM est une date de **mise à jour** | Début = date de mise à jour à la première apparition (elle tombe entre deux photos dans 98,5 % des cas), remplacée par la date exacte de la BDPM quand elle existe (556 épisodes) | début fiable au mois près |
| Une fiche peut repasser en pénurie | Chaque retour (après une remise à disposition) est un **nouvel épisode** | 1 599 épisodes pour 1 432 fiches |
| Pénurie apparue et résolue entre deux photos | Gardée, avec un début seulement borné (`debut_connu` = faux) | 189 épisodes |
| Épisode déjà en cours à la première archive (avril 2021) | Signalé (`censure_gauche`) | à exclure de l'estimation des durées |
| Les signalements n'ont pas d'ATC, et pas de code avant 2022 | CIP13 → BDPM (16 200), puis nom (4 121), substance (1 653), marque (237), Open Medic (10) | **98,8 % des signalements** ont un ATC5 ; la voie utilisée est gardée |
| Italie : l'AIFA révise la date de début d'une pénurie déjà listée (2 857 médicaments, presque toujours vers plus tard) | Un épisode = une présence continue du médicament sur la liste, pas « médicament + date de début » (qui créait un faux épisode à chaque révision) ; la dernière date déclarée sert de début, la première est gardée | 10 074 pénuries italiennes au lieu de 11 046 ; plus de faux épisodes |
| Allemagne : la déclaration initiale vaut « N/A » pour environ un quart des lignes | « N/A » traité comme vide : la ligne est sa propre déclaration initiale (auparavant, toutes ces lignes formaient un seul faux épisode) | 2 020 pénuries allemandes au lieu de 1 323 |
| Pénuries annoncées à l'avance (49 % en Italie) | Colonne `publication` = première photo où l'épisode apparaît : c'est la date du signal, à utiliser pour prédire (Q2), pas le début déclaré | pas de fuite d'information |
| Fin connue seulement entre deux photos | `fin` = dernière photo où l'épisode est publié, `fin_au_plus_tard` = photo suivante | 717 épisodes italiens ont un début après `fin` : pénurie plus courte que l'intervalle entre deux photos, ou annonce retirée |
| Italie : pas de colonne ATC avant fin 2024 | ATC repris du même code AIC, puis de la même substance | 94 % des épisodes italiens ont un ATC |
| Italie : « arrêt définitif de commercialisation » | Ce n'est pas une pénurie : `type_episode` = `arret_definitif` | 3 427 épisodes exclus de la cible |

### Niveau 3 : 2 datasets finaux (à faire)

| Dataset | Une ligne = | Sert à |
|---|---|---|
| `panel_fr` | une substance × un mois en France (~1 500 × 66 mois ≈ 100 000 lignes) | Question principale, Q1 (cascade), Q2 (signaux européens en colonnes) |
| `dashboard_summary` | une classe ATC × un pays × un mois | Le dashboard du TME6 (léger et rapide) |

---

## 2. Le problème central : l'historique

Les agences publient la liste des pénuries **en cours**. Une pénurie terminée disparaît de la liste.
Or, pour apprendre à prédire, il faut savoir ce qui s'est passé **avant**.

**Pour la France, l'historique officiel existe en partie.** L'ANSM publie chaque année tous les
signalements de rupture et de risque de rupture reçus des laboratoires (`ansm_signalements/`,
2019 → 2025). Ils donnent la date de déclaration, donc de quoi construire la cible, mais ni la date
de fin ni le statut. Pour la durée et la gravité, et pour les autres pays, il faut les archives.

**Notre solution : la Wayback Machine** (web.archive.org). Cette fondation archive
régulièrement des pages et fichiers publics. En récupérant une archive par mois des listes de
pénuries, on reconstruit ce qui était publié à chaque date passée.

Chaque source existe donc souvent sous deux formes :
- `data/raw/<source>/actuel/` : la photo d'aujourd'hui (la plus récente et la plus complète) ;
- `data/raw/wayback/<source>/` : les photos mensuelles passées.

---

## 3. Les sources brutes, une par une

Chiffres constatés lors de la collecte du 05/10/2026.

### 🇫🇷 France : ce qu'on prédit

#### BDPM : Base de données publique des médicaments (`bdpm/actuel/`)
Publiée par le ministère de la Santé et l'ANSM. C'est **l'univers complet** des médicaments vendus en
France, d'où son rôle central : elle donne les cas sans pénurie, indispensables pour prédire.

| Fichier | Lignes | Ce que c'est | Pourquoi on le prend |
|---|---:|---|---|
| `CIS_bdpm.txt` | 15 883 | Une ligne par médicament (code CIS) : nom, forme, voie, laboratoire, statut | Univers des médicaments ; forme et voie (injectable ou orale) comme variables |
| `CIS_CIP_bdpm.txt` | 20 923 | Une ligne par boîte vendue (code CIP13) : prix, remboursement | Le CIP13 fait le **lien avec Open Medic**, qui donne le code ATC |
| `CIS_COMPO_bdpm.txt` | 32 439 | Substances actives et dosages de chaque médicament | Savoir quelle substance contient chaque médicament |
| `CIS_GENER_bdpm.txt` | 10 737 | Groupes génériques : princeps et génériques | Compter les génériques et les fournisseurs (structure du marché) |
| `CIS_CIP_Dispo_Spec.txt` | 703 | Pénuries en cours : rupture, tension, arrêt, remise à disposition | Cible, côté BDPM |
| `CIS_MITM.txt` | 7 710 | Médicaments d'intérêt thérapeutique majeur, avec ATC | Criticité officielle française |
| `documentation_BDPM_v4.pdf` | — | Description officielle des colonnes | Indispensable pour lire les fichiers (ils n'ont pas d'en-têtes) |

#### ANSM : signalements annuels de rupture (`ansm_signalements/`)
Un classeur Excel par année (2021 à 2023 dans le même), publié au printemps suivant : 1 504 signalements en
2019, 2 446 en 2020, 2 167 en 2021, 3 761 en 2022, 4 925 en 2023, 3 809 en 2024, 3 889 en 2025.
Colonnes : date, laboratoire, médicament, DCI, et le code CIP13 depuis 2022.
**Limites :** MITM uniquement (seuls soumis à déclaration) ; ruptures et simples risques mélangés ;
un même médicament peut être signalé plusieurs fois ; pas de date de fin ; 2026 pas encore publié.

#### ANSM : page « Disponibilité des produits de santé » (`ansm/actuel/`)
La liste publique des pénuries, sous forme de page web (HTML) : 297 fiches aujourd'hui, avec statut
(rupture, tension, remise à disposition), date, nom, forme et substance.
**Pourquoi en HTML ?** Parce que c'est le format publié par le site. On le garde tel quel, et on
en extraira un tableau au niveau 2.

#### Open Medic : Assurance Maladie (`open_medic/`)
Une archive par année, de 2019 à 2025 (~25 Mo compressés, ~1,9 million de lignes par an).
Pour chaque boîte (CIP13) : **classification ATC complète, niveaux 1 à 5 avec libellés**,
générique ou non, et **nombre de boîtes remboursées**, détaillé par âge, sexe et région.

**Pourquoi :**
1. Mesurer la **demande** (une forte consommation fragilise-t-elle ?).
2. Obtenir **gratuitement** la classification ATC. L'export officiel de l'OMS coûte 200 €.
   L'ATC est la clé commune qui relie la France aux autres pays, et définit les « substituts » pour Q1.

### 🇪🇺 Autres pays : les signaux européens (Q2)

| Dossier | Source | Contenu | Pourquoi |
|---|---|---|---|
| `aifa/actuel/` | AIFA (agence italienne) | CSV d'environ 2 500 pénuries, avec code ATC, dates, raison et équivalents | Signal Italie ; l'ATC est fourni directement |
| `bfarm/actuel/` | BfArM (agence allemande) | CSV de 963 déclarations, avec ATC, dates et **raison de la pénurie** | Signal Allemagne ; la raison ouvre la direction E |
**Sources abandonnées (15/10/2026) :** l'Espagne (API CIMA de l'AEMPS) et l'EMA étaient collectées
mais jamais utilisées. L'API espagnole ne donne ni historique ni code ATC, et les fichiers de l'EMA
(85 pénuries suivies au niveau européen) n'apportaient rien aux questions. Voir FAISABILITE.md.

### 🕰️ Historique : archives de la Wayback Machine (`wayback/`)

Une archive par mois. Le fichier `_captures.json` de chaque dossier liste ce qui était disponible
le jour de la collecte.

| Dossier | Archives | Période | Ce que ça donne |
|---|---:|---|---|
| `ansm_disponibilites/` | 58 | 04/2021 → 09/2026 | **L'historique des pénuries en France** : la source la plus importante du projet |
| `aifa_carenti/` | 47 | 10/2021 → 09/2026 | Historique Italie |
| `bfarm_lieferengpaesse/` | 12 | 07/2024 → 09/2026 | Historique Allemagne (plus court) |
| `bdpm_dispo/` | 11 | 12/2023 → 03/2026 | Recoupement avec l'ANSM |
| `bdpm_cis/` | 41 | 02/2015 → 03/2026 | Médicaments commercialisés **à chaque date** |
| `bdpm_cip/` | 39 | 02/2015 → 03/2026 | Boîtes commercialisées à chaque date |
| `bdpm_gener/` | 41 | 02/2015 → 03/2026 | Génériques à chaque date |

**Pourquoi les anciennes versions de la BDPM ?** Pour éviter une **fuite d'information**.
Si on décrit le marché de 2022 avec la BDPM de 2026, on utilise des informations qu'on ne
connaissait pas en 2022. Par exemple, un générique retiré du marché *à cause* d'une pénurie fausserait
le modèle. Avec les archives, chaque mois est décrit avec ce qu'on savait à ce moment-là.

---

## 4. Limites connues (à discuter dans le rapport)

- **Archives irrégulières.** Certains mois n'ont pas d'archive. On les marquera comme manquants
  plutôt que d'inventer des valeurs.
- **Biais de déclaration.** Les pénuries explosent à partir de 2023-2024 dans tous les pays. C'est
  en partie réel, mais les obligations de déclaration ont aussi été renforcées.
- **Définitions différentes selon les pays.** « Rupture », « tension », « carenza », « Lieferengpass »
  ne veulent pas exactement dire la même chose. La cible sera binaire : au moins un signalement.
- **Pas de codes communs entre pays.** Chaque pays a ses codes (CIS, AIC, PZN, CN). La jointure se
  fait par substance (code ATC5).
- **Pénuries très courtes invisibles.** Avec une archive par mois, une pénurie qui commence et se
  termine entre deux archives peut ne jamais apparaître. L'historique sous-estime donc les pénuries
  courtes.
- **Le site de l'ANSM a pu changer de mise en page entre 2021 et 2026.** Le lecteur HTML du niveau 2
  devra gérer plusieurs versions de la page.
- **Sources avec la seule photo du jour :** compositions BDPM et MITM n'ont pas encore
  d'historique. On vérifiera si des archives existent.
