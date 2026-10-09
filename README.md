# Chicago 311 Alley Pothole Pipeline
 
An automated daily ELT pipeline that pulls Chicago 311 alley pothole requests from the city's open data API, transforms and tests them with dbt, and publishes a live Tableau Public map of median repair time by community area.
 
**Live map:** [Chicago Alley Pothole Response Time by Community Area](https://public.tableau.com/app/profile/dhanushri.devi.kannan/viz/ChicagoAlleyPotholeResponseTimebyCommunityArea/ResponseMap)
**Original analysis:** [chicago-311-pothole](https://github.com/dhanuk13/chicago-311-pothole), the one-time study this pipeline automates.
 
## How it works
 
```
Chicago Data Portal API (311 Service Requests, v6vf-nfxy)
        │  ingest.py — incremental extract, upsert
        ▼
DuckDB  raw_phb
        │  dbt build — models + 11 tests
        ▼
stg_phb ─► int_phb ─┐
                     ├─► mart_community (77 rows, one per community area)
stg_income (seed) ──┘
        │  export_sheet.py
        ▼
Google Sheet ─► Tableau Public (refreshes from the sheet about every 24h)
```
 
All of this runs once a day on GitHub Actions. No local machine is involved.
 
## Stack
 
Python 3.12 · DuckDB · dbt (dbt-duckdb) · GitHub Actions · Google Sheets API (gspread) · Tableau Public
 
## Repository layout
 
```
ingest.py                  Extract + load: API → DuckDB raw_phb
export_sheet.py            Publish mart_community to Google Sheets
requirements.txt
pothole_dbt/
  models/staging/          stg_phb (types, renames), stg_income, _sources.yml
  models/intermediate/     int_phb (duplicates removed, response_days)
  models/marts/            mart_community (final table for Tableau)
  models/_models.yml       column tests
  seeds/                   community_income.csv (2008–2012 ACS indicators)
  tests/                   custom data tests
.github/workflows/pipeline.yml
```
 
## Extract and load (`ingest.py`)
 
- **Scope:** request type `PHB` (Alley Pothole Complaint) only.
- **Incremental loading:** reads the latest `last_modified_date` already loaded (the watermark) and requests only rows modified at or after it. A typical daily run fetches tens to a few hundred rows in a single request instead of ~81,000.
- **Upserts:** each batch replaces existing rows by `sr_number` (delete + insert inside one transaction), so a request that closes later is updated rather than duplicated. The `>=` watermark deliberately overlaps by one row; the upsert makes that harmless.
- **Full-load fallback:** if `raw_phb` doesn't exist, the script downloads the full history with pagination (`$limit`/`$offset`, stable `$order` on `sr_number`).
- **Resilience:** 120-second timeouts and up to 5 retries with increasing waits. The city's API regularly returns timeouts and 5xx errors under load.
- **Raw layer:** every batch is saved unchanged as a timestamped JSON file before loading.
## Transform and test (`dbt build`)
 
| Model | Purpose |
|---|---|
| `stg_phb` | Casts text fields to timestamps, integers, and booleans; standard names (`created_at`, `is_duplicate`) |
| `stg_income` | Community area income and hardship index from the seed, excluding the citywide total row |
| `int_phb` | Removes duplicate reports; computes `response_days` (closed − created, in fractional days) |
| `mart_community` | One row per community area: median response time, closed-request volume, income, hardship, `last_refreshed` |
 
**Data rules:**
 
1. **Duplicates excluded.** About 30% of alley pothole requests are flagged as duplicates. A duplicate's close date follows its parent request, so including them distorts both response times and volume.
2. **Requests without a community area** drop out at the join to the 77 areas.
3. **Open requests** have no response time and are excluded from the median.
4. **Medians, not means.** Response times are heavily right-skewed.
**Tests (11):** `unique` and `not_null` on `sr_number`; `not_null` on `created_at` and `is_duplicate`; `unique` and `not_null` on community area in `stg_income` and `mart_community`; a `relationships` test that every request's community area exists in the 77 areas; and two custom tests: exactly 77 areas in the mart, and no request closed before it was created.
 
`dbt build` runs each model's tests immediately after building it, so a failing test stops downstream models from being built.
 
## Publish (`export_sheet.py`)
 
Reads `mart_community` read-only and replaces the Google Sheet's contents. It refuses to publish unless exactly 77 rows are present. Credentials come from GitHub secrets (`GOOGLE_SA_KEY`, `SHEET_ID`) via a Google Cloud service account with editor access to that one sheet; no credentials are stored in the repository.
 
## Scheduling and state
 
- **Schedule:** daily at 11:00 UTC, plus a manual **Run workflow** button. GitHub delays scheduled runs under load; in practice runs have started between late morning and early afternoon Chicago time.
- **State between runs:** each run starts on a fresh machine, so the DuckDB file is persisted with `actions/cache`. It is saved only when the whole run succeeds, so a failed run never carries bad data forward. If the cache is lost (unused caches expire after 7 days), `ingest.py` falls back to a full load automatically.
- **Pinned versions:** `ubuntu-24.04` and Python 3.12, so platform changes happen deliberately rather than silently.
## Reconciliation with the original analysis
 
Before going live, the pipeline was run with the same cutoff as the original notebook's data download (2026-06-10):
 
| | Notebook (June CSV) | Pipeline (API) |
|---|---|---|
| Non-duplicate requests | 53,878 | 53,806 |
| Median response (days) | 16.7 | 17.1 |
 
Yearly counts matched exactly for 2018–2025. The remaining differences are explained by requests that closed, or were marked duplicate, after the CSV was downloaded.
 
## Running locally
 
```bash
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows PowerShell
pip install -r requirements.txt
 
python ingest.py                    # from the repo root
cd pothole_dbt
dbt build
```
 
The export step needs the `GOOGLE_SA_KEY` and `SHEET_ID` environment variables and is normally run only by GitHub Actions.
 
## Known limitations
 
- **Deleted records aren't detected.** A request removed at the source never appears as "modified," so it stays in the local copy. A periodic full reload would address this.
- **Map lag.** GitHub's run and Tableau Public's ~24-hour refresh are independent schedules, so the map can trail the sheet by up to a day.
- **Small samples.** Some areas (e.g., O'Hare, Kenwood) have around 100 closed requests, so their medians move noticeably as new requests close.
- **Income vintage.** Income and hardship figures are from 2008–2012 and serve only as a proxy for relative neighborhood wealth.
- **Scope.** Alley potholes only. Street potholes (`PHF`) are a separate, much larger request type; adding them would mean one more code in the filter and a `pothole_type` column.
