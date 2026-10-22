# Construire notre dataset : nos choix, au regard des cours

Ce document explique **pourquoi** le dataset est construit comme il l'est, en s'appuyant sur les
deux cours *Building a Dataset from a Warehouse* (28/09) et *Data Families, Storage Formats and
Databases* (05/10). Il ne reprend pas les cours diapo par diapo : il dit ce que chaque idée devient
dans **notre** situation, y compris là où elle ne s'applique pas telle quelle, et ce qu'elle impose
pour la suite. Les chiffres viennent de l'exécution du 22/10/2026 (`manifestes/niveau2_2026-10-22.json`).

---

## 1. Notre situation est l'inverse de celle du cours

Le cours part d'un data scientist qui a un accès **en lecture** à un entrepôt construit par d'autres :
les tables existent, leur définition est fixée, et le travail consiste à en extraire une table
d'entraînement sans se tromper. Nous n'avons pas d'entrepôt. Les « systèmes opérationnels » sont les
sites des agences (ANSM, AIFA, BfArM), qui publient l'état **présent** et l'écrasent à chaque mise à
jour : une pénurie terminée disparaît de la liste. C'est exactement le problème de l'`UPDATE` qui
efface l'état passé (cours 1, diapo 10), sauf qu'ici personne n'a prévu d'historiser.

Nous jouons donc les deux rôles : celui de l'équipe qui construit l'entrepôt (collecte, nettoyage,
historisation) et celui du data scientist qui en extrait la table labellisée. Les trois niveaux du
projet correspondent aux couches d'un entrepôt :

| Notre niveau | Rôle dans un entrepôt | Règle |
|---|---|---|
| `data/raw/` | sources brutes, en lecture seule | octets reçus tels quels, chacun tracé par une empreinte SHA-256 ; une photo du jour est datée et n'est jamais remplacée |
| `data/clean/` | tables de faits et de dimensions | une table par objet, un sens précis pour une ligne, contrôles à chaque construction |
| `data/final/` (à faire) | table d'entraînement | une ligne = (substance, date d'observation), variables avant la date, label après |

La conséquence la plus importante : **l'historique, il a fallu le reconstruire**. Les archives de la
Wayback Machine jouent le rôle des chargements successifs d'un entrepôt. Comme nos photos datées ne
sont jamais réécrites, elles nous donnent aussi l'équivalent du *time travel* (diapo 66) : on peut
toujours relire ce qui était publié à une date donnée. Ce n'est pas vrai des sites eux-mêmes : l'AIFA
a retiré environ 1 500 entrées anciennes en 2026, un exemple réel de « données déjà chargées puis
modifiées » (diapo 64).

---

## 2. Ce que représente une ligne

Le cours insiste sur le fait qu'un nom de table ne dit pas ce qu'est une ligne (diapo 25), et que le
choix du grain est irréversible (diapo 24). Chez nous, les tables de faits n'ont pas toutes la même
nature, et cela change ce qu'on a le droit d'en faire.

| Table | Une ligne = | Nature | Conséquence |
|---|---|---|---|
| `ansm_signalements` | une déclaration d'un laboratoire à l'ANSM | fait **transactionnel** : écrit une fois, jamais modifié | la source la plus sûre pour le label : une date, un médicament, pas de révision |
| `ansm_observations`, `europe_observations` | une pénurie vue sur une photo de la liste | photo périodique, en **format long** (cours 2, diapo 31) | on reconstitue les épisodes à partir de la présence sur les photos successives |
| `shortage_events` | un épisode de pénurie dans un pays | fait **complété après coup** (*accumulating snapshot*, diapo 51) : le début est connu tôt, la fin plus tard | voir la section 3 : `fin` et `duree_jours` ne sont pas connues à la date où l'épisode commence |
| `penuries_fr_mensuel` | une substance × un mois | photo mensuelle agrégée | mélange un **stock** (pénuries en cours) et des **flux** (signalements, nouvelles pénuries) |

