# Les données : méthode en niveaux et rôle de chaque source

Ce document explique **comment** on construit le dataset et **pourquoi** chaque source est là.
Pour les questions de recherche, voir le [README](README.md).

---

## 1. La méthode en trois niveaux

On ne passe jamais directement des sites web au modèle. Les données traversent trois niveaux,
chacun avec un rôle précis :

```
NIVEAU 1 : BRUT              NIVEAU 2 : NETTOYÉ             NIVEAU 3 : FINAL
data/raw/                    data/clean/  (à faire)         data/final/  (à faire)

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

### Ce qui est prévu aux niveaux 2 et 3

**Niveau 2 : 5 tables nettoyées**

| Table | Une ligne = | Construite à partir de |
|---|---|---|
| `shortage_events` (table centrale) | une pénurie d'un médicament dans un pays, avec début, fin et statut | ANSM, BDPM dispo, AIFA, BfArM, CIMA, EMA (+ archives) |
| `products` | un médicament commercialisé en France | BDPM |
| `substances_atc` | une substance (code ATC5) avec ses niveaux ATC 1 à 4 et sa criticité | Open Medic, MITM, liste critique UE |
| `consumption` | une substance × une année : boîtes remboursées | Open Medic |
| `market_structure` | une substance × une date : nombre de médicaments, de laboratoires, de génériques | BDPM (+ archives) |

**Niveau 3 : 2 datasets finaux**

| Dataset | Une ligne = | Sert à |
|---|---|---|
| `panel_fr` | une substance × un mois en France (~1 500 × 66 mois ≈ 100 000 lignes) | Question principale, Q1 (cascade), Q2 (signaux européens en colonnes) |
| `dashboard_summary` | une classe ATC × un pays × un mois | Le dashboard du TME6 (léger et rapide) |

---

## 2. Le problème central : l'historique

Les agences publient la liste des pénuries **en cours**. Une pénurie terminée disparaît de la liste.
Or, pour apprendre à prédire, il faut savoir ce qui s'est passé **avant**.

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
| `cima/actuel/` | AEMPS, API CIMA (agence espagnole) | 893 problèmes d'approvisionnement en JSON (pages de 200) | Signal Espagne |
| `ema/actuel/` | Agence européenne du médicament | `shortages.json` (85 pénuries suivies au niveau UE), `medicines.json` (2 746 médicaments autorisés au niveau européen), `union_list_critical_medicines.xlsx` (liste des médicaments critiques de l'UE) | Criticité européenne ; complément |

**Note sur CIMA :** l'API espagnole renvoie ses résultats dans un ordre qui change à chaque
requête. Lire les pages une fois peut donc donner des doublons et des oublis. Le script lit la liste
plusieurs fois (fichiers `passage01`, `passage02`…) jusqu'à ce qu'un nouveau passage n'apporte plus
aucune ligne. Les doublons seront retirés au niveau 2.

### 🕰️ Historique : archives de la Wayback Machine (`wayback/`)

Une archive par mois. Le fichier `_captures.json` de chaque dossier liste ce qui était disponible
et sert de référence à la vérification.

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
- **Sources avec la seule photo du jour :** compositions BDPM, MITM, EMA et CIMA n'ont pas encore
  d'historique. On vérifiera si des archives existent.
