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
6. **Défauts connus des tables nettoyées (contrôle du 15/10/2026), non corrigés.**
   - *Codes ATC de niveau 4 pris pour des substances.* La liste MITM donne parfois un code à 5 caractères (`B05XC`, `A12AX`…) au lieu de 7. Il se propage à 116 médicaments de `produits`, 96 signalements, et crée 26 fausses « substances » dans `penuries_fr_mensuel` (2 444 lignes sur 150 494) : surtout des solutés, vitamines et produits de diagnostic. À écarter ou à marquer avant de modéliser.
   - *20 épisodes français finissent avant leur début* : pénuries vues seulement à leur remise à disposition, dont la date de remise affichée précède la photo précédente (utilisée comme début). Marginal (20 sur 1 603).
   - *Durées négatives normales en Italie et en Allemagne* (717 et 30 pénuries) : pénurie annoncée à l'avance, puis retirée de la liste avant la date prévue ou trop courte pour être vue entre deux photos. `fin_au_plus_tard` donne la borne de fin.
   - *Archives incomplètes* : 8 mois sans photo sur 67 pour la page ANSM, 13 sur 61 pour l'Italie, 15 sur 28 pour l'Allemagne, dont les dates de fin sont donc approximatives.
   - *Libellés ATC manquants* pour environ un quart des codes des épisodes : la table `atc` vient d'Open Medic, qui ne couvre que les médicaments remboursés en ville (pas les médicaments hospitaliers). Les codes eux-mêmes sont bons.

## 4. Préparer le dataset en pensant au ML (lien avec le programme)

C'est l'étape qui conditionne tout le reste. Les choix ci-dessous anticipent les cours *ML Protocol*.

### 4.1 Unité d'observation : un panel `substance (ATC5) × mois`, en France

Ordre de grandeur : environ 1 500 substances × 66 mois, soit environ 100 000 lignes. C'est assez pour du ML et léger en Parquet ou DuckDB.
Les autres pays (IT, DE, ES) n'ont pas d'univers complet de médicaments : ils deviennent des **colonnes** (signaux) du panel français, pas des lignes (voir QUESTIONS.md).

### 4.2 Cible (y)

`shortage_next_3m` = 1 si une nouvelle pénurie démarre pour cette substance en France entre *t+1* et *t+3*.

### 4.3 Variables (X), toutes connues à la date *t* (sinon fuite d'information)

| Famille | Exemples | Source |
|---|---|---|
| Structure du marché | nb de spécialités, nb de titulaires, nb de génériques, part du princeps | BDPM (versions archivées si possible) |
| Produit | forme (injectable / orale…), voie, ATC1-4, MITM | BDPM |
| Demande | boîtes remboursées (an *t*-1), évolution sur un an | Open Medic |
| Historique | nb de pénuries passées, mois depuis la dernière pénurie | panel lui-même (décalé) |
| **Cascade (Q1)** | nb de substances de la même ATC4 en pénurie à *t*, *t*-1, *t*-2 | panel (décalé) |
| **Contagion (Q2)** | substance en pénurie en Italie ou en Allemagne à *t*-1…*t*-3 | listes étrangères (décalées) |
| Saison | mois, hiver | date |

### 4.4 Protocole (cours du 12/10 et du 19/10)

- **Découpage temporel**, jamais aléatoire : entraînement ≤ 2024, validation 2025, test 2026.
- **Référence naïve** à battre : « en pénurie il y a peu → en pénurie bientôt ».
- **Classes déséquilibrées** : métriques PR-AUC et rappel@k, pas l'accuracy.
- Tester l'effet cascade en comparant le modèle **avec et sans** les variables de cascade, sur le même jeu de test.

## 5. Correspondance avec le programme

| Date | Cours | Application au projet |
|---|---|---|
| 14/09 | Collecte de données, EDA 1 | ✅ fait (05/10) : BDPM, ANSM, AIFA, BfArM, CIMA, EMA, Open Medic 2019-2025 et 249 archives Wayback (`python -m collecte`) |
| 21/09 | EDA 2 + Dash | Dashboard (TME6) : frise chronologique des pénuries, carte UE, heatmap ATC × temps, réseau de substituts |
| 28/09 – 05/10 | Construire un dataset depuis un entrepôt ; formats et bases | **Schéma en étoile** : table de faits `shortage_events` ; dimensions `substance`, `atc`, `country`, `month`, `product` ; panel dérivé. Stockage en **Parquet + DuckDB** |
| 12/10 – 19/10 | ML Protocol 1 et 2 | Cible, découpage temporel, référence naïve, prévention des fuites, validation croisée temporelle |
| 16/11 | Clustering | Profils de pénuries (durée, récurrence, saisonnalité) **pour répondre à une question**, pas pour classer à l'aveugle |
| 23/11 | Réduction de dimension | ACP sur la matrice ATC4 × mois des pénuries : des classes co-évoluent-elles ? |
| 30/11 | Interprétabilité et biais | SHAP / importance par permutation : facteurs de vulnérabilité. Biais de déclaration entre pays et entre périodes |
| 07/12 | MLOps | Pipeline reproductible (`collect → build → train`), mise à jour mensuelle |

## 6. Prochaines étapes (avant le TME4)

1. ~~Collecte des sources brutes, y compris les archives Wayback et Open Medic 2019-2025~~ ✅ fait le 05/10.
2. Niveau 2 : lecteurs ANSM (HTML), AIFA (CSV), BfArM (CSV), BDPM → table `shortage_events` et tables descriptives.
3. Niveau 3 : construction de `panel_fr`.
4. Comptages pour la description quantitative du livrable 1 (TME4).
