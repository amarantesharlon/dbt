select 1 as id
union all
select * from {{ ref('node_0') }}
union all
select * from {{ ref('node_1') }}
union all
select * from {{ ref('node_256') }}
union all
select * from {{ ref('node_526') }}
union all
select * from {{ ref('node_781') }}
