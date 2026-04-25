# Copernicus demo baseline

`copernicusBaseline.ts` is a packaged monthly climatology for the draft
simulator. It is intentionally small so the CASSINI demo can run fully in the
browser without waiting on Copernicus downloads.

Replace it with real exports in this order:

1. CEMS GloFAS historical river discharge at White Nile, Blue Nile/GERD, and
   Atbara sample points.
2. ERA5-Land monthly runoff index and PET over the relevant upstream basins.
3. Sentinel-2 L2A NDVI or CLMS crop/land-cover activity for Gezira and Egypt
   agriculture zones.
4. CLMS Water Bodies monthly reservoir surface area for GERD and Lake Nasser.

The simulator expects one row per month and the same fields as
`CopernicusMonth`.

## Generate the real GloFAS + ERA5-Land baseline

Configure credentials:

```bash
export EWDS_API_URL=https://ewds.climate.copernicus.eu/api
export EWDS_API_KEY='<uid>:<api-key>'
export CDSAPI_URL=https://cds.climate.copernicus.eu/api
export CDSAPI_KEY='<uid>:<api-key>'
```

Then run:

```bash
.venv/bin/python -m dataloader copernicus-baseline \
  --start-year 2020 \
  --end-year 2024 \
  --out frontend/public/copernicus-baseline.json
```

The app will automatically load `/copernicus-baseline.json` when it exists and
fall back to `copernicusBaseline.ts` otherwise.