**Un signalement n'est pas une pénurie.** 250 lignes du classeur ANSM sont strictement identiques, et
1 492 signalements portent sur un médicament déjà signalé le même mois. Compter des signalements,
c'est mesurer l'activité de déclaration, pas le nombre de pénuries, comme compter des lignes
d'articles n'est pas compter des paniers. D'où une **cible binaire** : au moins un signalement dans la
fenêtre.

**Le grain du panel : une substance (code ATC5) × un mois.** Le code ATC5 est la seule clé commune à la
France, à l'Italie et à l'Allemagne (chaque pays a ses propres codes de médicaments), et c'est le
niveau auquel les questions sont posées (« une substance devient-elle vulnérable ? »). Le choix a un
coût que nous assumons : on ne peut plus distinguer, pour une même substance, la forme injectable de
la forme orale, sauf à en faire une variable agrégée (part des présentations injectables).

**Additivité.** Le nombre de pénuries affichées un mois donné est un stock : l'additionner sur douze
mois compterait douze fois une pénurie longue. On le lit à une date, ou on en prend la moyenne. Les
signalements et les nouvelles pénuries sont des flux, qu'on peut additionner. Ce n'est pas un détail :
le dashboard agrègera par trimestre et par classe, et c'est là que l'erreur se produirait.

---

## 3. Ce que veut dire une date : le cœur du projet

Le cours 1 tourne autour d'une idée : à la date d'observation *d*, une variable ne peut utiliser que
ce qui était **connu** avant *d*. Le piège est qu'une table contient souvent des valeurs exactes,
mais connues plus tard. Chez nous, un même épisode porte quatre dates différentes :

| Date | Sens | Utilisable pour une variable à *d* ? |
|---|---|---|
| `debut` | début déclaré de la pénurie | **non** : en France, la date exacte vient parfois de la BDPM après coup (médiane : 20 jours avant la publication) ; en Italie, 49 % des pénuries sont annoncées **avant** leur début |
| `publication` | première photo où l'épisode apparaît | **oui** : c'est le moment où le public le sait |
| `fin` | fin de la pénurie | seulement si `fin_connue_le < d` |
| `fin_connue_le` | photo où l'on voit que l'épisode est terminé | c'est la date qui autorise la lecture de `fin` et de la durée |

`publication` et `fin_connue_le` n'existaient pas au départ. Elles ont été ajoutées précisément parce
qu'une table complétée après coup ne garde pas la trace de ses états intermédiaires (diapo 51) : sans
elles, une variable « durée des pénuries passées » calculée en 2022 aurait lu des fins connues en 2024.

### Les dimensions aussi changent : la BDPM historisée

Décrire le marché de 2022 avec la base des médicaments de 2026 serait une fuite : un générique retiré
*à cause* d'une pénurie aurait disparu du passé. C'est le cas du cours où l'on joint la version
actuelle d'une dimension (diapo 48), avec la même particularité : aucun test sur la structure de la
table ne la détecte. Nous avons donc construit trois dimensions historisées (`bdpm_*_historique`) :
une ligne par version d'un médicament, d'une boîte ou d'un groupe générique, valable sur
`[valid_from, valid_to)`, comme une dimension de type 2 (diapo 46). La table d'entraînement les
joindra par une jointure *as-of* sur la clé du médicament et la date d'observation (diapo 49).

Deux écarts avec le cours, et pourquoi :

- **Les versions sont déduites de photos, pas d'un journal des modifications.** On ne sait pas quand
  un médicament a changé, seulement entre quelles photos. `valid_from` est donc la photo où l'on voit
  le changement pour la première fois. La date est approchée **par excès** : on n'utilise jamais une
  information avant qu'elle ait pu être publiée. On perd en précision, jamais dans le sens de la fuite.
