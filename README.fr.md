# Star schema Kimball avec intégrité prouvée en CI — `modeling.star-schema-ecommerce`

> **Niveau** : intermédiaire (mid) · **Durée estimée** : ~14 h
> **Axe framework** : `transformation` · accessoires : `storage`, `software_engineering_dataops`
> **Prérequis** : SQL avancé (CTE, fenêtres, agrégats), bases dbt, Git PR workflow

Ce projet est ton flagship d'entretien. Quand un recruteur te demande
« raconte-moi ton dernier projet de modélisation dimensionnelle », c'est
celui-là. Pas un tuto. Un exercice qui exige du grain explicite, des
dimensions conformées, du role-playing, et un ADR défendu — exactement les
choses que 80 % des candidats fument à l'oral.

---

## Le contexte

Rundle, scooters en libre-service, a passé sa base OLTP de Google Sheets à
un vrai Postgres (c'était le projet `storage.oltp-postgres-design` — pas
obligatoire, mais c'est l'épisode 1 de la même fiction). Maintenant
l'équipe analytics veut des chiffres réconciliés :

- **Finance** : « revenue par canal × pays × mois ».
- **Produit** : « tunnel de conversion par cohorte d'onboarding ».
- **Ops** : « volume de retours par canal × pays ».

Aujourd'hui chaque analyste écrit ses jointures à sa sauce, et les deux
nombres ne tombent jamais d'accord. Ton job : construire un star schema
**conformé** au-dessus du dump OLTP, où *toutes* les questions analytiques
passent par les mêmes dimensions, et où le grain de chaque fact est
**mécaniquement** vérifié — pas juste documenté en prose.

Le warehouse est Postgres 16. La transformation, c'est dbt-core 1.7. Pas de
Spark, pas de Snowflake, pas d'Iceberg — un bon dbt sur Postgres suffit
pour 500k lignes. (Si tu n'es pas d'accord avec ce choix, c'est exactement
ce que ton ADR devra trancher.)

---

## La stack que tu vas opérer

| Couche | Tech | Rôle |
|---|---|---|
| Source | Postgres 16, schéma `bronze` | Dump OLTP chargé par `fixtures/load_bronze.py` (7 tables) |
| Staging | dbt views, schéma `staging` | Typage et renommage léger, **pas** de logique métier |
| Marts | dbt tables, schéma `marts` | 5 dims conformées + 2 facts (grains différents) |
| Tests | dbt generic + 3 singular tests + pytest | Grain, FK, conformed-dim, role-playing |
| Lint | sqlfluff (dialecte postgres) | Style SQL avant merge |
| CI | GitHub Actions | Postgres service + `dbt build` + `pytest` |

Le devcontainer monte un Postgres dans Docker, installe dbt-core +
dbt-postgres + sqlfluff, génère les fixtures (~500k order lines), et
charge `bronze`. Tu écris staging + marts.

---

## Ce que tu vas livrer

| Livrable | Où |
|---|---|
| Staging models (7 fichiers, déjà squelettés avec des `where false`) | `models/staging/stg_*.sql` |
| Dimensions conformées | `models/marts/dim_customer.sql`, `dim_product.sql`, `dim_channel.sql`, `dim_country.sql`, `dim_date.sql` |
| Fact tables (2, grains différents) | `models/marts/fct_order_lines.sql`, `fct_returns.sql` |
| Tests de structure dbt | `models/marts/_schema.yml` (déjà partiel — tu complètes les TODO) |
| Singular tests dbt | `tests/grain_order_line.sql`, `conformed_dim_customer.sql`, `role_playing_date.sql` (fournis, ne pas modifier) |
| ADR | `docs/adr/001-star-vs-snowflake-vs-obt.md` (stub fourni à remplir) |

---

## Le grain — la chose la plus importante de ce projet

Tu vas écrire dans le header de `fct_order_lines.sql` la phrase suivante :

> Grain : une ligne par (`order_id`, `line_number`).

Cette phrase a deux corollaires non-négociables :

1. **Toute requête sur la fact qui agrège par order_id sommera des lignes
   distinctes.** Si tu fais accidentellement une jointure cartésienne avec
   un dim non-dédupliqué, ta fact double, et le singular test
   `tests/grain_order_line.sql` tombe — c'est exactement à ça qu'il sert.
2. **Tu ne mets pas d'attributs de dim sur la fact.** Le nom du client est
   sur `dim_customer`. Sur la fact, c'est `sk_customer` et rien d'autre.
   Les colonnes que tu gardes sur la fact en plus des FK : `order_id` et
   `line_number` (degenerate dimensions) + les measures.

Le grain en prose, c'est de la doc. Le grain en `having count(*) > 1`,
c'est un invariant prouvé. Tu fais les deux.

---

## Les dimensions conformées — l'autre chose importante

