select 1 as id
union all
select * from {{ ref('node_0') }}
union all
select * from {{ ref('node_3') }}
union all
select * from {{ ref('node_6') }}
union all
select * from {{ ref('node_8') }}
union all
select * from {{ ref('node_10') }}
union all
select * from {{ ref('node_12') }}
union all
select * from {{ ref('node_116') }}
union all
select * from {{ ref('node_208') }}
union all
select * from {{ ref('node_360') }}
union all
select * from {{ ref('node_522') }}
union all
select * from {{ ref('node_694') }}
