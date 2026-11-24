# Power BI build guide: live Network Operations report

Goal: a 4-page report that reads PostgreSQL in **DirectQuery** and refreshes itself
every few seconds, so a KPI logged in the web app appears in the report almost immediately.

Time needed: about 2–3 hours the first time.

---

## 0. Before you start

```powershell
docker compose up -d                 # start PostgreSQL
venv\Scripts\python init_db.py       # only the first time (wipes the DB)
venv\Scripts\python seed_data.py     # only the first time
```

The Power BI login is in your `.env`: user `powerbi_reader`, password `POWERBI_PASSWORD`.
This account can only read the `bi` schema, never the raw tables or user passwords.

## 1. Connect (DirectQuery)

1. Power BI Desktop → **Get data → PostgreSQL database**.
2. Server: `localhost:5432` · Database: `tt_network` · Data connectivity mode: **DirectQuery**.
3. Credentials: choose the **Database** tab (not Windows) → `powerbi_reader` + password.
   If it complains about encryption, click OK to connect unencrypted (local only).
4. In the Navigator, tick the 5 views under `bi`:
   `dim_date`, `dim_site`, `dim_user`, `fact_kpi_daily`, `fact_ticket` → **Load**.
   Rename them without the `bi ` prefix if Power BI adds one.

## 2. Model (Model view)

Create these relationships (drag column to column), all **Many-to-one, single direction**:

| From (many) | To (one) | Active |
|---|---|---|
| fact_kpi_daily[date] | dim_date[date] | yes |
| fact_kpi_daily[site_id] | dim_site[site_id] | yes |
| fact_ticket[created_date] | dim_date[date] | yes |
| fact_ticket[site_id] | dim_site[site_id] | yes |
| fact_ticket[technician_id] | dim_user[user_id] | yes |
| fact_ticket[engineer_id] | dim_user[user_id] | **no** (inactive) |

Then:
- Select `dim_date` → **Mark as date table** → column `date`.
- `dim_date[month_label]` → **Sort by column** → `year_month`.
- `dim_date[weekday_label]` → **Sort by column** → `weekday_number`.
- `dim_site[latitude]` → Data category **Latitude**; `longitude` → **Longitude**; `governorate` → **State or Province**.
- Hide all `*_id` columns in the fact tables (right click → Hide in report view).

## 3. Measures

Open `powerbi/measures.dax`. Create an empty `_Measures` table (Home → Enter data → Load),
then add each measure with **New measure**. Set the format noted under each one.

## 4. Pages

Theme: View → Themes → pick a dark or a clean one and keep it for all pages.
Add a slicer panel on the left of every page (Date range, Governorate, Supplier) and
**sync slicers** across pages (View → Sync slicers).

### Page 1 · Network Overview (live)
- **Cards** (top row): `Availability Today %`, `SLA Compliance %`, `Data Traffic (TB)`,
  `VoLTE Share %`, `Open Tickets`, `Last KPI Logged`.
- **Line chart**: X = `dim_date[date]`, Y = `Avg Availability %`; secondary Y = `Avg Blocking Rate %`.
  Add a constant line at 99 (the SLA).
- **Map** (or Azure Map): Latitude/Longitude from `dim_site`, bubble size = `Data Traffic (TB)`,
  colour = `Avg Availability %` (conditional formatting, red below 99).
- **Table**: sites degraded today: `site_name`, `governorate`, `supplier`, `Avg Availability %`,
  `Avg Blocking Rate %`; visual filter `dim_date[date]` = today (relative date: "is in this 1 day").
- **Turn on auto refresh**: click empty canvas → Format page → **Page refresh** → On →
  Auto page refresh → Fixed interval **5 seconds**.

### Page 2 · Quality & Supplier Benchmark
- Clustered bar: `supplier` × `Avg Availability %` and `Avg Blocking Rate %`.
- Scatter: Values = `site_name`, X = `Data Traffic (TB)`, Y = `Avg Blocking Rate %`,
  Legend = `supplier` (shows whether congestion follows traffic).
- Matrix: Rows = `governorate`, Columns = `month_label`, Values = `Avg Availability %`
  with a background colour scale.
- Table "Top 10 worst sites": `site_name`, `SLA Breach Days`, `Quality Breach Days`;
  Top N filter = 10 by `SLA Breach Days`.

### Page 3 · Traffic Trends
- Area chart: X = `year_month`, Y = `Data Traffic (TB)`; second chart `Voice Traffic (Erl)`.
- Line: `VoLTE Share %` by month (adoption curve).
- Column: `weekday_label` × `Data Traffic (TB)` (weekend effect).
- KPI card: `Data Traffic MoM %`.

### Page 4 · Maintenance Operations
- Cards: `Tickets`, `Open Tickets`, `High Priority Open`, `MTTR (h)`, `Avg Engineer Rating`.
- Donut: `fact_ticket[status]` × `Tickets`.
- Bar: `priority` × `MTTR (h)`.
- Table: `dim_user[user_name]` (technicians), `Resolved Tickets`, `MTTR (h)`, `Avg Engineer Rating`.
- Column: `month_label` × `Tickets`, legend = `fault_type` (top fault causes).

## 5. Demo it live

```powershell
venv\Scripts\python simulate_live_kpis.py 2
```
This logs today's KPIs for random sites every 2 s (15 % degraded). Watch page 1:
`Last KPI Logged` ticks, availability moves and degraded sites appear on the map.
You can also log a KPI by hand at `http://127.0.0.1:5000/kpi/add` (run `python app.py`).

Screen-record this for LinkedIn: app form on the left, Power BI on the right.

## 6. Save

Save as `powerbi/Network_Operations.pbix`. The file only stores the connection and layout,
not the data (DirectQuery), so it stays small and contains no data.

## Troubleshooting

- **"Npgsql" / provider error:** update Power BI Desktop (recent versions include the PostgreSQL driver).
- **Auto page refresh greyed out:** it only works on DirectQuery pages. Check the connection mode
  in the status bar at the bottom right.
- **Visual says "too many rows / query timeout":** add the date slicer and limit to the last 90 days.
- **Port 5432 already in use:** another PostgreSQL is running. Stop it, or change the left side of
  `"5432:5432"` in `docker-compose.yml` and in `DATABASE_URL`.