- **Une partie des archives est inutilisable.** 51 des 121 archives BDPM ont été coupées à 1 Mio par la
  Wayback Machine (environ 5 300 médicaments au lieu de 14 000). Les garder ferait « disparaître » des
  milliers de médicaments puis les ferait « réapparaître » : de fausses versions. Elles sont écartées.
  Il reste des trous entre 06/2020 et 05/2024, pendant lesquels l'état du marché est celui de la
  dernière photo complète. Nous le traitons comme une limite, pas comme une valeur à inventer.

Pas de clé de substitution non plus : dans le cours, elle sert à relier un fait à l'état de la
dimension au moment du fait. Nos faits (signalements, épisodes) ne sont pas reliés à la BDPM au
moment où ils se produisent ; c'est la cohorte qui le sera, par la date d'observation.

### La latence de publication : ce qui sera connu au moment de prédire

Les adresses des classeurs de signalements contiennent leur date de mise en ligne : les signalements
de 2019 ont été publiés en octobre 2021, ceux de 2024 et 2025 le 1er avril 2026. **Un signalement est
connu du public 9 à 22 mois après sa date.** Le cours distingue deux usages de la même donnée
(diapos 8 et 52) :

- **pour entraîner**, hors ligne, la latence ne gêne pas : on construit les exemples passés avec des
  données aujourd'hui disponibles. Les signalements font un très bon **label** ;
- **pour prédire** au mois courant, un signalement récent n'est pas encore publié. Une variable
  « signalements des trois derniers mois » serait toujours remplie à l'entraînement et toujours vide
  en production : le modèle apprendrait sur une information qu'il n'aura jamais.

