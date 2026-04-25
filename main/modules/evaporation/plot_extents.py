#!/usr/bin/env python3
"""
Plot lake/reservoir extents on a map.
Reads extent definitions from nodes.yaml and visualizes each bounding box.
Overlays lake_cover.nc as background (blue=water, white=land).

Usage:
    python plot_extents.py
"""

import pathlib
import argparse
import yaml
import numpy as np
import xarray as xr
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import ListedColormap

HERE = pathlib.Path(__file__).parent
NODES_FILE = HERE / "nodes.yaml"
ERA5_CACHE_DIR = HERE / "era5_cache"
OUTPUT_FILE = HERE / "lake_extents.png"

# Water detection threshold
LAKE_COVER_THRESHOLD = 0.5  # cl > this = water

COLORS = [
    '#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00',
    '#ffff33', '#a65628', '#f781bf', '#999999', '#66c31a',
    '#8dd3c7', '#ffffb3', '#bebada'
]


def load_nodes() -> list[dict]:
    with open(NODES_FILE) as f:
        data = yaml.safe_load(f)
    return data.get("nodes", [])


def get_lake_cover_data():
    lc_path = ERA5_CACHE_DIR / "lake_cover.nc"
    if not lc_path.exists():
        return None
    ds = xr.open_dataset(str(lc_path), engine="netcdf4")
    cl = ds["cl"].squeeze().values
    lats = ds.coords["latitude"].values
    lons = ds.coords["longitude"].values
    return cl, lats, lons


def plot_extents(show: bool = True):
    nodes = load_nodes()
    fig, ax = plt.subplots(figsize=(14, 10))
    
    lc_data = get_lake_cover_data()
    if lc_data is not None:
        cl, lats, lons = lc_data
        lon_mesh, lat_mesh = np.meshgrid(lons, lats)
        water_mask = (cl > LAKE_COVER_THRESHOLD).astype(float)
        cmap = ListedColormap(['white', '#bdd7e7'])
        ax.pcolormesh(lon_mesh, lat_mesh, water_mask, cmap=cmap, shading='auto')
        print(f"  Lake cover: {water_mask.sum()} water cells")
    
    for i, node in enumerate(nodes):
        node_id = node["id"]
        extent = node.get("extent", {})
        lat_min = extent.get("lat_min")
        lat_max = extent.get("lat_max")
        lon_min = extent.get("lon_min")
        lon_max = extent.get("lon_max")
        
        if None in (lat_min, lat_max, lon_min, lon_max):
            continue
        
        width = lon_max - lon_min
        height = lat_max - lat_min
        color = COLORS[i % len(COLORS)]
        
        rect = plt.Rectangle((lon_min, lat_min), width, height, fill=False, edgecolor=color, linewidth=2)
        ax.add_patch(rect)
        ax.annotate(node_id.capitalize(), (lon_min + width/2, lat_min + height/2),
                   ha='center', va='center', fontsize=8, color=color, fontweight='bold',
                   bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.7, edgecolor=color))
    
    ax.set_xlim(25, 42)
    ax.set_ylim(-5, 36)
    ax.set_xlabel("Longitude (°E)", fontsize=12)
    ax.set_ylabel("Latitude (°N)", fontsize=12)
    ax.set_title("Lake and Reservoir Extents — Nile Basin", fontsize=14, fontweight='bold')
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3, linestyle='--')
    
    legend_patches = [mpatches.Patch(color=COLORS[i], label=nodes[i]['id'].capitalize()) for i in range(len(nodes))]
    ax.legend(handles=legend_patches, loc='upper left', fontsize=7, ncol=2, framealpha=0.9)
    
    fig.tight_layout()
    if show:
        plt.show()
    fig.savefig(OUTPUT_FILE, dpi=150)
    print(f"Saved: {OUTPUT_FILE}")


def main():
    parser = argparse.ArgumentParser(description="Plot lake extents")
    parser.add_argument("--no-show", action="store_true", help="Don't show interactive plot")
    args = parser.parse_args()
    plot_extents(show=not args.no_show)


if __name__ == "__main__":
    main()