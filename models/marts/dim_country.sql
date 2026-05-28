-- dim_country — the CONFORMED country dim.
--
-- Why "conformed" matters here:
--   Both the customer's billing country (customers.country_code) and the order's
--   ship-to country (orders.country_code) join to THIS dim, not to two parallel dims.
--   That's what makes "revenue by ship-to country" and "customers by billing country"
--   reconciliable on the same dim.
--
-- TODO(learner): project country_code, country_name, region from stg_countries,
-- generate sk_country.

{{ config(materialized='table') }}

with countries as (
    select * from {{ ref('stg_countries') }}
)

select
    null::text as sk_country,
    null::text as country_code
from countries
where false
