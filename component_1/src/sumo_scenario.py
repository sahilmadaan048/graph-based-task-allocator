"""Load TAPASCologne/SUMO network and route demand without requiring SUMO binaries.

The loader reads SUMO .net.xml and .rou.xml files. It converts directed SUMO
edges into the small RoadNetwork interface consumed by VehicleSimulation and
extracts empirical 10-minute departure rates plus gate-to-destination weights.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from pathlib import Path
import math
import xml.etree.ElementTree as ET
import numpy as np
from pyproj import CRS, Transformer
from .road_network import RoadNetwork, Edge


def _shape_xy(text: str):
    pts = []
    for token in (text or "").split():
        try:
            x, y = token.split(",")[:2]
            pts.append((float(x), float(y)))
        except (ValueError, IndexError):
            continue
    return pts


def load_sumo_network(net_file: str | Path) -> tuple[RoadNetwork, dict[str, int]]:
    """Load SUMO topology, lane geometry, passenger permissions and projection.

    SUMO coordinates are shifted by netOffset. We undo that offset before
    inverse projection and retain local metre coordinates for simulation.
    """
    root = ET.parse(net_file).getroot()
    location = root.find("location")
    if location is None or not location.get("projParameter"):
        raise ValueError("SUMO network must contain location.projParameter for geographic conversion")
    proj = location.get("projParameter")
    if proj == "!":
        raise ValueError("SUMO network has no geographic projection (projParameter='!'); use a projected TAPASCologne network")
    try:
        transformer = Transformer.from_crs(CRS.from_user_input(proj), CRS.from_epsg(4326), always_xy=True)
    except Exception as exc:
        raise ValueError(f"Cannot interpret SUMO projParameter {proj!r}: {exc}") from exc
    offset_text = location.get("netOffset", "0,0").split(",")
    offset_x, offset_y = (float(offset_text[0]), float(offset_text[1]))

    net = RoadNetwork()
    node_id_to_idx: dict[str, int] = {}
    coords = []
    for node in root.findall("junction"):
        nid = node.get("id", "")
        if nid.startswith(":"): continue
        try: x, y = float(node.get("x")), float(node.get("y"))
        except (TypeError, ValueError): continue
        node_id_to_idx[nid] = len(coords); coords.append((x, y))
    if not coords: raise ValueError(f"No usable junctions found in {net_file}")
    cx = sum(x for x, _ in coords) / len(coords); cy = sum(y for _, y in coords) / len(coords)
    net.nodes = [(x-cx, y-cy) for x, y in coords]
    net.out_edges = {i: [] for i in range(len(net.nodes))}
    def to_latlon(x, y):
        lon, lat = transformer.transform(x + cx - offset_x, y + cy - offset_y)
        return lat, lon
    net.to_latlon = to_latlon
    net.geo_center = to_latlon(0.0, 0.0)
    edge_id_to_idx: dict[str, int] = {}
    edge_xml_by_id = {}
    for el in root.findall("edge"):
        eid = el.get("id", "")
        if eid.startswith(":"): continue
        u_id, v_id = el.get("from"), el.get("to")
        if u_id not in node_id_to_idx or v_id not in node_id_to_idx: continue
        lanes = el.findall("lane")
        # For ordinary passenger-car GPS mobility, ignore edges explicitly
        # forbidden to passenger vehicles.
        usable = []
        edge_allow = set((el.get("allow") or "").split())
        edge_disallow = set((el.get("disallow") or "").split())
        for lane in lanes:
            allow = set((lane.get("allow") or "").split()) or edge_allow
            disallow = set((lane.get("disallow") or "").split()) | edge_disallow
            if allow and "passenger" not in allow and "all" not in allow: continue
            if "passenger" in disallow or "all" in disallow: continue
            usable.append(lane)
        if not usable: continue
        speeds, lengths, shapes = [], [], []
        for lane in usable:
            try:
                speeds.append(float(lane.get("speed", "13.89")))
                lengths.append(float(lane.get("length", "0")))
            except ValueError: pass
            shp = _shape_xy(lane.get("shape") or el.get("shape") or "")
            if len(shp) >= 2: shapes.append(shp)
        if not speeds: continue
        u, v = node_id_to_idx[u_id], node_id_to_idx[v_id]
        geom_len = math.dist(net.nodes[u], net.nodes[v])
        length = max(float(np.mean(lengths)) if lengths else 0.0, geom_len, 1.0)
        # Convert the chosen lane polyline to the same centered local frame.
        raw_shape = shapes[0] if shapes else [(coords[u][0], coords[u][1]), (coords[v][0], coords[v][1])]
        shape = tuple((x-cx, y-cy) for x, y in raw_shape)
        edge_idx = len(net.edges); edge_id_to_idx[eid] = edge_idx; edge_xml_by_id[eid] = el
        net.edges.append(Edge(edge_idx, u, v, length, max(speeds), shape))
        net.out_edges[u].append(edge_idx)
    if not net.edges: raise ValueError(f"No usable passenger road edges found in {net_file}")

    connections = root.findall("connection")
    net.turn_data_present = bool(connections)
    net.allowed_next_edges = defaultdict(list)
    for conn in connections:
        a, b = conn.get("from"), conn.get("to")
        allow = set((conn.get("allow") or "").split())
        disallow = set((conn.get("disallow") or "").split())
        if allow and "passenger" not in allow and "all" not in allow:
            continue
        if "passenger" in disallow or "all" in disallow:
            continue
        if a in edge_id_to_idx and b in edge_id_to_idx:
            net.allowed_next_edges[edge_id_to_idx[a]].append(edge_id_to_idx[b])
    return net, edge_id_to_idx


def load_tapas_demand(route_file: str | Path, net: RoadNetwork,
                      edge_id_to_idx: dict[str, int]) -> dict:
    """Extract departure histogram and empirical OD weights from SUMO routes.

    Supports explicit <vehicle><route edges="..."/></vehicle> and
    <vehicle route="routeId"/> records. Route definitions are indexed first;
    vehicle records are then streamed to keep memory use moderate.
    """
    route_file = Path(route_file)
    route_defs: dict[str, list[str]] = {}
    for _, el in ET.iterparse(route_file, events=("end",)):
        if el.tag == "route" and el.get("id") and el.get("edges"):
            route_defs[el.get("id")] = el.get("edges").split()
        el.clear()

    bin_counts = np.zeros(144, dtype=float)
    gate_counts = Counter()
    od_counts = defaultdict(Counter)
    accepted = 0
    stack = []
    inline_route_edges = None
    for event, el in ET.iterparse(route_file, events=("start", "end")):
        if event == "start":
            stack.append(el.tag)
            if el.tag == "vehicle":
                inline_route_edges = None
            elif el.tag == "route" and len(stack) >= 2 and stack[-2] == "vehicle":
                inline_route_edges = el.get("edges", "").split()
            continue
        if el.tag in ("vehicle", "flow"):
            edges = inline_route_edges or []
            if not edges and el.get("route"):
                edges = route_defs.get(el.get("route"), [])
            if not edges:
                # SUMO flow can use from/to rather than an explicit route.
                from_edge, to_edge = el.get("from"), el.get("to")
                if from_edge and to_edge:
                    edges = [from_edge, to_edge]
            if len(edges) >= 2 and edges[0] in edge_id_to_idx and edges[-1] in edge_id_to_idx:
                first = net.edges[edge_id_to_idx[edges[0]]]
                last = net.edges[edge_id_to_idx[edges[-1]]]
                try:
                    depart = float(el.get("depart", el.get("begin", "0")))
                except ValueError:
                    depart = 0.0
                slot = int((depart % 86400) // 600)
                bin_counts[slot] += 1
                gate_counts[first.u] += 1
                od_counts[first.u][last.v] += 1
                accepted += 1
            inline_route_edges = None
        el.clear()
        if stack:
            stack.pop()
    if accepted == 0:
        raise ValueError("No route demand could be mapped to the loaded SUMO network. Check that .rou.xml and .net.xml versions match.")

    # Determine city destination nodes from route endpoints; retain only endpoints
    # reachable from at least one observed origin.
    dest_counts = Counter()
    for origins in od_counts.values():
        dest_counts.update(origins)
    net.gates = sorted(gate_counts)  # empirical trip origins (not geographic perimeter gates)
    net.empirical_demand = True
    gate_total = sum(gate_counts.values())
    net.gate_weights = np.array([gate_counts[g] / gate_total for g in net.gates])
    net.city_nodes = sorted(dest_counts)
    dest_total = sum(dest_counts.values())
    net.destination_weights = np.array([dest_counts[d] / dest_total for d in net.city_nodes])
    net.od_dest_weights = {}
    for origin, counts in od_counts.items():
        dests = [d for d in counts if d != origin]
        total = sum(counts[d] for d in dests)
        if total:
            net.od_dest_weights[origin] = (dests, np.array([counts[d] / total for d in dests]))
    # Counts are per 10-minute slot; use departures/600s as arrivals/sec.
    net.arrival_rate_profile = bin_counts / 600.0
    return {
        "accepted_route_records": accepted,
        "departure_counts_per_10min": bin_counts.astype(int).tolist(),
        "total_departures": int(bin_counts.sum()),
        "route_file": str(route_file),
    }


def load_tapas_scenario(net_file: str | Path, route_file: str | Path):
    net, edge_map = load_sumo_network(net_file)
    demand = load_tapas_demand(route_file, net, edge_map)
    return net, demand
