-- stg_products — bronze.products, lightly typed.
--
-- TODO(learner):
--   1. Project product_id, product_name, category_code, list_price_eur.
--   2. The dump represents CURRENT state. Do NOT build SCD2 here — the
--      ADR you write should explicitly mention that history tracking
--      is out of scope for this project.

{{ config(materialized='view') }}

select
    null::bigint as product_id
from {{ source('bronze', 'products') }}
where false