Conséquence pour la suite : l'historique **récent** d'une substance viendra de la page publique de
l'ANSM (publiée en continu, datée par `publication`), et les variables tirées des signalements ne
porteront que sur des années déjà publiées à *d*. La même logique vaut pour Open Medic (une année de
remboursements n'est complète qu'après sa fin : on utilise l'année précédente) et pour la liste
critique de l'UE, qui donne la date d'inscription de chaque substance.

Restent deux sources dont nous n'avons que la photo de 2026 : la liste MITM et les compositions. Une
substance devient rarement MITM, et la composition d'un médicament ne change pas ; le risque de fuite
est faible mais réel (une substance a pu être classée MITM *après* une pénurie). Nous le signalons
comme limite plutôt que de prétendre l'avoir résolu.

---

## 4. Jointures, valeurs manquantes et totaux

**Agréger avant de joindre.** Le tableau mensuel combine deux sources au grain substance × mois.
Chacune est d'abord agrégée à ce grain, puis jointe : joindre les signalements aux épisodes ligne à
ligne aurait multiplié les lignes (diapos 41-42). Les jointures sont écrites `how="left"` depuis la
liste complète des substances : `pd.merge` fait par défaut une jointure interne, qui aurait supprimé
sans message les substances jamais en pénurie (cours 2, diapo 14 ; cours 1, diapo 36), c'est-à-dire
la classe négative dont le modèle a besoin.

**Vide n'est pas zéro.** Dans `penuries_fr_mensuel`, un mois couvert par une source sans aucun
signalement vaut 0 ; un mois que la source ne couvre pas (signalements avant 2019, page ANSM avant
04/2021) reste vide. Remplacer ces vides par 0 dirait au modèle qu'il n'y a pas eu de pénurie, alors
qu'on ne le sait pas (diapo 37).

**Lignes sans substance.** Le cours remplace une clé introuvable par une ligne « Unknown » plutôt que
de supprimer la ligne (diapo 27). Nous ne le faisons pas, et c'est un choix : notre table finale est
indexée par substance, et une ligne sans substance ne peut être rattachée à aucune ligne du panel. En
revanche, nous appliquons la seconde moitié de la règle : **mesurer la part perdue** et la borner. À
chaque construction : 1,4 % des signalements, 7,1 % des fiches ANSM et 6,3 % des épisodes n'ont pas de
code ATC5 (surtout des préparations hospitalières et de l'homéopathie). Si une part dépasse son seuil,
la construction s'arrête.

**Totaux réconciliés.** Comparer un total avant et après une étape détecte une perte, mais pas deux
erreurs de sens opposé (diapo 44). Les contrôles vérifient donc à la fois des totaux (signalements
avec ATC = somme du panel mensuel) et des nombres de lignes (épisodes français et européens conservés
sans perte, clés uniques dans chaque table).

---

## 5. Des séries qui ne sont pas homogènes dans le temps

Le cours montre qu'un volume qui saute d'un mois à l'autre vient souvent d'un changement de source ou
de périmètre, pas du comportement étudié (diapo 30). Nous en avons trois :

- les signalements doublent entre 2021 (2 167) et 2023 (4 925) : crise réelle des antibiotiques, mais
  aussi obligations de déclaration renforcées ;
- l'Allemagne n'a d'archives qu'à partir de 07/2024 ; avant, son absence de signal veut dire « pas
  observé », pas « pas de pénurie » ;
- l'Italie a purgé ses anciennes entrées en 2026.

Conséquences : l'**année** sera une variable, pour que le modèle n'attribue pas la hausse aux
substances ; chaque variable européenne sera accompagnée d'un indicateur « pays observé à *d* » ; et
l'apport des signaux européens (question 2) sera mesuré **sur la période où ils existent**, pas sur
tout l'historique.

---

## 6. Stockage et formats (cours 2)

Nous avons suivi l'arbre de décision du cours, avec nos chiffres :

| Critère | Notre réponse | Conséquence |
|---|---|---|
| Volume | 480 Mo de brut, mais la plus grosse table nettoyée tient en 33 Mo de mémoire et le panel final fera environ 10 Mo | pandas + Parquet ; seule Open Medic (1,9 million de lignes par an) est lue **par morceaux** de 500 000 lignes, parce que l'opération (une somme) se calcule à partir de résultats partiels |
| Relations | les jointures sont faites une fois, à la construction, pas à chaque lecture | pas de SGBD ; SQLite avec un index ne se justifierait que si le dashboard refaisait les mêmes jointures à chaque interaction |
| Collaboration | deux personnes, mais jamais deux écrivains sur la même table : chacun régénère les données à partir du même code | git pour le code ; pas de PostgreSQL |
| Structure | schémas fixes, une fois la page HTML de l'ANSM aplatie en tableau | tables Parquet ; pas de base de documents |

**Les types sont déclarés, jamais devinés.** Les fichiers BDPM sont lus en texte (`dtype=str`) : les
codes CIS et CIP sont des identifiants, pas des nombres. Les dates sont lues avec leur format
explicite, l'encodage est détecté fichier par fichier. Les comptages qui peuvent être vides sont en
entiers nullables (`Int64`), pour garder la différence entre vide et zéro. Les colonnes à peu de
valeurs (pays, type d'épisode, gravité, criticité) sont en dtype `category` : leur empreinte mémoire
passe de 0,44 Mo à 0,04 Mo, et la gravité est une catégorie **ordonnée** (risque < tension < rupture),
ce qui rend son maximum significatif. Une fois écrite en Parquet, une table garde ses types : on ne
relit jamais le brut deux fois.

**Couche brute en lecture seule et lignage.** Les fichiers bruts ne sont jamais modifiés ; une
correction se fait dans le code de nettoyage. Chaque fichier a son empreinte dans `data/raw/manifeste.csv`,
revérifiée avant chaque nettoyage : si un brut a été modifié à la main, la construction s'arrête. Les
changements de données sont journalisés dans `CHANGELOG_DATA.md` (date, auteur, quoi, pourquoi).

---

## 7. Pouvoir dire si un écart vient du code ou des données

C'est l'objet du manifeste (cours 1, diapo 65). Chaque table nettoyée y est décrite par son nombre de
lignes, ses valeurs vides, la somme de chaque colonne numérique et une empreinte de son contenu, et sa
provenance par deux empreintes : celle du **code** de nettoyage et celle du **manifeste brut**. Une copie
datée est gardée dans `manifestes/`, suivie par git, pour rester disponible tout le projet (diapo 66).

Le cas s'est déjà produit : deux exécutions de la même version du code ont donné 16 842 et 16 769
épisodes. L'empreinte du brut différait, pas celle du code : l'écart venait de la photo du jour, plus
récente chez l'un que chez l'autre. Sans manifeste, on n'aurait pas pu trancher.

---

## 8. La suite : construire la table d'entraînement

Le plan suit l'ordre imposé par le cours (diapos 53 à 63), adapté à notre cas.

1. **Cohorte (fixe le grain).** Une ligne par substance et par mois d'observation *d*, pour les
   substances qui ont au moins un médicament commercialisé à *d* d'après la BDPM historisée.
   **Décision à prendre :** les signalements ne concernent que les médicaments d'intérêt thérapeutique
   majeur (MITM). Les substances qui en ont connaissent 12,1 % de mois avec un signalement, les autres
   1,2 %. Sans restriction, le modèle apprendrait surtout « MITM ou pas », ce qu'on sait déjà. Nous
   proposons de restreindre la cohorte aux substances MITM (1 223 sur 1 514).
2. **Variables**, chacune avec sa règle de date (section 3) : marché à *d* (as-of), historique récent
   par la page ANSM (`publication < d`), signalements des années déjà publiées, consommation de l'année
   précédente, criticité UE si inscrite avant *d*, cascade (autres substances de la même classe ATC4),
   signaux européens avec leur indicateur de couverture, mois et année.
3. **Label** : au moins un signalement dans les trois mois qui suivent *d*. Les dates dont la fenêtre
   dépasse 12/2025 (fin des signalements publiés) sont exclues : leur label serait incomplet, donc
   faussement négatif.
4. **Assemblage** par jointures à gauche sur la cohorte, chaque étape étant d'abord agrégée à une ligne
   par (substance, *d*). Puis vérification que le nombre de lignes est celui de la cohorte, qu'aucune
   valeur n'est vide sans raison, que le taux de positifs est plausible, et qu'aucune variable n'a lu un
   événement daté de *d* ou après.
5. **Découpage temporel, avec un écart de trois mois** entre entraînement, validation et test, pour
   qu'aucun signalement ne serve à la fois de label d'entraînement et de label de test (diapo 62) :
   entraînement 04/2019 → 09/2023, validation 01/2024 → 09/2024, test 01/2025 → 10/2025.
6. **Référence à battre** (« signalée récemment → signalée bientôt »), puis modèles **avec et sans** les
   variables de cascade et d'Europe : c'est ainsi que les questions 1 et 2 sont testées.
7. **Table de prédiction** : le même code, avec une seule date (le mois courant) et sans l'étape du
   label (diapo 63). La latence de la section 3 y est décisive : seules les variables disponibles au
   mois courant peuvent entrer dans le modèle.
8. **Rangement** (cours 2, diapos 32-34) : `data/final/panel_fr_v1_<date>.parquet` avec son manifeste,
   modèles sérialisés avec joblib dans `models/`, prédictions et métriques dans `outputs/`.

---

## 9. Limites que nous assumons

- La cible ne couvre que les MITM, seuls soumis à déclaration.
- L'état du marché entre 06/2020 et 05/2024 est approché par la dernière photo complète.
- La liste MITM et les compositions ne sont connues qu'à leur état de 2026.
- Les pénuries trop courtes pour apparaître entre deux archives sont invisibles côté page ANSM (pas
  côté signalements).
- Les définitions de « pénurie » diffèrent entre pays : les signaux européens sont des indicateurs, pas
  des mesures comparables.
- Une partie de la hausse des signalements est un effet de déclaration, pas de pénurie.
