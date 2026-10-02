select
   s.community_area,
    s.community,
    median(i.response_days)  as median_response,
    s.income,
    s.hardship,
    count(i.response_days)   as volume,
    current_timestamp        as last_refreshed
from {{ ref('stg_income') }} s
left join {{ ref('int_phb') }} i
    on i.community_area = s.community_area
group by all