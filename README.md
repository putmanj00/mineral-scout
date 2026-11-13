# Mineral Scout

Find where minerals occur, whether you can legally dig there, and — when the
land is private — who to ask. Focused on the US (best in the West), world
basemap included.

## Features

- **Mineral sites map** — USGS MRDS occurrences/prospects/producers, filterable
  by commodity (Gold, Copper, …) and development status, clustered Leaflet map.
- **Abandoned mines** — USGS USMIN features from historic topo maps (adits,
  shafts, prospect pits) with a **tailings/dumps-only** toggle (tailings come
  from the USMIN polygon layer, rendered as centroids).
- **Active mining claims** — BLM MLRS claim polygons (lode/placer/tunnel/mill),
  so you don't collect the claimed mineral on someone's claim.
- **Land ownership overlay** — BLM Surface Management Agency tiles (BLM / USFS /
  NPS / State / Private …).
- **"Check land" mode** — click anywhere: combines BLM SMA + PAD-US 4.1 +
  Census county + active-claims point check into one verdict (public /
  restricted / state trust / private / unknown) with the applicable
  collecting rules.
- **Owner lookup on private land** — county-registry approach: free county
  assessor REST services where they exist (Maricopa, Yavapai, Cochise AZ —
  returns assessor-record owner + APN + deep link), assessor search pages and
  NETR public-records directory everywhere else. Honest about states where
  owners aren't published online (NJ, CA, KY…).
- **Collecting-law panels** — per-state summaries with primary-source
  citations (43 CFR 8365.1-5, 43 CFR 3622.4, 36 CFR 2.1, agency pages),
  verified 2026-07-12. Includes the important Arizona correction: the $15
  State Trust recreational permit does **not** allow rockhounding — Arizona's
  friendliness comes from its BLM land (25 lb/day, 250 lb/yr).
- **Safety** — "Stay Out, Stay Alive" abandoned-mine warnings throughout.
- **GPX export** of the current filtered view (optionally including mine
  features) + client-side bookmarks with their own GPX export.
- **Mindat localities layer** (optional) — set `MSCOUT_MINDAT_API_KEY` (free
  key with a mindat.org account); without it the layer explains how to enable.

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --port 8106
# open http://localhost:8106
```

Phone access (optional, over your own Tailscale network):
`tailscale serve --bg --https=8106 http://127.0.0.1:8106`, then open
`https://<your-host>.<your-tailnet>.ts.net:8106`; disable with
`tailscale serve --https=8106 off`.

Durable service: `systemctl --user enable --now deploy/mineral-scout.service`
(Restart=always, binds 127.0.0.1:8106).

## Configuration (env or `.env`, prefix `MSCOUT_`)

| Var | Default | Meaning |
|-----|---------|---------|
| `MSCOUT_MINDAT_API_KEY` | empty | enables the mindat localities layer |
| `MSCOUT_UPSTREAM_TIMEOUT` | 30 | seconds for upstream USGS/BLM calls |
| `MSCOUT_CACHE_TTL` | 86400 | upstream response cache TTL (s) |

## Tests

```bash
.venv/bin/python -m pytest
```

Upstreams are mocked (respx); live-endpoint smoke happens at dev time.

## Data sources (all verified live 2026-07-12)

| Source | Use | Endpoint |
|--------|-----|----------|
| USGS MRDS | mineral sites | `mrdata.usgs.gov/wfs/mrds` (WFS/GML) |
| USGS USMIN | abandoned mines + tailings | `USGS_Topographic_Mine_Symbols` FeatureServer (layers 8 + 2) |
| BLM SMA | land ownership | `BLM_Natl_SMA_Cached_with_PriUnk` MapServer (query + tiles) |
| BLM MLRS | mining claims | `gis.blm.gov/nlsdb` MiningClaims layers 1/2 |
| USGS PAD-US 4.1 | protected/public areas | `Manager_Name_PADUS` FeatureServer |
| Census geocoder | state/county | `geocoding.geo.census.gov` |
| County assessors | parcel owner | registry in `app/sources/parcels.py` |
| mindat.org | localities (opt-in key) | `api.mindat.org/v1` |

Known ceilings: MRDS is a frozen dataset (last update 2022); tailings
polygons render as centroid markers; owner names are assessor records and
unavailable online in some states; closed-claims layer is slow so only
active claims are shown.

Not legal advice. Never enter abandoned mines.
# E2E: .venv/bin/pip install playwright && .venv/bin/python scripts/e2e_browser.py (server must be running on :8106)

## License

MIT. See [LICENSE](LICENSE).
