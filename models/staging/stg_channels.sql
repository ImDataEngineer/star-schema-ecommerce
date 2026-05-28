-- stg_channels — channel reference (5 rows). One-to-one with dim_channel.

{{ config(materialized='view') }}

select
    null::text as channel_id
from {{ source('bronze', 'channels') }}
where false
