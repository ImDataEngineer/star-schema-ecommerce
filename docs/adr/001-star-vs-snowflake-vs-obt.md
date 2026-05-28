# ADR 001 — Star schema vs Snowflake vs One Big Table pour Rundle

> **Status** — `Proposed` | `Accepted` | `Superseded`
> **Date** — _à remplir_
> **Decider(s)** — _à remplir_
> **ADR placeholder — replace before submission_

<!--
Ce fichier suit le format MADR (Markdown Architecture Decision Record).
Voir : https://github.com/adr/madr

Le CI vérifie que :
  1. Le fichier existe et fait > 200 caractères de contenu réel.
  2. Le placeholder ci-dessus a été retiré (oui, vraiment ce string littéral).
  3. Les sections Context, Decision, Consequences, Alternatives Considered
     sont présentes.

Le contenu de ta décision n'est PAS noté par le CI — c'est ton entretien qui
le notera. Sois honnête sur les trade-offs. Si tu choisis OBT pour de bonnes
raisons (équipe < 10 analystes, DuckDB en serving, latence pas critique),
c'est défendable. Si tu choisis Star "parce que c'est Kimball", c'est une
réponse à mi-mot — défends-la avec des chiffres.
-->

## Context

_Décris la situation. Quelques pointeurs utiles à mentionner :_
- _Volume actuel : ~500k order lines, 3 ans d'historique, 50k clients._
- _Croissance attendue (10x dans 12 mois ? 2x ?)._
- _Charges analytiques principales (revenue par mois × pays, conversion funnel, retours)._
- _Stack de serving (dbt + Postgres ici ; demain dbt + Snowflake ? + DuckDB ?)._
- _Taille de l'équipe analyste / data engineer._

## Decision

_Énonce ta décision en UNE phrase. Exemple : « Nous adoptons un star schema
Kimball classique (5 dims conformées + 2 facts à grains différents) parce
que […]. »_

## Consequences

_Ce que tu gagnes ET ce que tu paies. Au minimum :_
- _Bénéfices opérationnels (réutilisation des dims, intelligibilité, alignement
  finance/produit sur les mêmes nombres)._
- _Coût de maintenance (nombre de modèles dbt, complexité des jointures)._
- _Effets de bord sur la performance (joins à chaque requête vs flat OBT)._
- _Ce qui DEVIENT difficile à faire (par ex. : SCD2 sur products nécessite
  une refonte non-triviale)._

## Alternatives Considered

### Snowflake schema (normalisation profonde des dims)

_Quand est-ce pertinent ? (hiérarchies réutilisables, dim_product gigantesque,
forte pression d'espace). Quand est-ce du sur-engineering ? (2k produits,
1 hiérarchie product → category, requêtes BI simples)._

_Conclusion : retenu / rejeté parce que ___._

### One Big Table (OBT — un seul wide table dénormalisé)

_Avantages : zéro jointure runtime, parfait pour DuckDB / BigQuery / Athena
sur petite équipe. Inconvénients : duplication massive de l'attribut client
sur 500k lignes, ré-écriture complète si un attribut de dim change, pas de
réutilisation entre fact tables._

_Conclusion : retenu / rejeté parce que ___._

### Star schema (la décision retenue, ou pas)

_Pourquoi cette décision est défendable pour CE volume et CE workload, pas
parce que c'est ce que dit Kimball._

## Notes

_Si tu changes d'avis dans 6 mois, c'est ici que la prochaine ADR (002) doit
être référencée. Ne ré-écris pas cette ADR — on dépreciate, on remplace._

## References

- Kimball & Ross, *The Data Warehouse Toolkit*, 3rd ed., Ch. 1-3.
- Reis & Housley, *Fundamentals of Data Engineering*, Ch. 8.
- MADR template — https://github.com/adr/madr