Une dimension **conformée**, c'est une dim utilisée par plusieurs facts au
même endroit dans le warehouse, avec le **même** SK pour le même
attribut métier. Concrètement :

- `dim_country` est joinable depuis `fct_order_lines` (sur la ship-to
  country) ET depuis `fct_returns` (même ship-to country). Un seul
  `dim_country` matérialisé, deux usages.
- `dim_customer` est joinable depuis `fct_order_lines` (le client de
  la commande) ET depuis `fct_returns` (le client du retour). Un seul
  `dim_customer`, deux facts. C'est ce que le singular test
  `tests/conformed_dim_customer.sql` vérifie : aucune ligne de
  `fct_returns` ne doit pointer vers un `sk_customer` absent de
  `dim_customer`.

Le piège classique : tu filtres `dim_customer` aux clients « actifs »
parce que c'est ce que ton dashboard du moment veut. La conséquence :
`fct_returns` (qui inclut les retours de clients devenus inactifs)
orpheline. Et le check 6 tombe.

La règle Kimball : **ne filtre jamais une dim conformée selon un usage
particulier**. Une dim conformée appartient à *toutes* les facts.

---

## Role-playing : `dim_date` joint deux fois, **une seule fois matérialisé**

`fct_order_lines` porte deux dates : `order_date` et `ship_date`. Les deux
résolvent à `dim_date`. Le bon réflexe :

```sql
with dim_order_date as (select * from {{ ref('dim_date') }}),
     dim_ship_date  as (select * from {{ ref('dim_date') }}),
     ...
select
    ...,
    dim_order_date.date_key as order_date_key,
    dim_ship_date.date_key  as ship_date_key,
    ...
from stg_order_lines ol
left join stg_orders o on ol.order_id = o.order_id
left join dim_order_date on dim_order_date.date_iso = o.order_date
left join dim_ship_date  on dim_ship_date.date_iso  = o.ship_date
```

Une CTE = un alias = un usage. **Tu n'as pas créé `dim_order_date.sql` ni
`dim_ship_date.sql`.** Cette duplication de modèle est exactement ce que
le role-playing rend inutile.

---

## Comment commencer

Si tu es dans GitHub Codespaces, le devcontainer a déjà :
- démarré Postgres 16 (port 5432, base `rundle_warehouse`),
- généré les 7 fixtures CSV,
- chargé `bronze`,
- copié `profiles.yml.example` vers `.dbt/profiles.yml`,
- exécuté `dbt debug` pour vérifier la connexion.

Sinon, en local :

```bash
# 1. Démarre Postgres
docker compose -f .devcontainer/docker-compose.yml up -d

# 2. Installe les dépendances
pip install -r requirements.txt

# 3. Génère les fixtures (déterministe, seed=42, ~500k order lines)
python -m fixtures.generate_fixtures

# 4. Charge bronze
python -m fixtures.load_bronze

# 5. Copie le profile dbt
mkdir -p .dbt && cp profiles.yml.example .dbt/profiles.yml

# 6. Vérifie la connexion dbt
dbt debug --profiles-dir .dbt

# 7. Itère : implémente tes modèles, lance dbt build
dbt build --profiles-dir .dbt

# 8. Quand dbt build passe, lance la rubric complète
pytest tests/ -v
```

Quand les 6 checks pytest passent en local, **commit + push** sur ton fork.
La CI GitHub Actions rejoue la même rubric et l'app IAmDataEng affiche le
verdict dans ton dashboard.

---

## Les 6 checks de la rubric

Tous déterministes, tous expliqués en clair quand ils échouent.

| # | Id | Ce qu'on vérifie |
|---|---|---|
| 1 | `adr_present` | `docs/adr/001-star-vs-snowflake-vs-obt.md` existe, contient > 200 caractères de contenu réel, le placeholder a été retiré, et les sections MADR (Context, Decision, Consequences, Alternatives) sont présentes. |
| 2 | `fk_coverage_static` | Lecture YAML de `models/marts/_schema.yml`. Pour `fct_order_lines`, chacune des 6 colonnes FK attendues (`sk_customer`, `sk_product`, `sk_channel`, `sk_country_ship`, `order_date_key`, `ship_date_key`) est déclarée AVEC un test `relationships` vers le bon dim. |
| 3 | `sqlfluff_passes` | `sqlfluff lint models/` retourne 0 contre la config `.sqlfluff` (dialecte postgres). |
| 4 | `dbt_build_passes` | `dbt build --target ci` exécute tous les models + tous les tests dbt sans erreur. Inclut les 3 singular tests (`grain_order_line`, `conformed_dim_customer`, `role_playing_date`). |
| 5 | `grain_unique` | Sur la table matérialisée `marts.fct_order_lines`, `COUNT(*) == COUNT(DISTINCT (order_id, line_number))`. Redondant avec le singular test — c'est volontaire. |
| 6 | `conformed_customer` | Sur les tables matérialisées : aucune ligne de `marts.fct_returns` n'a un `sk_customer` absent de `marts.dim_customer`. |

