-- fct_returns — second fact, exists primarily to exercise conformed-dim discipline.
--
-- Grain: one row per returned order (i.e. orders.status = 'returned').
--   This is a different grain from fct_order_lines (which is one row per line).
--   That's the point: two facts at DIFFERENT grains must STILL share the SAME
--   conformed dimensions. If your dim_customer works for one fact but not the
--   other, you don't have conformed dims.
--
-- Foreign keys (surrogate):
--     sk_customer        -> dim_customer
--     sk_channel         -> dim_channel
--     sk_country_ship    -> dim_country
--     return_date_key    -> dim_date   (we approximate with ship_date — Rundle's
--                                       OLTP dump doesn't carry an explicit return_date)
--
-- Measures: return_amount_eur (sum of line_amount_eur across all lines of the order).
--
-- TODO(learner):
--   1. Start from stg_orders filtered on status = 'returned'.
--   2. Aggregate stg_order_lines up to the order grain (SUM of line_amount_eur).
--   3. Resolve the same dim_customer, dim_channel, dim_country, dim_date used by
--      fct_order_lines. Reuse — do NOT build customer_dim_for_returns.

{{ config(materialized='table') }}

with returned_orders as (
    select * from {{ ref('stg_orders') }}
    where false  -- TODO: filter on status = 'returned'
)

select
    null::bigint  as order_id,
    null::text    as sk_customer,
    null::text    as sk_channel,
    null::text    as sk_country_ship,
    null::integer as return_date_key,
    null::numeric as return_amount_eur
from returned_orders
where false
