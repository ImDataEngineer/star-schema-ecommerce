> *Also available in [French](./README.fr.md).*

[![Template](https://img.shields.io/badge/repo-template-1e293b?style=flat-square)](https://github.com/ImDataEngineer/star-schema-ecommerce/generate) [![iamdataeng.com](https://img.shields.io/badge/iamdataeng.com-2563eb?style=flat-square)](https://iamdataeng.com/projects/modeling.star-schema-ecommerce)

> **Context.** Coursework template from [iamdataeng.com/projects/modeling.star-schema-ecommerce](https://iamdataeng.com/projects/modeling.star-schema-ecommerce). Fork, complete the TODO blocks, push, receive a pedagogical CI verdict. Not a maintained open-source project, an evaluated exercise.

# Kimball star schema with integrity proven in CI — `modeling.star-schema-ecommerce`

> **Level**: intermediate (mid) · **Estimated time**: ~14 h
> **Framework axis**: `transformation` · secondary: `storage`, `software_engineering_dataops`
> **Prerequisites**: advanced SQL (CTEs, windows, aggregates), dbt basics, Git PR workflow

This project is your interview flagship. When a recruiter asks "tell me
about your last dimensional modeling project", this is the one. Not a
tutorial. An exercise that demands explicit grain, conformed dimensions,
role-playing, and a defended ADR — precisely the things 80% of
candidates fumble in the room.

---

## The context

Rundle, a scooter-sharing operator, just migrated its OLTP base from
Google Sheets to a real Postgres (that was the `storage.oltp-postgres-design`
project — not required, but episode 1 of the same fictional arc). Now
the analytics team wants reconciled numbers:

- **Finance**: "revenue by channel × country × month."
- **Product**: "conversion funnel by onboarding cohort."
- **Ops**: "return volume by channel × country."

Today every analyst writes their joins their own way, and no two
numbers ever agree. Your job: build a **conformed** star schema on top
of the OLTP dump, where *every* analytical question routes through the
same dimensions, and where every fact's grain is **mechanically**
verified — not just documented in prose.

The warehouse is Postgres 16. The transformation layer is dbt-core 1.7.
No Spark, no Snowflake, no Iceberg — well-written dbt on Postgres is
plenty for 500k rows. (If you disagree with that call, that's exactly
what your ADR is for.)

---

## The stack you'll operate

| Layer | Tech | Role |
|---|---|---|
| Source | Postgres 16, schema `bronze` | OLTP dump loaded by `fixtures/load_bronze.py` (7 tables) |
| Staging | dbt views, schema `staging` | Typing and light renaming, **no** business logic |
| Marts | dbt tables, schema `marts` | 5 conformed dims + 2 facts (different grains) |
| Tests | dbt generic + 3 singular tests + pytest | Grain, FK, conformed-dim, role-playing |
| Lint | sqlfluff (postgres dialect) | SQL style before merge |
| CI | GitHub Actions | Postgres service + `dbt build` + `pytest` |

The devcontainer brings up a Postgres in Docker, installs dbt-core +
dbt-postgres + sqlfluff, generates the fixtures (~500k order lines),
and loads `bronze`. You write staging + marts.

---

## What you ship

| Deliverable | Where |
|---|---|
| Staging models (7 files, already skeletoned with `where false`) | `models/staging/stg_*.sql` |
| Conformed dimensions | `models/marts/dim_customer.sql`, `dim_product.sql`, `dim_channel.sql`, `dim_country.sql`, `dim_date.sql` |
| Fact tables (2, different grains) | `models/marts/fct_order_lines.sql`, `fct_returns.sql` |
| dbt structure tests | `models/marts/_schema.yml` (partial — fill in the TODOs) |
| dbt singular tests | `tests/grain_order_line.sql`, `conformed_dim_customer.sql`, `role_playing_date.sql` (provided, do not modify) |
| ADR | `docs/adr/001-star-vs-snowflake-vs-obt.md` (stub to fill in) |

---

## Grain — the single most important thing in this project

You're going to write the following sentence in the header of
`fct_order_lines.sql`:

> Grain: one row per (`order_id`, `line_number`).

That sentence has two non-negotiable corollaries:

1. **Any query on the fact that aggregates by order_id will sum distinct
   rows.** If you accidentally cartesian-join a non-deduplicated dim,
   your fact doubles, and the singular test
   `tests/grain_order_line.sql` fires — exactly what it's there for.
2. **You do not put dim attributes on the fact.** The customer's name
   lives on `dim_customer`. On the fact, it's `sk_customer` and nothing
   else. The columns you keep on the fact besides FKs: `order_id` and
   `line_number` (degenerate dimensions) + the measures.

Grain in prose is documentation. Grain as `having count(*) > 1` is a
proven invariant. You do both.

---

## Conformed dimensions — the other thing that matters

A **conformed** dimension is a dim used by multiple facts in the same
spot of the warehouse, with the **same** SK for the same business
attribute. Concretely:

- `dim_country` is joinable from `fct_order_lines` (on ship-to country)
  AND from `fct_returns` (same ship-to country). One materialized
  `dim_country`, two usages.
- `dim_customer` is joinable from `fct_order_lines` (the customer of the
  order) AND from `fct_returns` (the customer of the return). One
  `dim_customer`, two facts. That's what the singular test
  `tests/conformed_dim_customer.sql` checks: no row in `fct_returns` can
  point at an `sk_customer` missing from `dim_customer`.

The classic trap: you filter `dim_customer` down to "active" customers
because that's what today's dashboard wants. Consequence: rows in
`fct_returns` (which include returns from now-inactive customers) go
orphan. And check 6 fires.

The Kimball rule: **never filter a conformed dim to fit a particular
use case**. A conformed dim belongs to *every* fact.

---

## Role-playing: `dim_date` joined twice, **materialized once**

`fct_order_lines` carries two dates: `order_date` and `ship_date`. Both
resolve to `dim_date`. The right reflex:

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

One CTE = one alias = one usage. **You did not create `dim_order_date.sql`
or `dim_ship_date.sql`.** That model duplication is exactly what
role-playing makes unnecessary.

---

## Getting started

If you're in GitHub Codespaces, the devcontainer has already:
- started Postgres 16 (port 5432, database `rundle_warehouse`),
- generated the 7 CSV fixtures,
- loaded `bronze`,
- copied `profiles.yml.example` to `.dbt/profiles.yml`,
- run `dbt debug` to verify the connection.

Otherwise, locally:

```bash
# 1. Start Postgres
docker compose -f .devcontainer/docker-compose.yml up -d

# 2. Install dependencies
pip install -r requirements.txt

# 3. Generate fixtures (deterministic, seed=42, ~500k order lines)
python -m fixtures.generate_fixtures

# 4. Load bronze
python -m fixtures.load_bronze

# 5. Copy the dbt profile
mkdir -p .dbt && cp profiles.yml.example .dbt/profiles.yml

# 6. Verify the dbt connection
dbt debug --profiles-dir .dbt

# 7. Iterate: implement your models, run dbt build
dbt build --profiles-dir .dbt

# 8. Once dbt build passes, run the full rubric
pytest tests/ -v
```

Once the 6 pytest checks pass locally, **commit + push** to your fork.
GitHub Actions CI replays the same rubric and the IamDataEngineer app
displays the verdict in your dashboard.

---

## The 6 rubric checks

All deterministic, all explained in plain English on failure.

| # | Id | What we check |
|---|---|---|
| 1 | `adr_present` | `docs/adr/001-star-vs-snowflake-vs-obt.md` exists, contains > 200 chars of real content, the placeholder has been removed, and the MADR sections (Context, Decision, Consequences, Alternatives) are present. |
| 2 | `fk_coverage_static` | YAML read of `models/marts/_schema.yml`. For `fct_order_lines`, each of the 6 expected FK columns (`sk_customer`, `sk_product`, `sk_channel`, `sk_country_ship`, `order_date_key`, `ship_date_key`) is declared WITH a `relationships` test against the right dim. |
| 3 | `sqlfluff_passes` | `sqlfluff lint models/` returns 0 against the `.sqlfluff` config (postgres dialect). |
| 4 | `dbt_build_passes` | `dbt build --target ci` runs all models + all dbt tests without error. Includes the 3 singular tests (`grain_order_line`, `conformed_dim_customer`, `role_playing_date`). |
| 5 | `grain_unique` | On the materialized `marts.fct_order_lines` table, `COUNT(*) == COUNT(DISTINCT (order_id, line_number))`. Redundant with the singular test — intentionally. |
| 6 | `conformed_customer` | On the materialized tables: no row in `marts.fct_returns` has an `sk_customer` missing from `marts.dim_customer`. |

---

## The traps we've seen mids fall into

Seen in PR review five times this year:

- **Declaring grain "one row per order"... and implementing one row per
  order_line.** When grain lives in a README and nowhere in the code, it
  doesn't exist. The sentence goes in the model header, the `having
  count(*) > 1` test goes in `tests/grain_order_line.sql`. Both in
  agreement.

- **Snowflaking "because normalization".** If `dim_product` is small (2k
  rows here) and the product → category hierarchy has 6 entries,
  splitting `dim_product` + `dim_category` adds a join for zero
  analytical gain. Snowflaking is for reusable, voluminous dims (e.g.
  dim_location with a deep geo hierarchy shared across 5 dims). Justify
  it in the ADR.

- **Forgetting that `ship_date` also needs `dim_date`.** Role-playing is
  exactly there to prevent one analyst writing `where order_date >= ...`
  and another writing `where to_date(ship_date) >= ...`. One dim, two
  aliases, done.

- **Putting natural keys on the fact.** The fact's FKs are **surrogates**
  (`sk_customer`, `sk_product`, etc.). `order_id` and `line_number` stay
  on it as degenerate dimensions because no meaningful `dim_order`
  exists — but raw `customer_id`, `product_id`, no.

- **Filtering a conformed dim to fit a use case.** If you write
  `dim_customer = select * from stg_customers where is_active = true`,
  you break conformity with `fct_returns`. A conformed dim is not
  filtered, it's exhaustive.

- **Non-deterministic surrogate key.** `row_number() over ()` without
  ORDER BY gives you a different SK on every `dbt run` — `dbt build`
  passes once, breaks the next run when the FKs no longer resolve.
  Either `md5(natural_key::text)`, or `dense_rank() over (order by
  natural_key)`. Document your choice.

- **Building a `dim_order`.** `order_id` is a **degenerate dimension**:
  it lives on the fact, and there's no dim for it because it has no
  attributes of its own (its attributes already live elsewhere:
  customer, channel, country, date). If you find yourself starting
  `dim_order.sql`, stop and re-read Kimball ch. 3.

- **Building an SCD2 for `dim_product`.** The dump represents the
  CURRENT state of the OLTP. ~2% of products were renamed during the
  period — that's an overwrite (SCD1), not historical tracking (SCD2).
  The `transformation.scd2-merge` project (V1) covers SCD2 when you
  actually need it. Here, SCD1.

---

## Going further (references)

No reading is mandatory to pass, but these sources structure the rubric:

- Kimball & Ross, *The Data Warehouse Toolkit*, 3rd ed. — **Ch. 1 to 3**
  on grain, conformed dims, surrogate keys, role-playing. It's *the*
  book. If you read only one for this project, this is it.
- Reis & Housley, *Fundamentals of Data Engineering* — **Ch. 8
  (Transformation), pp. 280-295** on modeling patterns.
- dbt docs: [Generic tests](https://docs.getdbt.com/reference/resource-properties/data-tests),
  [Singular tests](https://docs.getdbt.com/best-practices/writing-custom-generic-tests),
  [Model contracts](https://docs.getdbt.com/docs/collaborate/govern/model-contracts).
- Lauri Ikonen, *Kimball in the lakehouse era* (2023) — how conformed
  dims hold up when dbt + Iceberg replace the old warehouse.
- MADR template — [github.com/adr/madr](https://github.com/adr/madr).

---

## If you're stuck

The project is sized for 14 h. If you're spinning past that:

1. Re-read the error message — it almost always points at the precise
   cause.
2. Run `dbt build --profiles-dir .dbt` and look at the **first** red
   test in the output, not the last.
3. Inspect the compiled SQL in `target/run/rundle_warehouse/models/marts/`
   — that's what Postgres actually executes, not what you wrote in the
   Jinja template.
4. Open an issue on your fork with the `help-wanted` label — the
   IamDataEngineer community hangs out there.

Good luck.
