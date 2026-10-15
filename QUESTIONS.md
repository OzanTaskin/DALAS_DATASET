# Questions de recherche — version préliminaire (05/10/2026, révisée)

> Ces questions portent sur le monde réel (l'énoncé exige des questions sur le monde réel, pas sur le dataset).
> Elles pourront être affinées au fil du semestre (cf. FAQ de l'énoncé).

**Titre de travail : Les pénuries de médicaments en France — prévisibles, contagieuses, importées ?**

## Pourquoi recentrer sur la France

Seule la France publie l'**univers complet** des médicaments commercialisés (BDPM), donc aussi ceux qui ne sont jamais en pénurie.
C'est indispensable pour prédire. L'Italie et l'Allemagne ne publient que leurs listes de pénuries.
On les utilise donc comme **signaux extérieurs**, sur le même ensemble de substances (codes ATC5) que la France.

## Question principale — prévisibilité

**Peut-on anticiper les pénuries de médicaments en France, et quels facteurs rendent une substance vulnérable ?**

- Formulation opérationnelle : pour une substance active (ATC5) au mois *t*, quelle est la probabilité qu'une nouvelle pénurie (rupture ou tension) soit déclarée en France entre *t+1* et *t+3* ?
- Facteurs candidats : nombre de laboratoires et de génériques, forme (injectable ou orale), volume consommé, criticité (MITM, liste critique UE), classe thérapeutique, saison, pénuries passées.

## Question 1 — contagion entre substituts (« effet cascade »)

**Une pénurie en France se propage-t-elle aux médicaments de substitution ?**

- Le risque de pénurie d'une substance augmente-t-il quand d'autres substances de la même classe thérapeutique (ATC4) sont déjà en pénurie ?
- Exemple attendu : amoxicilline → amoxicilline/acide clavulanique, céphalosporines.

## Question 2 — pénuries « importées » d'Europe

**Les pénuries chez nos voisins européens (Italie, Allemagne) annoncent-elles des pénuries en France ?**

- Une pénurie de la même substance déclarée à l'étranger dans les mois précédents augmente-t-elle le risque en France ?
- Ce signal européen améliore-t-il la prédiction (modèle avec / sans variables européennes) ?
- Quels pays signalent en premier ?

## Ce qu'on ne prétend pas faire

- Prédire la date exacte d'une pénurie.
- Prédire les pénuries dans les autres pays, du moins pour l'instant : leur univers de médicaments n'est pas disponible (piste d'extension : direction A du README).
- Expliquer les causes industrielles précises (usines, matières premières) : ces données ne sont pas publiques.
