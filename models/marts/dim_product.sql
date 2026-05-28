-- dim_product — SCD1 (current state only).
--
-- TODO(learner):
--   1. Project product_id, product_name, category_code, list_price_eur from stg_products.
--   2. Generate sk_product (same strategy as dim_customer — be consistent).
--   3. Do NOT split into dim_product + dim_category. Snowflaking that
--      hierarchy adds a join for zero analytical gain at this volume.
--      Justify the choice in your ADR.

{{ config(materialized='table') }}

with products as (
    select * from {{ ref('stg_products') }}
)

select
    null::text   as sk_product,
    null::bigint as product_id
from products
where false
