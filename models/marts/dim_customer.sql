-- dim_customer — conformed customer dimension.
--
-- Grain: one row per customer_id (and one extra row: the "unknown customer"
-- sentinel, if you choose Kimball pattern (b) in stg_orders.sql).
--
-- Surrogate key strategy: pick ONE and stick with it. Either:
--   - md5(customer_id::text)::text  (string SK, 32-char hex, deterministic)
--   - dense_rank() over (order by customer_id)  (integer SK, dense, deterministic
--     given a stable upstream order — be careful if upstream changes)
-- DO NOT use row_number() without an ORDER BY — the value is not stable across runs.
--
-- TODO(learner):
--   1. Project customer_id, email, country_code, signup_date, segment from stg_customers.
--   2. Generate sk_customer.
--   3. (Optional but recommended) UNION ALL a single row with customer_id = -1,
--      sk_customer = the SK of -1, segment = 'unknown' — the sentinel for late-arriving
--      customers. fact rows then point at this sentinel instead of orphaning.

{{ config(materialized='table') }}

with customers as (
    select * from {{ ref('stg_customers') }}
)

select
    -- TODO: replace these placeholders with the real columns + your chosen SK expression.
    null::text   as sk_customer,
    null::bigint as customer_id
from customers
where false
