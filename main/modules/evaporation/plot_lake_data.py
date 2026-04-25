#!/usr/bin/env python3
"""
Plot colormaps for each lake/reservoir to inspect data coverage.
Uses cached ERA5 data and nodes.yaml configuration.

Usage:
    python plot_lake_data.py              # plot all lakes
    python plot_lake_data.py victoria   # plot single lake
    python plot_lake_data.py --pev      # plot pev instead of temp
"""

import sys
import pathlib
import argparse
import yaml
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt

HERE = pathlib.Path(__file__).parent
NODES_FILE = HERE / "nodes.yaml"
ERA5_CACHE = HERE / "era5_cache" / "era5_raw.nc"
OUTPUT_DIR = HERE / "plots"


def load_nodes() -> list[dict]:
    """Load node definitions from nodes.yaml."""
    with open(NODES_FILE) as f:
        data = yaml.safe_load(f)
    return data.get("nodes", [])


def get_node(node_id: str = None, nodes: list = None) -> dict | None:
    """Get node by ID."""
    if node_id is None:
        return None
    for node in nodes:
        if node["id"] == node_id:
            return node
    return None


def load_era5_data():
    """Load ERA5 data from cache."""
    if not ERA5_CACHE.exists():
        print(f"ERROR: ERA5 data not found at {ERA5_CACHE}")
        print(f"  Run: python evaporation.py --download")
        sys.exit(1)
    
    ds = xr.open_dataset(str(ERA5_CACHE), engine="netcdf4")
    return ds


def subsetExtent(data: xr.Dataset, extent: dict) -> tuple:
    """Subset data by extent and return spatial arrays."""
    lat_min = extent.get("lat_min")
    lat_max = extent.get("lat_max")
    lon_min = extent.get("lon_min")
    lon_max = extent.get("lon_max")
    
    lats = data.coords["latitude"].values
    lons = data.coords["longitude"].values
    
    lat_mask = (lats >= lat_min) & (lats <= lat_max)
    lon_mask = (lons >= lon_min) & (lons <= lon_max)
    
    lat_sub = lats[lat_mask]
    lon_sub = lons[lon_mask]
    
    temp = None
    evap = None
    
    if "t2m" in data:
        temp = data["t2m"].values[:, lat_mask, :][:, :, lon_mask]
    elif "2t" in data:
        temp = data["2t"].values[:, lat_mask, :][:, :, lon_mask]
    
    if "pev" in data:
        evap = data["pev"].values[:, lat_mask, :][:, :, lon_mask]
    elif "potential_evaporation" in data:
        evap = data["potential_evaporation"].values[:, lat_mask, :][:, :, lon_mask]
    elif "e" in data:
        evap = data["e"].values[:, lat_mask, :][:, :, lon_mask]
    
    return temp, evap, lat_sub, lon_sub


