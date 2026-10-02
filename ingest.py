import json
import time
from datetime import datetime, timezone
from pathlib import Path
 
import duckdb
import requests
 
URL = "https://data.cityofchicago.org/resource/v6vf-nfxy.json"
PAGE_SIZE = 10000
DB_PATH = "data/potholes.duckdb"
RAW_DIR = Path("data/raw")
 
 
def fetch_page(params, attempts=5):
    """Request one page from the API, retrying if the server is slow or fails."""
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(URL, params=params, timeout=120)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as error:
            print(f"  attempt {attempt} failed: {error}")
            if attempt == attempts:
                raise                      
            time.sleep(10 * attempt)    
 
 
def fetch_all(where):
    """Fetch every row matching a SoQL $where filter, one page at a time."""
    all_rows = []
    offset = 0
    while True:
        params = {
            "$where": where,
            "$limit": PAGE_SIZE,
            "$offset": offset,
            "$order": "sr_number",     
        }
        print(f"requesting offset {offset}...")
        rows = fetch_page(params)
        all_rows.extend(rows)
        print(f"offset {offset}: got {len(rows)} rows")
        if len(rows) < PAGE_SIZE:         
            return all_rows
        offset += PAGE_SIZE
 
 
def get_watermark(con):
    """The latest last_modified_date already loaded, or None if raw_phb doesn't exist yet."""
    table_exists = con.sql(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'raw_phb'"
    ).fetchone()[0]
    if not table_exists:
        return None
    
    return con.sql("SELECT MAX(last_modified_date) FROM raw_phb").fetchone()[0]
 
 
def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(DB_PATH)
 
    # 1. Decide: full load or incremental?
    watermark = get_watermark(con)
    if watermark is None:
        print("No raw table yet -> FULL load")
        rows = fetch_all("sr_short_code = 'PHB'")
    else:
        print(f"Incremental load: rows modified at or after {watermark}")
        rows = fetch_all(f"sr_short_code = 'PHB' AND last_modified_date >= '{watermark}'")
 
    if not rows:
        print("Nothing new to load.")
        con.close()
        return
 
    # 2. Save this batch exactly as received (raw layer)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    batch_file = RAW_DIR / f"phb_{stamp}.json"
    batch_file.write_text(json.dumps(rows))
    print(f"Saved {len(rows)} rows to {batch_file}")
 
    con.sql(
        f"CREATE OR REPLACE TEMP TABLE batch AS "
        f"SELECT * FROM read_json_auto('{batch_file.as_posix()}')"
    )
 
    # 3. Load: create the table on a full load, upsert on an incremental one
    if watermark is None:
        con.sql("CREATE OR REPLACE TABLE raw_phb AS SELECT * FROM batch")
    else:
        con.execute("BEGIN TRANSACTION")
        con.execute("DELETE FROM raw_phb WHERE sr_number IN (SELECT sr_number FROM batch)")
        con.execute("INSERT INTO raw_phb BY NAME SELECT * FROM batch")
        con.execute("COMMIT")
 
    # 4. Check the result
    print(con.sql("""
        SELECT
            COUNT(*)                   AS raw_rows,
            COUNT(DISTINCT sr_number)  AS unique_requests,
            MAX(last_modified_date)    AS new_watermark
        FROM raw_phb
    """))
    con.close()
 
 
if __name__ == "__main__":
    main()
 
