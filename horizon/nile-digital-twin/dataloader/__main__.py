import typer

app = typer.Typer(help="Nile digital twin dataloader")


@app.command()
def nodes(stub: bool = typer.Option(False, help="Produce stub data (fast)")) -> None:
    """Write nodes.geojson and node_config.yaml."""
    from dataloader import nodes as _nodes
    _nodes.build(stub=stub)


@app.command()
def forcings(stub: bool = False) -> None:
    """Fetch ERA5 forcings and write per-node timeseries Parquet."""
    from dataloader import forcings as _forcings
    _forcings.build(stub=stub)


@app.command()
def overlays(stub: bool = False) -> None:
    """Fetch Sentinel-2/CGLS NDVI and write overlays Parquet."""
    from dataloader import overlays as _overlays
    _overlays.build(stub=stub)


@app.command()
def tiles() -> None:
    """Render NDVI raster tile pyramid."""
    from dataloader import tiles as _tiles
    _tiles.build()


@app.command("all")
def all_(stub: bool = False) -> None:
    """Run nodes → forcings → overlays → tiles."""
    nodes(stub=stub)
    forcings(stub=stub)
    overlays(stub=stub)
    if not stub:
        tiles()


if __name__ == "__main__":
    app()
