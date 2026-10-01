import duckdb

con = duckdb.connect("data/potholes.duckdb")      

con.sql("""
    CREATE OR REPLACE TABLE raw_phb AS
    SELECT * FROM read_json_auto('data/raw/phb_raw.json')
""")

print(con.sql("SELECT COUNT(*) AS row_count FROM raw_phb"))
print(con.sql("DESCRIBE raw_phb"))

con.sql("""
    CREATE OR REPLACE TABLE stg_phb AS
    SELECT
        sr_number,
        status,
        CAST(created_date       AS TIMESTAMP) AS created_at,
        CAST(closed_date        AS TIMESTAMP) AS closed_at,
        CAST(last_modified_date AS TIMESTAMP) AS last_modified_at,
        CAST(community_area     AS INTEGER)   AS community_area,
        CAST(duplicate          AS BOOLEAN)   AS is_duplicate
    FROM raw_phb
""")

print(con.sql("DESCRIBE stg_phb"))

print(con.sql("""
    SELECT
        COUNT(*)                                          AS total,
        COUNT(*) FILTER (WHERE is_duplicate)              AS duplicates,
        COUNT(*) FILTER (WHERE community_area IS NULL)    AS no_community_area,
        COUNT(*) FILTER (WHERE closed_at IS NULL)         AS still_open
    FROM stg_phb
"""))

con.sql("""
    CREATE OR REPLACE TABLE int_phb AS
    SELECT
        *,
        date_diff('second', created_at, closed_at) / 86400.0 AS response_days
    FROM stg_phb
    WHERE NOT is_duplicate
""")

print(con.sql("""
    SELECT
        COUNT(*)                                    AS requests,
        COUNT(response_days)                        AS closed_requests,
        ROUND(MEDIAN(response_days), 1)             AS median_days,
        ROUND(AVG(response_days), 1)                AS mean_days
    FROM int_phb
"""))

print(con.sql("""
    SELECT
        year(created_at)                                   AS yr,
        COUNT(*)                                           AS total,
        COUNT(*) FILTER (WHERE is_duplicate)               AS dup_true,
        COUNT(*) FILTER (WHERE NOT is_duplicate)           AS dup_false,
        COUNT(*) FILTER (WHERE is_duplicate IS NULL)       AS dup_null
    FROM stg_phb
    GROUP BY yr
    ORDER BY yr
"""))

con.sql("""
    CREATE OR REPLACE TABLE seed_income AS
    SELECT
        area_num  AS community_area,
        area_name AS community,
        income,
        hardship
    FROM read_csv_auto('data/seeds/Income.csv')
         AS t(area_num, area_name, crowded, poverty, unemployed, no_hs, dependency, income, hardship)
    WHERE area_num IS NOT NULL
""")

con.sql("""
    CREATE OR REPLACE TABLE mart_community AS
    SELECT
        s.community_area,
        s.community,
        MEDIAN(i.response_days)  AS median_response,
        s.income,
        s.hardship,
        COUNT(i.response_days)   AS volume,
        current_timestamp        AS last_refreshed
    FROM seed_income s
    LEFT JOIN int_phb i
           ON i.community_area = s.community_area
    GROUP BY ALL
""")

print(con.sql("SELECT COUNT(*) AS areas FROM mart_community"))

print(con.sql("""
    (SELECT community, ROUND(median_response, 1) AS median_days, volume
     FROM mart_community ORDER BY median_response ASC LIMIT 3)
    UNION ALL
    (SELECT community, ROUND(median_response, 1), volume
     FROM mart_community ORDER BY median_response DESC LIMIT 3)
"""))
