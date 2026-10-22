# Étude de faisabilité — 05/10/2026

Tests réels effectués le 05/10/2026 (requêtes HTTP, téléchargements d'échantillons). Voir `QUESTIONS.md` pour les questions.

> Ce document est le **compte rendu des tests faits avant la collecte**. Les chiffres du tableau ci-dessous sont ceux des tests.
> Pour ce qui a réellement été collecté, voir [DONNEES.md](DONNEES.md).

## 1. Verdict

**Faisable**, mais un point bloque la prédiction : les fichiers officiels actuels ne donnent qu'une **photo des pénuries en cours**, pas leur historique.
La solution testée consiste à **reconstruire l'historique à partir des archives de la Wayback Machine**, qui conserve des captures mensuelles des listes de pénuries depuis 2021.

**Correction du 13/10/2026.** Pour la France, un historique officiel existe : l'ANSM publie chaque année la liste des signalements de rupture et de risque de rupture (2019 → 2025, 22 501 lignes). Il donne la date de déclaration, mais ni la fin ni le statut. On l'utilise comme cible, et la reconstruction Wayback le complète (durée, gravité). Voir [DONNEES.md](DONNEES.md), section 2.

## 2. Sources testées

| Source | Pays | Accès | Volume constaté | Historique | ATC fourni | Verdict |
|---|---|---|---|---|---|---|
| BDPM `CIS_CIP_Dispo_Spec.txt` | FR | Fichier | 703 lignes | Non : uniquement les pénuries actives ou récemment remises à disposition | Non (jointure via CIS) | ✅ base actuelle |
| ANSM, signalements annuels (classeurs Excel) | FR | Fichier | 22 501 signalements, 1 504 à 4 925 par an | **Oui, officiel : 2019 → 2025**, date de déclaration seulement (ni fin, ni statut) ; MITM uniquement | Non (CIP13 depuis 2022) | ✅ **historique officiel FR** |
| Page ANSM « Disponibilité des produits de santé » | FR | HTML (une seule page, environ 296 fiches) | ~296 fiches actuelles | **Oui via Wayback : 58 captures mensuelles depuis 04/2021**, contenu analysable (statut, date, nom, forme, substance) | Non | ✅ **source clé de l'historique FR** |
| AIFA `elenco_medicinali_carenti.csv` | IT | CSV | 2 486 lignes, débuts 2016 → 2026 | Partiel dans le fichier + **47 captures Wayback depuis 10/2021** | **Oui (100 %)** | ✅ très bonne |
| BfArM Lieferengpässe `/public/csv` | DE | CSV (latin-1, sep `;`) | 963 lignes, 23 colonnes, raison de la pénurie, date de 1re déclaration 2018 → 2026 | Partiel + 12 captures Wayback depuis 07/2024 | **Oui** | ✅ bonne |
| AEMPS CIMA API `/cima/rest/psuministro` | ES | API JSON paginée | ~890 problèmes d'approvisionnement actifs (total annoncé instable, voir DONNEES.md) | Non (actifs seulement) ; Wayback non vérifié | Via `/medicamento?cn=` | ❌ abandonnée le 15/10 (ni historique ni ATC) |
| EMA shortages JSON | UE | JSON | 85 fiches | Oui, mais très peu d'entrées | Oui | ❌ abandonnée le 15/10 (trop peu d'entrées) |
| Liste critique de l'UE (EMA, HMA, Commission) | UE | XLSX | 299 substances | Date d'inscription de chaque substance (12/2023 → 2025) | **Oui** | ✅ gardée le 22/10 (criticité européenne) |
| openFDA `drug/shortages` | US | API JSON | 1 587 fiches, champ `shortage_reason` | Dates de publication | Non | 🟡 bonus de comparaison (**non collecté** pour l'instant) |
| Open Medic (Assurance Maladie) | FR | Archive ZIP par année, liens à jeton (collecté : 2019 → 2025) | ~1,9 million de lignes par an (CIP13 × âge × sexe × région) : boîtes remboursées et montants | Oui, annuel | **Oui (ATC1 → ATC5)** | ✅ volumes et ATC gratuits |
| Index ATC/DDD de l'OMS (atcddd.fhi.no) | — | HTML consultable gratuitement | Hiérarchie et libellés | — | — | 🟡 inutile pour l'instant : Open Medic fournit déjà les libellés ATC1 à ATC5 (**non collecté**) |

**À propos de l'ATC :** inutile d'acheter l'export à 200 €. Les codes ATC5 sont fournis par Open Medic, AIFA et BfArM. Les niveaux 1 à 4 se déduisent du préfixe du code (`J01CA04` → `J01CA` → `J01C` → `J01` → `J`). Les libellés des niveaux 1 à 5 sont fournis par Open Medic.

## 3. Risques identifiés

1. **Biais de déclaration.** Le nombre de pénuries explose à partir de 2023-2024 dans tous les pays (FR, DE, IT). C'est en partie réel, mais aussi lié au renforcement des obligations de déclaration. Il faut **normaliser par période** ou inclure le temps comme variable, et le discuter dans le rapport.
2. **Captures Wayback irrégulières.** Certains mois manquent. Il faut travailler au pas **mensuel** et marquer les mois sans capture comme manquants, sans les remplir.
3. **Jointure entre pays.** La clé commune retenue est **ATC5 (substance)**, éventuellement complétée par la forme (orale ou injectable). Les noms commerciaux et codes nationaux (CIS, AIC, PZN, CN) ne se correspondent pas d'un pays à l'autre.
4. **Définitions différentes.** « Rupture », « tension », « carenza » et « Lieferengpass » ne recouvrent pas exactement la même chose. La cible retenue est binaire : *au moins un signalement de problème d'approvisionnement*, avec la gravité en variable secondaire.
5. **Classe négative.** Il faut l'univers complet des substances commercialisées (BDPM + Open Medic pour la France), sinon le modèle ne voit que des cas positifs.
6. **Défauts connus des tables nettoyées (contrôle du 15/10/2026, suivi du 22/10/2026).**
   - ~~*Codes ATC de niveau 4 pris pour des substances.*~~ **Corrigé le 22/10** : seuls les codes à 7 caractères sont gardés, et un contrôle automatique le vérifie dans toutes les tables.
   - ~~*Date de publication manquante* pour 248 épisodes français vus seulement à leur remise à disposition.~~ **Corrigé le 22/10.**
   - ~~*Épisodes déjà en cours à la première archive comptés comme nouvelles pénuries ; dernier mois partiel dans le panel mensuel.*~~ **Corrigé le 22/10.**
   - *Archives BDPM tronquées à 1 Mio par la Wayback Machine* (découvert le 22/10) : 18, 17 et 16 fichiers sur 41, 39 et 41. Écartés au nettoyage ; l'historique du marché a des trous entre 06/2020 et 05/2024.
   - *20 épisodes français finissent avant leur début* : pénuries vues seulement à leur remise à disposition, dont la date de remise affichée précède la photo précédente (utilisée comme début). Marginal (20 sur 1 603).
   - *Durées négatives normales en Italie et en Allemagne* (717 et 30 pénuries) : pénurie annoncée à l'avance, puis retirée de la liste avant la date prévue ou trop courte pour être vue entre deux photos. `fin_au_plus_tard` donne la borne de fin.
   - *Archives incomplètes* : 8 mois sans photo sur 67 pour la page ANSM, 13 sur 61 pour l'Italie, 15 sur 28 pour l'Allemagne, dont les dates de fin sont donc approximatives.
   - *Libellés ATC manquants* pour environ un quart des codes des épisodes : la table `atc` vient d'Open Medic, qui ne couvre que les médicaments remboursés en ville (pas les médicaments hospitaliers). Les codes eux-mêmes sont bons.

## 4. Préparer le dataset en pensant au ML (lien avec le programme)

C'est l'étape qui conditionne tout le reste. Les choix ci-dessous anticipent les cours *ML Protocol*.

### 4.1 Unité d'observation : un panel `substance (ATC5) × mois`, en France

Ordre de grandeur : environ 1 200 à 1 500 substances × 80 mois (2019 → 2025), soit environ 100 000 lignes. C'est assez pour du ML, et environ 10 Mo en mémoire : Parquet + pandas suffisent, sans base de données (cours *Data Storage*, critère de volume).
Les autres pays (IT, DE) n'ont pas d'univers complet de médicaments : ils deviennent des **colonnes** (signaux) du panel français, pas des lignes (voir QUESTIONS.md).

**Cohorte (décision à valider ensemble).** Les signalements ne concernent que les MITM : 12,1 % de mois positifs chez les 1 223 substances qui ont au moins un MITM, 1,2 % chez les autres. Sans restriction, le modèle apprendrait surtout « MITM ou pas ». Proposition : restreindre la cohorte aux substances qui ont un MITM, et le dire dans le rapport.

### 4.2 Cible (y)

`shortage_next_3m` = 1 si au moins un **signalement officiel** à l'ANSM est daté entre *t+1* et *t+3* (fenêtre `[d, d + 3 mois)` avec *d* = 1er jour du mois *t+1*). Binaire : un signalement n'est pas une pénurie (un médicament peut être signalé plusieurs fois le même mois). Variante de robustesse : nouvelle pénurie sur la page ANSM (depuis 04/2021).

### 4.3 Variables (X), toutes connues à la date *d* (sinon fuite d'information)

La dernière colonne dit quelle date de disponibilité est utilisée : c'est l'« audit de colonne » du cours *Building a Dataset from a Warehouse*.

| Famille | Exemples | Source | Règle temporelle |
|---|---|---|---|
| Structure du marché | nb de spécialités, de titulaires, de génériques, part du princeps | `bdpm_*_historique` | version valable à *d* (jointure as-of) |
| Produit | forme (injectable / orale…), voie, ATC1-4 | `bdpm_specialites_historique`, `atc` | idem |
| Criticité | MITM ; liste critique de l'UE | `bdpm_mitm` (photo de 2026 : limite) ; `ue_liste_critique` | UE : `date_inscription < d` |
| Demande | boîtes remboursées, évolution sur un an | `consommation` | année *t*-1 (une année n'est complète qu'après sa fin) |
| Historique récent | pénurie affichée sur 3 et 12 mois, mois depuis la dernière, gravité ; durée des pénuries passées | `shortage_events` (France) | `publication < d` ; fin et durée seulement si `fin_connue_le < d` |
| Historique long | signalements par an, nb de laboratoires signalants | `ansm_signalements` | **années déjà publiées à *d*** : les classeurs paraissent 9 à 22 mois après les faits (METHODE.md, section 3) |
| **Cascade (Q1)** | nb d'**autres** substances de la même ATC4 en pénurie affichée sur 3 mois | `shortage_events` (France) | `publication < d`, la substance elle-même exclue |
| **Contagion (Q2)** | substance en pénurie en Italie ou en Allemagne sur 3 mois ; pays couvert ou non | `shortage_events` | `publication < d` (jamais `debut`) |
| Saison et période | mois, hiver, **année** (rupture de série 2022-2023) | *d* | — |

### 4.4 Protocole (cours du 12/10 et du 19/10)

- **Découpage temporel**, jamais aléatoire, avec un **trou de 3 mois** (la longueur de la fenêtre du label) entre deux périodes, pour qu'aucun signalement ne serve à la fois de label d'entraînement et de label de test. Les signalements s'arrêtant à 12/2025, le test ne peut pas être en 2026 : entraînement *d* ∈ 04/2019 → 09/2023, validation 01/2024 → 09/2024, test 01/2025 → 10/2025.
- **Référence naïve** à battre : « en pénurie il y a peu → en pénurie bientôt ».
- **Classes déséquilibrées** : métriques PR-AUC et rappel@k, pas l'accuracy.
- Tester l'effet cascade en comparant le modèle **avec et sans** les variables de cascade, sur le même jeu de test.

## 5. Correspondance avec le programme

| Date | Cours | Application au projet |
|---|---|---|
| 14/09 | Collecte de données, EDA 1 | ✅ fait (05/10) : BDPM, ANSM, AIFA, BfArM, CIMA, EMA, Open Medic 2019-2025 et 249 archives Wayback (`python -m collecte`) |
| 21/09 | EDA 2 + Dash | Dashboard (TME6) : frise chronologique des pénuries, carte UE, heatmap ATC × temps, réseau de substituts |
| 28/09 – 05/10 | Construire un dataset depuis un entrepôt ; formats et bases | ✅ **Schéma en étoile** : table de faits `shortage_events`, dimensions (`produits`, `atc`, BDPM **historisée** en SCD type 2) ; contrôles (grain, ATC, intervalles, totaux) ; manifestes du brut et des tables. Stockage : **Parquet + pandas** (tout tient en mémoire, une seule écriture par table) ; SQLite seulement si le dashboard refait les mêmes jointures à chaque interaction |
| 12/10 – 19/10 | ML Protocol 1 et 2 | Cible, découpage temporel, référence naïve, prévention des fuites, validation croisée temporelle |
| 16/11 | Clustering | Profils de pénuries (durée, récurrence, saisonnalité) **pour répondre à une question**, pas pour classer à l'aveugle |
| 23/11 | Réduction de dimension | ACP sur la matrice ATC4 × mois des pénuries : des classes co-évoluent-elles ? |
| 30/11 | Interprétabilité et biais | SHAP / importance par permutation : facteurs de vulnérabilité. Biais de déclaration entre pays et entre périodes |
| 07/12 | MLOps | Pipeline reproductible (`collect → build → train`), mise à jour mensuelle |

## 6. Prochaines étapes

1. ~~Collecte des sources brutes, y compris les archives Wayback et Open Medic 2019-2025~~ ✅ fait le 05/10.
2. ~~Niveau 2 : lecteurs ANSM (HTML), AIFA (CSV), BfArM (CSV), BDPM → table `shortage_events` et tables descriptives~~ ✅ fait ; signalements officiels (13/10), corrections et BDPM historisée (15/10 et 22/10).
3. ~~Comptages pour la description quantitative du livrable 1 (TME4)~~ ✅ fait.
4. Valider ensemble la cohorte (restriction aux substances MITM) et la cible (signalements).
5. Niveau 3 : construction de `panel_fr` (cohorte → variables → label → contrôles → manifeste), voir DONNEES.md.
6. Lignes de base (référence naïve, régression logistique), puis modèles avec et sans variables cascade et Europe.
7. Dashboard (TME6) à partir de `dashboard_summary`, puis rapport final (TME9).
