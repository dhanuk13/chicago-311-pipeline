import json
import os

import duckdb
import gspread

DB_PATH = "data/potholes.duckdb"
EXPECTED_AREAS = 77


def main():
    credentials = json.loads(os.environ["GOOGLE_SA_KEY"])
    sheet_id = os.environ["SHEET_ID"]

    # 1. Read the final table (read_only: this script never changes the database)
    con = duckdb.connect(DB_PATH, read_only=True)
    result = con.sql("""
        SELECT
            community_area,
            community,
            ROUND(median_response, 2)        AS median_response,
            income,
            hardship,
            volume,
            CAST(last_refreshed AS VARCHAR)  AS last_refreshed
        FROM mart_community
        ORDER BY community_area
    """)
    header = result.columns
    rows = [list(row) for row in result.fetchall()]
    con.close()

    # 2. Refuse to publish an incomplete table
    if len(rows) != EXPECTED_AREAS:
        raise SystemExit(f"Expected {EXPECTED_AREAS} areas, found {len(rows)}. Not exporting.")

    # 3. Replace the sheet's contents with the new table
    client = gspread.service_account_from_dict(credentials)
    worksheet = client.open_by_key(sheet_id).sheet1
    worksheet.clear()
    worksheet.update(range_name="A1", values=[header] + rows)

    print(f"Exported {len(rows)} rows to Google Sheet {sheet_id}")


if __name__ == "__main__":
    main()
