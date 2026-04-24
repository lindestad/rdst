#!/usr/bin/env python3
"""
Plot Nile river network nodes on a geographic map with directional arrows.
Reads node positions and connections from nile.yaml.
"""

import math
import yaml
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import matplotlib.lines as mlines
import numpy as np
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.mpl.ticker import LongitudeFormatter, LatitudeFormatter


# Reference numbering matching the topology diagram (0=Cairo … 12=Victoria)
NODE_ORDER = [
    "cairo", "aswand", "merowe", "karthoum", "singa",
    "kashm", "tsengh", "ozentari", "tana", "roseires",
    "gerd", "southwest", "victoria",
]

# Per-node label nudge: (lon_offset, lat_offset), ha, va
# Chosen to steer labels away from neighbours and arrows.
LABEL_OFFSETS = {
    "victoria":  (( 0.0,  0.75), "center", "bottom"),
    "southwest": ((-1.5,  0.0 ), "right",  "center"),
    "karthoum":  ((-1.4,  0.0 ), "right",  "center"),
    "merowe":    ((-1.4,  0.0 ), "right",  "center"),
    "aswand":    (( 1.1,  0.0 ), "left",   "center"),
    "cairo":     (( 1.1,  0.0 ), "left",   "center"),
    "singa":     ((-1.4,  0.0 ), "right",  "center"),
    "roseires":  ((-1.5,  0.0 ), "right",  "center"),
    "gerd":      (( 0.0, -0.7 ), "center", "top"),
    "tana":      (( 1.1,  0.0 ), "left",   "center"),
    "kashm":     (( 1.1,  0.3 ), "left",   "bottom"),
    "tsengh":    (( 1.1,  0.0 ), "left",   "center"),
    "ozentari":  (( 1.1,  0.0 ), "left",   "center"),
}


def load_nodes(yaml_path: str) -> dict:
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    return {n["id"]: n for n in data["nodes"]}


def classify_nodes(nodes: dict):
    """Return (sources, terminals, intermediates) as sets of node IDs."""
    has_incoming = set()
    for node in nodes.values():
        for conn in node.get("connections", []):
            has_incoming.add(conn["node_id"])
    sources      = {nid for nid in nodes if nid not in has_incoming}
    terminals    = {nid for nid, n in nodes.items() if not n.get("connections")}
    intermediates = set(nodes.keys()) - sources - terminals
    return sources, terminals, intermediates


def draw_arrow(ax, src, dst, fraction, transform, rad: float = 0.15):
    """Draw a curved arrow from src to dst, with optional fraction label."""
    x0, y0 = src["longitude"], src["latitude"]
    x1, y1 = dst["longitude"], dst["latitude"]
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length == 0:
        return
    ux, uy = dx / length, dy / length
    margin = 0.5  # degrees — keeps arrowhead/tail clear of the node marker

    ax.annotate(
        "",
        xy    =(x1 - ux * margin, y1 - uy * margin),
        xytext=(x0 + ux * margin, y0 + uy * margin),
        xycoords=transform, textcoords=transform,
        arrowprops=dict(
            arrowstyle="-|>,head_width=0.35,head_length=0.3",
            color="#1a6fa8",
            lw=1.2 + fraction * 2.5,
            connectionstyle=f"arc3,rad={rad}",
        ),
        zorder=4,
    )

    if fraction < 1.0:
        # Place fraction label offset perpendicular to the chord
        perp_x, perp_y = -uy, ux
        mid_x = (x0 + x1) / 2 + perp_x * abs(rad) * 3
        mid_y = (y0 + y1) / 2 + perp_y * abs(rad) * 3
        ax.text(
            mid_x, mid_y, f"{fraction:.0%}",
            transform=transform, fontsize=6.5, color="#1a6fa8",
            ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.75),
            zorder=5,
        )


