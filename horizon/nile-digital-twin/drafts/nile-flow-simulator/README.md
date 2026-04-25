# Nile flow simulator draft

This directory preserves the prototype work outside the active application so it
can be reapplied or mined after the main branch changes settle.

Contents:

- `frontend/src/App.tsx` - standalone React screen for the draft simulator.
- `frontend/src/copernicusData/copernicusBaseline.ts` - packaged 12-month
  Copernicus-shaped fallback data.
- `frontend/src/copernicusData/README.md` - notes on replacing fallback data.
- `tools/copernicus_baseline.py` - real-data builder for CEMS GloFAS and
  ERA5-Land monthly climatologies.

The active app no longer imports these files. To use this draft again, copy the
frontend files into an isolated app shell or port the simulator components into
the current main frontend.

The real-data builder expects Copernicus credentials:

```bash
export EWDS_API_URL=https://ewds.climate.copernicus.eu/api
export EWDS_API_KEY='<uid>:<api-key>'
export CDSAPI_URL=https://cds.climate.copernicus.eu/api
export CDSAPI_KEY='<uid>:<api-key>'
```

Then adapt/run:

```bash
python drafts/nile-flow-simulator/tools/copernicus_baseline.py \
  --start-year 2020 \
  --end-year 2024 \
  --out frontend/public/copernicus-baseline.json
```

The copied tool still imports the repo's `dataloader.config`, so run it from
the repository root or port it back into the main dataloader package.