def plot_single(data: xr.Dataset, node: dict, show: bool = True, save: bool = True):
    """Plot temperature and evaporation for a single node."""
    node_id = node["id"]
    name = node_id.capitalize()
    extent = node.get("extent", {})
    
    print(f"\n=== {name} ({node_id}) ===")
    print(f"  Extent: lat {extent.get('lat_min')} to {extent.get('lat_max')}")
    print(f"         lon {extent.get('lon_min')} to {extent.get('lon_max')}")
    
    temp, evap, lats, lons = subsetExtent(data, extent)
    
    if temp is not None:
        temp_mean = np.nanmean(temp, axis=0)
        print(f"  Temp: shape {temp_mean.shape}, range {np.nanmin(temp_mean):.1f} to {np.nanmax(temp_mean):.1f} K")
    else:
        temp_mean = None
        print(f"  Temp: NOT AVAILABLE")
    
    if evap is not None:
        evap_mean = np.nanmean(evap, axis=0)
        print(f"  Evap: shape {evap_mean.shape}, range {np.nanmin(evap_mean):.4f} to {np.nanmax(evap_mean):.4f} m")
        
        # Check for water-like pattern in PEV
        evap_positive = (evap_mean > 0.001).sum()
        evap_near_zero = (evap_mean < 0.001).sum()
        print(f"  Evap > 0.001: {evap_positive} cells (potential water)")
        print(f"  Evap < 0.001: {evap_near_zero} cells (likely land/dry)")
    else:
        evap_mean = None
        print(f"  Evap: NOT AVAILABLE")
    
    if temp_mean is None and evap_mean is None:
        print("  No data available!")
        return
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    if temp_mean is not None and evap_mean is not None:
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        fig.suptitle(f"{name} - Data Inspection", fontsize=14, fontweight='bold')
        
        # Temperature
        im1 = axes[0].pcolormesh(lons, lats, temp_mean, cmap="viridis", shading="auto")
        axes[0].set_title("Temperature (time avg)")
        axes[0].set_xlabel("Longitude (°E)")
        axes[0].set_ylabel("Latitude (°N)")
        axes[0].set_aspect("equal")
        plt.colorbar(im1, ax=axes[0], label="K")
        
        # Evaporation
        im2 = axes[1].pcolormesh(lons, lats, evap_mean, cmap="Blues", shading="auto")
        axes[1].set_title("Potential Evaporation (time avg)")
        axes[1].set_xlabel("Longitude (°E)")
        axes[1].set_ylabel("Latitude (°N)")
        axes[1].set_aspect("equal")
        plt.colorbar(im2, ax=axes[1], label="m water equivalent")
        
        plt.tight_layout()
        
        if save:
            out_path = OUTPUT_DIR / f"{node_id}_inspection.png"
            plt.savefig(out_path, dpi=150)
            print(f"  Saved: {out_path}")
        
        if show:
            plt.show()
        else:
            plt.close()
    
    elif temp_mean is not None:
        fig, ax = plt.subplots(figsize=(8, 6))
        im = ax.pcolormesh(lons, lats, temp_mean, cmap="viridis", shading="auto")
        ax.set_title(f"{name} - Temperature")
        ax.set_xlabel("Longitude (°E)")
        ax.set_ylabel("Latitude (°N)")
        ax.set_aspect("equal")
        plt.colorbar(im, ax=ax, label="K")
        plt.tight_layout()
        
        if save:
            out_path = OUTPUT_DIR / f"{node_id}_temp.png"
            plt.savefig(out_path, dpi=150)
            print(f"  Saved: {out_path}")
        
        if show:
            plt.show()
        else:
            plt.close()
    
    elif evap_mean is not None:
        fig, ax = plt.subplots(figsize=(8, 6))
        im = ax.pcolormesh(lons, lats, evap_mean, cmap="Blues", shading="auto")
        ax.set_title(f"{name} - Evaporation")
        ax.set_xlabel("Longitude (°E)")
        ax.set_ylabel("Latitude (°N)")
        ax.set_aspect("equal")
        plt.colorbar(im, ax=ax, label="m")
        plt.tight_layout()
        
        if save:
            out_path = OUTPUT_DIR / f"{node_id}_evap.png"
            plt.savefig(out_path, dpi=150)
            print(f"  Saved: {out_path}")
        
        if show:
            plt.show()
        else:
            plt.close()


def main():
    parser = argparse.ArgumentParser(description="Plot lake data inspection maps")
    parser.add_argument("node", nargs="?", help="Node ID to plot (default: all)")
    parser.add_argument("--no-show", action="store_true", help="Don't show interactive plot")
    parser.add_argument("--no-save", action="store_true", help="Don't save to file")
    parser.add_argument("--pev", action="store_true", help="Filter: show PEV instead of absolute")
    args = parser.parse_args()
    
    nodes = load_nodes()
    data = load_era5_data()
    
    show = not args.no_show
    save = not args.no_save
    
    if args.node:
        # Plot single node
        node = get_node(args.node, nodes)
        if node is None:
            print(f"ERROR: Unknown node '{args.node}'")
            print(f"  Available: {', '.join([n['id'] for n in nodes])}")
            sys.exit(1)
        plot_single(data, node, show=show, save=save)
    else:
        # Plot all nodes
        for node in nodes:
            plot_single(data, node, show=False, save=save)
        
        print(f"\n=== All plots saved to {OUTPUT_DIR}/ ===")
        print("\nNOTE: ERA5 PEV is negative (evaporation). Lower absolute values =")
        print("      less evaporation demand = MORE likely to be open water.")


if __name__ == "__main__":
    main()