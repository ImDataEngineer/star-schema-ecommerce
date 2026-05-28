-- stg_orders — order header.
--
-- Decisions you must make here:
--   - How to handle the ~0.5% of orders whose customer_id is unknown
--     (late-arriving customer). Two acceptable patterns:
--       a) Drop the offending rows. Log how many. The fact will simply have
--          fewer rows. Justify the loss in your ADR.
--       b) Keep the rows and route them to a sentinel customer surrogate key
--          ("unknown customer") in dim_customer. Then NO orphan exists.
--     Pattern (b) is the Kimball-canonical answer. Pattern (a) is also valid
--     if you document the trade-off.
--   - Do NOT join customer attributes here. stg_orders stays at the order grain.

{{ config(materialized='view') }}

select
    null::bigint as order_id
from {{ source('bronze', 'orders') }}
where false
