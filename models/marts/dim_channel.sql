-- dim_channel — 5-row reference dim.
--
-- TODO(learner): project channel_id, channel_name, channel_type from stg_channels,
-- generate sk_channel.

{{ config(materialized='table') }}

with channels as (
    select * from {{ ref('stg_channels') }}
)

select
    null::text as sk_channel,
    null::text as channel_id
from channels
where false
