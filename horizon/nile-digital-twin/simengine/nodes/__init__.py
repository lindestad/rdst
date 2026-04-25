# Importing a subclass module triggers its @register_node_class.
# Keep this file in sync as new node types are added.
from simengine.nodes import source, sink, reservoir, reach, confluence, wetland, demand_irrigation, demand_municipal  # noqa: F401
