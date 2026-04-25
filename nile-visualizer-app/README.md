# NRSM Nile Visualizer App

TypeScript React frontend for exploring the Nile MVP simulator output.

## Run

```powershell
npm install
npm run dev
```

The app currently uses typed data copied from the MVP scenario and `nrsm-cli`
monthly output. The next useful integration step is a small export command that
writes scenario plus result JSON into `src/data` or a public runtime payload.

## Build

```powershell
npm run build
```
