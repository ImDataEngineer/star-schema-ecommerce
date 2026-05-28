-- dim_date — role-playing calendar dim.
--
-- The SAME dim_date is joined to fact_order_lines TWICE:
--   - on order_date_key  (alias dim_order_date in the fact's CTE)
--   - on ship_date_key   (alias dim_ship_date in the fact's CTE)
--
-- There is NO dim_order_date.sql or dim_ship_date.sql model. Role-playing
-- means ONE physical table, multiple aliases at join time.
--
-- date_key (YYYYMMDD integer) is both the surrogate AND the natural key. This is
-- the textbook exception to the "always use opaque SKs" rule — Kimball Ch. 7.

{{ config(materialized='table') }}

with dates as (
    select * from {{ ref('stg_dates') }}
)

select
    null::integer as date_key,
    null::date    as date_iso
from dates
where false
