-- stg_customers — light typing/renaming over bronze.customers.
--
-- Responsibility: ONE row per customer_id, typed columns, no business logic.
-- Resist the temptation to compute lifetime value here — that belongs to a mart.
--
-- TODO(learner):
--   1. Select the columns you actually need downstream (customer_id, email,
--      country_code, signup_date, segment) — projecting * makes future renames
--      a guessing game.
--   2. Keep the natural key (customer_id) as-is. The surrogate key lives in dim_customer.
--   3. Decide if you want to expose `email` here at all — many teams strip PII
--      at staging. For this project, keep it; the security project (dms.*) is where
--      that lesson lives.

{{ config(materialized='view') }}

select
    -- TODO: list columns explicitly. Do not SELECT *.
    null::bigint as customer_id
from {{ source('bronze', 'customers') }}
where false  -- placeholder so dbt parses; remove once you start the real select
