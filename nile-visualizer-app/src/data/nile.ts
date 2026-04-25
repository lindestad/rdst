import aswandCsv from "./results/nile-mvp/aswand.csv?raw";
import cairoCsv from "./results/nile-mvp/cairo.csv?raw";
import gerdCsv from "./results/nile-mvp/gerd.csv?raw";
import karthoumCsv from "./results/nile-mvp/karthoum.csv?raw";
import kashmCsv from "./results/nile-mvp/kashm.csv?raw";
import meroweCsv from "./results/nile-mvp/merowe.csv?raw";
import ozentariCsv from "./results/nile-mvp/ozentari.csv?raw";
import roseiresCsv from "./results/nile-mvp/roseires.csv?raw";
import singaCsv from "./results/nile-mvp/singa.csv?raw";
import southwestCsv from "./results/nile-mvp/southwest.csv?raw";
import tanaCsv from "./results/nile-mvp/tana.csv?raw";
import tsenghCsv from "./results/nile-mvp/tsengh.csv?raw";
import victoriaCsv from "./results/nile-mvp/victoria.csv?raw";
import { datasetFromCsvTextByNode } from "../adapters/nrsm";

export { edges, nodes } from "./nileGraph";

export const sampleDataset = datasetFromCsvTextByNode(
  {
    aswand: aswandCsv,
    cairo: cairoCsv,
    gerd: gerdCsv,
    karthoum: karthoumCsv,
    kashm: kashmCsv,
    merowe: meroweCsv,
    ozentari: ozentariCsv,
    roseires: roseiresCsv,
    singa: singaCsv,
    southwest: southwestCsv,
    tana: tanaCsv,
    tsengh: tsenghCsv,
    victoria: victoriaCsv,
  },
  {
    name: "Nile MVP Demo",
    source: "Packaged nile-mvp CSV results",
    horizon: "90 days",
    reporting: "30-day periods",
    units: "NRSM model units per reporting period",
  },
);
