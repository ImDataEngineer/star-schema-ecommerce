-- stg_dates — calendar reference.
--
-- ONE physical dim_date exists. fact_order_lines joins it twice — once on
-- order_date_key, once on ship_date_key. That is role-playing. You do NOT
-- create dim_order_date.sql and dim_ship_date.sql.

{{ config(materialized='view') }}

select
    null::integer as date_key
from {{ source('bronze', 'dates') }}
where false
