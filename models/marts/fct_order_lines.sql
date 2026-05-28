-- fct_order_lines — THE fact table for this warehouse.
--
-- Grain (declared explicitly — and enforced mechanically by
-- tests/grain_order_line.sql):
--
--     one row per (order_id, line_number)
--
-- Foreign keys (all SURROGATE — no natural keys on the fact except the two
-- degenerate dims order_id and line_number):
--
--     sk_customer        -> dim_customer
--     sk_product         -> dim_product
--     sk_channel         -> dim_channel
--     sk_country_ship    -> dim_country  (ship-to country, from orders.country_code)
--     order_date_key     -> dim_date     (role-playing — same dim_date)
--     ship_date_key      -> dim_date     (role-playing — same dim_date)
--
-- Measures (additive at this grain): quantity, unit_price_eur, discount_eur,
-- line_amount_eur (= quantity * unit_price_eur - discount_eur, computed in
-- stg_order_lines).
--
-- TODO(learner):
--   1. Start FROM stg_order_lines. That defines the grain.
--   2. LEFT JOIN stg_orders to get order_date, ship_date, channel_id, country_code, customer_id.
--      LEFT JOIN — not INNER — so that if you chose the "drop orphans" approach
--      in staging, the staging filter is what removes them, not a fact join.
--   3. Resolve every FK by joining to the dim and selecting the dim's surrogate key.
--      Watch out: when you join dim_customer, make sure the dim has ONE row per
--      customer_id. If you SELECT * from dim_customer and dim has 2 rows for the
--      same natural key (because of, say, the unknown-customer sentinel using -1
--      and a real customer accidentally being -1), you fan out the fact — and
--      grain_order_line.sql fails.
--   4. Role-play dim_date: two CTEs (dim_order_date as ..., dim_ship_date as ...)
--      both pointing at {{ ref('dim_date') }}.

{{ config(materialized='table') }}

with order_lines as (
    select * from {{ ref('stg_order_lines') }}
),

orders as (
    select * from {{ ref('stg_orders') }}
)

-- TODO(learner): join the dims here and produce the fact.
select
    null::bigint  as order_id,
    null::integer as line_number,
    null::text    as sk_customer,
    null::text    as sk_product,
    null::text    as sk_channel,
    null::text    as sk_country_ship,
    null::integer as order_date_key,
    null::integer as ship_date_key,
    null::integer as quantity,
    null::numeric as unit_price_eur,
    null::numeric as discount_eur,
    null::numeric as line_amount_eur
from order_lines
where false
