"""Synthetic city road graph (spokes + ring + inner/outer connectors).

Coordinates are a local metric frame (x east, y north, origin = city center).
Replace this module later with a loader for the real SUMO/OSM network; the
simulator only needs: nodes, edges, out_edges, gates, city_nodes, shortest_route.
"""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass

EARTH_RADIUS_M = 6_371_000.0


def meters_to_latlon(x_m: float, y_m: float, lat0: float, lon0: float):
    lat = lat0 + math.degrees(y_m / EARTH_RADIUS_M)
    lon = lon0 + math.degrees(x_m / (EARTH_RADIUS_M * math.cos(math.radians(lat0))))
    return lat, lon


@dataclass(frozen=True)
class Edge:
    eid: int
    u: int
    v: int
    length: float       # meters
    speed_limit: float  # m/s
    shape: tuple[tuple[float, float], ...] = ()  # local-metre polyline, endpoints included


class RoadNetwork:
    def __init__(self):
        self.nodes: list[tuple[float, float]] = []
        self.edges: list[Edge] = []
        self.out_edges: dict[int, list[int]] = {}
        self.gates: list[int] = []       # city entry/exit points on the periphery
        self.city_nodes: list[int] = []  # possible destinations inside the city
        self._route_cache: dict[tuple[int, int], list[int]] = {}

    def add_node(self, x: float, y: float) -> int:
        self.nodes.append((x, y))
        nid = len(self.nodes) - 1
        self.out_edges[nid] = []
        return nid

    def add_road(self, a: int, b: int, speed: float) -> None:
        for u, v in ((a, b), (b, a)):  # two-way road = two directed edges
            (x1, y1), (x2, y2) = self.nodes[u], self.nodes[v]
            e = Edge(len(self.edges), u, v, math.hypot(x2 - x1, y2 - y1), speed, ((x1, y1), (x2, y2)))
            self.edges.append(e)
            self.out_edges[u].append(e.eid)

    def shortest_route(self, src: int, dst: int) -> list[int]:
        """Fastest legal route by free-flow time, respecting SUMO turns if supplied."""
        key = (src, dst)
        if key in self._route_cache:
            return self._route_cache[key].copy()
        if src == dst:
            self._route_cache[key] = []
            return []
        # Edge-state Dijkstra is required when SUMO connection records define
        # legal turns. Without connection records, use the generic node graph.
        if getattr(self, "turn_data_present", False):
            dist, prev, heap = {}, {}, []
            for eid in self.out_edges.get(src, []):
                e = self.edges[eid]; d = e.length / e.speed_limit
                dist[eid] = d; heapq.heappush(heap, (d, eid))
            best = None
            while heap:
                d, eid = heapq.heappop(heap)
                if d > dist.get(eid, math.inf): continue
                edge = self.edges[eid]
                if edge.v == dst:
                    best = eid; break
                for nxt in getattr(self, "allowed_next_edges", {}).get(eid, []):
                    ne = self.edges[nxt]; nd = d + ne.length / ne.speed_limit
                    if nd < dist.get(nxt, math.inf):
                        dist[nxt], prev[nxt] = nd, eid
                        heapq.heappush(heap, (nd, nxt))
            if best is None:
                self._route_cache[key] = []; return []
            route, cur = [best], best
            while cur in prev:
                cur = prev[cur]; route.append(cur)
            result = route[::-1]
        else:
            dist, prev, heap = {src: 0.0}, {}, [(0.0, src)]
            while heap:
                d, u = heapq.heappop(heap)
                if u == dst: break
                if d > dist.get(u, math.inf): continue
                for eid in self.out_edges[u]:
                    e = self.edges[eid]; nd = d + e.length / e.speed_limit
                    if nd < dist.get(e.v, math.inf):
                        dist[e.v], prev[e.v] = nd, eid
                        heapq.heappush(heap, (nd, e.v))
            if dst not in prev:
                self._route_cache[key] = []; return []
            route, n = [], dst
            while n != src:
                route.append(prev[n]); n = self.edges[prev[n]].u
            result = route[::-1]
        self._route_cache[key] = result
        return result.copy()


def build_city(cfg: dict) -> RoadNetwork:
    net = RoadNetwork()
    k_n, radii = cfg["spokes"], cfg["spoke_radii_m"]
    ring_r = cfg["ring_radius_m"]
    kmh = cfg["speed_kmh"]
    v_in, v_ring, v_out = (kmh[k] / 3.6 for k in ("inner", "ring", "outer"))

    center = net.add_node(0.0, 0.0)
    spoke = [[None] * len(radii) for _ in range(k_n)]
    for k in range(k_n):
        a = 2 * math.pi * k / k_n
        for i, r in enumerate(radii):
            spoke[k][i] = net.add_node(r * math.cos(a), r * math.sin(a))

    seg_speed = lambda r_outer: v_in if r_outer <= ring_r else v_out
    for k in range(k_n):                      # radial roads
        prev = center
        for i, r in enumerate(radii):
            net.add_road(prev, spoke[k][i], seg_speed(r))
            prev = spoke[k][i]

    for r in cfg["connector_radii_m"]:        # concentric connectors
        i = radii.index(r)
        for k in range(k_n):
            net.add_road(spoke[k][i], spoke[(k + 1) % k_n][i], seg_speed(r))

    ring_i = radii.index(ring_r)              # ring road with intermediate nodes
    extra = cfg["ring_nodes_between_spokes"]
    for k in range(k_n):
        chain = [spoke[k][ring_i]]
        for j in range(1, extra + 1):
            a = 2 * math.pi * (k + j / (extra + 1)) / k_n
            chain.append(net.add_node(ring_r * math.cos(a), ring_r * math.sin(a)))
        chain.append(spoke[(k + 1) % k_n][ring_i])
        for a_, b_ in zip(chain, chain[1:]):
            net.add_road(a_, b_, v_ring)

    net.gates = [spoke[k][-1] for k in range(k_n)]
    gate_set = set(net.gates)
    net.city_nodes = [n for n in range(len(net.nodes)) if n not in gate_set]
    return net
