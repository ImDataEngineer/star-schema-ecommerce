-- stg_countries — the conformed country reference.
--
-- Why this matters: orders.country_code (ship-to) AND customers.country_code
-- (billing) both join to the SAME dim_country. That conformance is what makes
-- the warehouse useful for cross-fact analysis. If you build two country dims,
-- finance and product will disagree on the same number.

{{ config(materialized='view') }}

select
    null::text as country_code
from {{ source('bronze', 'countries') }}
where false
