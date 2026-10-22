# Journal des changements des données

Une ligne par changement qui modifie le contenu d'une table ou d'un dataset : date, auteur, ce qui
change, pourquoi. Le détail technique est dans les messages de commit ; les chiffres de chaque
exécution sont dans `data/clean/manifeste.json`.

| Date | Auteur | Changement | Pourquoi |
|---|---|---|---|
| 2026-10-05 | Ozan | Collecte initiale : BDPM, ANSM, AIFA, BfArM, CIMA, EMA, Open Medic 2019-2025, archives Wayback | Niveau 1 du projet |
| 2026-10-08 | Ozan | Niveau 2 : 16 tables, dont `shortage_events` (17 343 épisodes FR/IT/DE) | Une table par objet, une seule façon de lire chaque source |
| 2026-10-13 | Rahim | Nouvelle source et table `ansm_signalements` (22 501 signalements officiels 2019-2025) ; table `penuries_fr_mensuel` | Historique officiel des déclarations françaises, plus long que la reconstruction Wayback : nouvelle cible possible |
| 2026-10-15 | Rahim | Italie : un épisode = présence continue sur la liste (11 046 → 10 074 pénuries) | L'AIFA révise les dates de début : la clé « médicament + date » créait de faux épisodes |
| 2026-10-15 | Rahim | Allemagne : « N/A » dans la déclaration initiale traité comme vide (1 323 → 2 020 pénuries) | Ces lignes formaient un seul faux épisode |
| 2026-10-15 | Rahim | Colonnes `publication`, `debut_declare_initial`, `fin_au_plus_tard` | `publication` est la date à laquelle on sait : seule date utilisable pour prédire |
| 2026-10-15 | Rahim | Espagne (CIMA) et EMA retirées de la collecte | Ni historique ni ATC pour l'Espagne ; 85 pénuries seulement pour l'EMA |
| 2026-10-22 | Ozan | Liste critique de l'UE remise, seule : table `ue_liste_critique` (299 substances, avec date d'inscription) | Variable annoncée dans les questions ; la date d'inscription évite la fuite |
| 2026-10-22 | Ozan | Codes ATC à 5 caractères (liste MITM) écartés des ATC5 | 25 codes de classe passaient pour des substances (2 350 lignes du panel mensuel) |
| 2026-10-22 | Ozan | `publication` renseignée pour les 248 épisodes français vus seulement à leur remise à disposition ; `censure_gauche` dans `shortage_events` pour les trois pays | Pas de date de publication = épisode inutilisable comme variable ; épisodes déjà en cours à exclure des durées |
| 2026-10-22 | Ozan | `penuries_fr_mensuel` : épisodes déjà en cours exclus des nouvelles pénuries ; arrêt au dernier mois complet | Faux pic de « nouvelles » pénuries en 04/2021 ; dernier mois vu en partie seulement |
| 2026-10-22 | Ozan | Dimensions historisées `bdpm_*_historique` (SCD type 2), sans les archives tronquées à 1 Mio | Décrire le marché passé avec la BDPM de 2026 ferait fuir de l'information |
| 2026-10-22 | Ozan | Vérification des empreintes du brut, manifeste et contrôles des tables nettoyées | Détecter un fichier brut abîmé, comparer deux exécutions, attraper les erreurs silencieuses |
| 2026-10-22 | Ozan | Colonne `fin_connue_le` dans `ansm_episodes` et `shortage_events` | La fin d'un épisode n'est connue qu'après coup : une variable à la date d ne doit la lire que si elle était déjà connue |
| 2026-10-22 | Ozan | dtype `category` (gravité ordonnée) dans `shortage_events` et `penuries_fr_mensuel` ; manifeste enrichi (sommes, empreintes du contenu et du code), copie datée dans `manifestes/` | Types explicites, mémoire réduite ; savoir si un écart vient du code ou des données |
| 2026-10-22 | Ozan | Variables prévues : les signalements ne servent qu'au label et à l'historique des années déjà publiées | Les classeurs ANSM sont annuels et paraissent au plus tôt au printemps suivant (au moins 3 mois de retard, souvent plus d'un an) : indisponibles au moment de prédire |
| 2026-10-22 | Ozan | Montants d'Open Medic arrondis au centime ; précision de la colonne `mois` fixée | Deux exécutions sur les mêmes données donnaient des tables différentes au dernier chiffre près (ordre des additions, version de pandas) |
| 2026-10-22 | Ozan | Rapport TME4 mis à jour avec les chiffres actuels (signalements, corrections Italie et Allemagne, codes ATC) | Le rapport du 08/10 décrivait l'état d'avant la fusion |
| 2026-10-22 | Rahim | Archive BDPM `CIS_bdpm` du 28/09/2022 écartée : tronquée à 1 Mio pile sur une fin de ligne, elle passait le test (`bdpm_specialites_historique` : 42 206 → 36 200 lignes) | Elle faisait « disparaître » environ 9 000 médicaments du marché entre 09/2022 et 05/2024 (vu sur les graphiques de contrôle) |