---

## Les pièges qu'on a vus chez les mids

Vu en revue de PR cinq fois cette année :

- **Déclarer le grain « une ligne par order »… et implémenter une ligne par
  order_line.** Quand le grain est en prose dans un README et nulle part
  dans le code, il n'existe pas. La phrase est dans le header du model,
  le test `having count(*) > 1` est dans `tests/grain_order_line.sql`. Les
  deux d'accord.

- **Snowflaker « parce que normalisation ».** Si `dim_product` est petit
  (2k lignes ici) et la hiérarchie product → category a 6 entrées,
  splitter `dim_product` + `dim_category` ajoute une jointure pour zéro
  gain analytique. Le snowflake est pour des dims réutilisables et
  volumineuses (e.g. dim_location avec une hiérarchie geo profonde
  partagée entre 5 dims). Justifie-le dans l'ADR.

- **Oublier que `ship_date` aussi a besoin de `dim_date`.** Le role-playing,
  c'est exactement pour éviter qu'un analyste écrive `where order_date >= ...`
  d'un côté et `where to_date(ship_date) >= ...` de l'autre. Une dim,
  deux aliases, fini.

- **Mettre les clés naturelles sur la fact.** Les FK de la fact sont des
  **surrogates** (`sk_customer`, `sk_product`, etc.). `order_id` et
  `line_number` y restent comme degenerate dimensions parce qu'il n'y a
  pas de `dim_order` qui aurait du sens — mais `customer_id`, `product_id`
  brut, non.

- **Filtrer une dim conformée selon l'usage.** Si tu fais
  `dim_customer = select * from stg_customers where is_active = true`,
  tu casses la conformité avec `fct_returns`. Une dim conformée ne se
  filtre pas, elle est exhaustive.

- **Surrogate key non-déterministe.** `row_number() over ()` sans ORDER BY
  te donne un SK différent à chaque `dbt run` — `dbt build` passe une fois,
  casse au prochain run quand les FK ne résolvent plus. Soit `md5(natural_key::text)`,
  soit `dense_rank() over (order by natural_key)`. Documente ton choix.

- **Construire un `dim_order`.** `order_id` est une **degenerate dimension** :
  elle vit sur la fact, il n'y a pas de dim pour elle parce qu'elle n'a pas
  d'attributs propres (ses attributs sont déjà ailleurs : client, canal,
  pays, date). Si tu commences à écrire `dim_order.sql`, arrête-toi et
  relis Kimball Ch. 3.

- **Construire un SCD2 pour `dim_product`.** Le dump représente l'état
  COURANT de l'OLTP. ~2 % des produits ont été renommés en cours de
  période — c'est de l'overwrite (SCD1), pas du tracking historique
  (SCD2). Le projet `transformation.scd2-merge` (V1) couvre SCD2 quand
  tu en as vraiment besoin. Ici, SCD1.

---

## Pour aller plus loin (références)

Aucune lecture obligatoire pour valider, mais ces sources structurent la
rubric :

- Kimball & Ross, *The Data Warehouse Toolkit*, 3rd ed. — **Ch. 1 à 3** sur
  le grain, les dims conformées, les surrogate keys, le role-playing. C'est
  *le* livre. Si tu n'en lis qu'un sur ce projet, c'est celui-là.
- Reis & Housley, *Fundamentals of Data Engineering* — **Ch. 8 (Transformation),
  pp. 280-295** sur les patterns de modélisation.
- dbt docs : [Generic tests](https://docs.getdbt.com/reference/resource-properties/data-tests),
  [Singular tests](https://docs.getdbt.com/best-practices/writing-custom-generic-tests),
  [Model contracts](https://docs.getdbt.com/docs/collaborate/govern/model-contracts).
- Lauri Ikonen, *Kimball in the lakehouse era* (2023) — comment les dims
  conformées tiennent quand dbt + Iceberg remplacent l'ancien warehouse.
- MADR template — [github.com/adr/madr](https://github.com/adr/madr).

---

## Si tu es bloqué

Le projet est dimensionné pour 14 h. Si tu galères au-delà :

1. Relis le message d'erreur — il pointe presque toujours la cause précise.
2. Lance `dbt build --profiles-dir .dbt` et regarde le **premier** test
   rouge dans la sortie, pas le dernier.
3. Inspecte le SQL compilé dans `target/run/rundle_warehouse/models/marts/`
   — c'est ce que Postgres exécute, pas ce que tu as écrit dans le
   template Jinja.
4. Ouvre une issue dans ton fork avec le label `help-wanted` — la
   communauté IAmDataEng y passe.

Bonne route.
