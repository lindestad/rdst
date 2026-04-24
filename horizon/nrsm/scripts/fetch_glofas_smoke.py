# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "cdsapi>=0.7.7",
# ]
# ///
"""Tiny GloFAS/EWDS smoke fetch for the Nile dataloader.

Run from the repository root or horizon/nrsm:

    uv run horizon/nrsm/scripts/fetch_glofas_smoke.py --dry-run
    uv run horizon/nrsm/scripts/fetch_glofas_smoke.py --submit

The script uses .env values:

    EWDS_API_URL=https://ewds.climate.copernicus.eu/api
    EWDS_API_KEY=<PERSONAL-ACCESS-TOKEN>

If EWDS_API_KEY is blank it falls back to CDS_API_KEY. The request shape follows
the current EWDS "CDSAPI setup" and CEMS subset examples for GloFAS historical.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


DEFAULT_DATASET = "cems-glofas-historical"
DEFAULT_REQUEST = {
    "system_version": ["version_4_0"],
    "hydrological_model": ["lisflood"],
    "product_type": ["intermediate"],
    "variable": ["river_discharge_in_the_last_24_hours"],
    "hyear": ["2023"],
    "hmonth": ["06"],
    "hday": ["01"],
    "data_format": "grib2",
    "download_format": "unarchived",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submit", action="store_true", help="Submit the EWDS request")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the request and credential status without submitting",
    )
    parser.add_argument("--year", default="2023", help="Historical year, e.g. 2023")
    parser.add_argument("--month", default="06", help="Historical month as two digits")
    parser.add_argument("--day", default="01", help="Historical day as two digits")
    parser.add_argument(
        "--target",
        default="horizon/nrsm/data/raw/glofas/glofas_smoke_gerd_2023-06-01.grib2",
        help="Output GRIB2 path",
    )
    args = parser.parse_args()

    repo_root = find_repo_root()
    load_dotenv(repo_root / ".env")
    load_dotenv(repo_root / "horizon" / "nrsm" / ".env")

    url, key = api_credentials()
    request = build_request(args.year, args.month, args.day)
    target = resolve_output_path(repo_root, args.target)

    print("GloFAS smoke request")
    print(f"  dataset: {DEFAULT_DATASET}")
    print(f"  api url: {url}")
    print(f"  api key present: {'yes' if key else 'no'}")
    print(f"  target: {target}")
    print(json.dumps(request, indent=2))

    if not args.submit or args.dry_run:
        print()
        print("Dry run only. Add --submit to fetch.")
        print("Before submitting, manually accept the GloFAS dataset Terms of Use in EWDS.")
        return 0 if key else 2

    if not key:
        raise SystemExit("Missing EWDS_API_KEY or CDS_API_KEY in .env")

    target.parent.mkdir(parents=True, exist_ok=True)
    import cdsapi

    client = cdsapi.Client(url=url, key=key)
    try:
        result = client.retrieve(DEFAULT_DATASET, request)
    except Exception as error:
        message = str(error)
        if "didn't accept all required site policies" in message or "Missing policies" in message:
            print()
            print("EWDS rejected the request because the account has not accepted required policies.")
            print("Open this while logged in with the API-key account, accept the terms, then rerun:")
            print("  https://ewds.climate.copernicus.eu/licences/terms-of-use-cems")
            raise SystemExit(3) from None
        raise
    if hasattr(result, "download"):
        result.download(str(target))
    else:
        # Older cdsapi versions accepted target as retrieve's third arg, but the
        # new EWDS examples use retrieve(...).download(...). Keep a clear error
        # if the client behavior changes.
        raise RuntimeError("cdsapi retrieve result does not expose download()")

    print(f"Wrote {target}")
    return 0


def find_repo_root() -> Path:
    current = Path.cwd().resolve()
    for path in [current, *current.parents]:
        if (path / ".git").exists() or (path / ".git").is_file():
            return path
    return current


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def first_present(*keys: str) -> str | None:
    for key in keys:
        value = os.environ.get(key)
        if value:
            return value
    return None


def api_credentials() -> tuple[str, str | None]:
    url = first_present("EWDS_API_URL", "CDS_API_URL") or "https://ewds.climate.copernicus.eu/api"
    key = first_present("EWDS_API_KEY", "CDS_API_KEY")
    return url, key


def build_request(year: str, month: str, day: str) -> dict[str, object]:
    request = dict(DEFAULT_REQUEST)
    request["hyear"] = [year]
    request["hmonth"] = [month.zfill(2)]
    request["hday"] = [day.zfill(2)]
    return request


def resolve_output_path(repo_root: Path, target: str) -> Path:
    path = Path(target)
    if path.is_absolute():
        return path
    return repo_root / path


if __name__ == "__main__":
    raise SystemExit(main())
