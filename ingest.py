import time
import json
from pathlib import Path
 
import pandas as pd
import requests
 
pd.set_option("display.max_columns", None)
 
URL = "https://data.cityofchicago.org/resource/v6vf-nfxy.json"
PAGE_SIZE = 10000
 
 
def fetch_page(params, attempts=3):
    """Request one page from the API, retrying if the server is slow or fails."""
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(URL, params=params, timeout=120)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as error:
            print(f"  attempt {attempt} failed: {error}")
            if attempt == attempts:
                raise                      # give up after the last attempt
            time.sleep(10 * attempt)       # wait 10s, then 20s, before retrying
 
 
all_rows = []
offset = 0
 
while True:
    params = {
        "sr_short_code": "PHB",            
        "$limit": PAGE_SIZE,               
        "$offset": offset,               
        "$order": "sr_number",            
    }
    rows = fetch_page(params)
 
    all_rows.extend(rows)
    print(f"offset {offset}: got {len(rows)} rows")
 
    if len(rows) < PAGE_SIZE:            
        break
 
    offset += PAGE_SIZE
 
df = pd.DataFrame(all_rows)
print(df.shape)
print(df[["sr_number", "created_date", "closed_date", "community_area"]].head())
 
print("All sr_numbers unique:", df["sr_number"].is_unique)
Path("data/raw").mkdir(parents=True, exist_ok=True)    
with open("data/raw/phb_raw.json", "w") as f:
    json.dump(all_rows, f)

print("Saved", len(all_rows), "rows to data/raw/phb_raw.json")