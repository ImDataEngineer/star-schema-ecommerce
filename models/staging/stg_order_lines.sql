-- stg_order_lines — line-level facts, natural key (order_id, line_number).
--
-- This is the row that will become fact_order_lines after surrogate key joins.
-- The grain is non-negotiable: ONE row per (order_id, line_number).
--
-- TODO(learner):
--   1. Project natural keys + measures only.
--   2. Compute line_amount_eur = quantity * unit_price_eur - discount_eur as a measure.
--      Measures live on the fact; do NOT put quantity*price in a downstream view.
--   3. Do NOT join customer or product attributes here. Joining dimensions in
--      staging breaks the "one row per (order_id, line_number)" grain the moment
--      a dim has multiple rows per natural key (it WILL happen at some point).

{{ config(materialized='view') }}

select
    null::bigint as order_id,
    null::integer as line_number
from {{ source('bronze', 'order_lines') }}
where false
