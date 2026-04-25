from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
TIMESERIES_DIR = DATA_DIR / "timeseries"
OVERLAYS_DIR = DATA_DIR / "overlays" / "ndvi"
TILES_DIR = DATA_DIR / "tiles" / "ndvi"
STATIC_DIR = DATA_DIR / "static"

NODES_GEOJSON = DATA_DIR / "nodes.geojson"
NODE_CONFIG_YAML = DATA_DIR / "node_config.yaml"

PERIOD_START = "2005-01-01"
PERIOD_END = "2024-12-01"