def main():
    nodes = load_nodes("nile.yaml")
    sources, terminals, _ = classify_nodes(nodes)

    lons = [n["longitude"] for n in nodes.values()]
    lats = [n["latitude"]  for n in nodes.values()]
    extent = [min(lons) - 2.5, max(lons) + 3.5,
              min(lats) - 2.5, max(lats) + 2.5]

    proj = ccrs.PlateCarree()
    fig  = plt.figure(figsize=(13, 15))
    ax   = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_extent(extent, crs=proj)

    # ── Base-map features ─────────────────────────────────────────────────────
    ax.add_feature(cfeature.OCEAN.with_scale("50m"),    facecolor="#d0e8f0", zorder=0)
    ax.add_feature(cfeature.LAND.with_scale("50m"),     facecolor="#f5f0e8", zorder=0)
    ax.add_feature(cfeature.LAKES.with_scale("50m"),    facecolor="#c8dff0", alpha=0.9, zorder=1)
    ax.add_feature(cfeature.RIVERS.with_scale("50m"),   edgecolor="#7ab8d4", lw=0.8,   zorder=1)
    ax.add_feature(cfeature.BORDERS.with_scale("50m"),  edgecolor="#aaaaaa", lw=0.6,   zorder=2)
    ax.add_feature(cfeature.COASTLINE.with_scale("50m"),edgecolor="#888888", lw=0.6,   zorder=2)

    gl = ax.gridlines(draw_labels=True, linewidth=0.4, color="gray",
                      alpha=0.5, linestyle="--", zorder=2)
    gl.top_labels   = False
    gl.right_labels = False
    gl.xformatter   = LongitudeFormatter()
    gl.yformatter   = LatitudeFormatter()

    data_transform = ccrs.Geodetic()

    # ── Reservoir-capacity colormap ───────────────────────────────────────────
    caps = np.array([float(n["reservoir"]["max_capacity"]) for n in nodes.values()])
    norm = mcolors.LogNorm(vmin=caps.min(), vmax=caps.max())
    cmap = cm.YlOrRd

    # ── Arrows: spread arc radii for nodes that receive multiple inflows ───────
    incoming_count = {nid: 0 for nid in nodes}
    for node in nodes.values():
        for conn in node.get("connections", []):
            if conn["node_id"] in incoming_count:
                incoming_count[conn["node_id"]] += 1

    incoming_idx = {nid: 0 for nid in nodes}
    for node in nodes.values():
        for conn in node.get("connections", []):
            tid = conn["node_id"]
            if tid not in nodes:
                print(f"Warning: connection target '{tid}' not found — skipped.")
                continue
            n_in = incoming_count[tid]
            idx  = incoming_idx[tid]
            # Single inflow: gentle curve; multiple inflows: fan from -0.3 to +0.3
            rad = 0.12 if n_in <= 1 else (-0.3 + 0.6 * idx / (n_in - 1))
            incoming_idx[tid] += 1
            draw_arrow(ax, node, nodes[tid], conn["fraction"], data_transform, rad)

    # ── Nodes ─────────────────────────────────────────────────────────────────
    for num, nid in enumerate(NODE_ORDER):
        if nid not in nodes:
            continue
        node = nodes[nid]
        lon, lat = node["longitude"], node["latitude"]
        cap  = float(node["reservoir"]["max_capacity"])
        size = 80 + 380 * (cap / caps.max())
        face_color = cmap(norm(cap))

        # Shape and border encode node role
        if nid in sources:
            marker, edge_color, edge_lw = "^", "#2c7bb6", 2.2
        elif nid in terminals:
            marker, edge_color, edge_lw = "s", "#d7191c", 2.2
        else:
            marker, edge_color, edge_lw = "o", "white",   1.8

        ax.scatter(lon, lat, s=size, c=[face_color], marker=marker,
                   transform=data_transform, zorder=6,
                   edgecolors=edge_color, linewidths=edge_lw)

        # Node number centred inside the marker
        text_color = "white" if norm(cap) > 0.55 else "#333333"
        ax.text(lon, lat, str(num),
                transform=data_transform,
                fontsize=6.5, fontweight="bold",
                ha="center", va="center", color=text_color, zorder=7)

        # Directional name label
        (dx, dy), ha, va = LABEL_OFFSETS.get(nid, ((0.0, 0.65), "center", "bottom"))
        ax.text(lon + dx, lat + dy, nid.capitalize(),
                transform=data_transform,
                fontsize=8.5, fontweight="bold",
                ha=ha, va=va, color="#111111", zorder=7,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.75))

    # ── Colorbar ──────────────────────────────────────────────────────────────
    sm = cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, orientation="horizontal",
                        pad=0.04, fraction=0.025, aspect=40)
    cbar.set_label("Reservoir max capacity (m³)", fontsize=8)
    cbar.ax.tick_params(labelsize=7)

    # ── Legend ────────────────────────────────────────────────────────────────
    h_src  = mlines.Line2D([], [], marker="^", color="w", markersize=9,
                           markerfacecolor="grey", markeredgecolor="#2c7bb6",
                           markeredgewidth=1.8, label="Source node (no upstream)")
    h_int  = mlines.Line2D([], [], marker="o", color="w", markersize=9,
                           markerfacecolor="grey", markeredgecolor="white",
                           markeredgewidth=1.5, label="Intermediate node")
    h_term = mlines.Line2D([], [], marker="s", color="w", markersize=9,
                           markerfacecolor="grey", markeredgecolor="#d7191c",
                           markeredgewidth=1.8, label="Terminal node (no outflow)")
    h_flow = mpatches.Patch(color="#1a6fa8", label="Water flow (width ∝ fraction)")
    ax.legend(handles=[h_src, h_int, h_term, h_flow],
              loc="lower left", fontsize=8, framealpha=0.9)

    ax.set_title("Nile River Network — Node Connections", fontsize=14, pad=12)
    fig.tight_layout()
    out = "nile_network_map.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"Saved → {out}")


if __name__ == "__main__":
    main()

