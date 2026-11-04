"""Component: stochastic vehicle mobility simulation.

Vehicles are NOT pre-defined. They arrive at the city gates as a random
(time-varying, bursty) process, drive on a road graph with an IDM
car-following model, rest inside the city (kerbside parking or garage),
make extra trips, and finally leave through a gate.

step() returns GPS-like records: timestamp, vehicle_id, x_m, y_m, latitude,
longitude (+ state). Everything is SIMULATED, never a real measurement.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np

from .road_network import RoadNetwork, build_city, meters_to_latlon
from .gps_contract import GPSObservation, validate_observation


@dataclass(eq=False)  # eq=False -> hashable by identity
class Vehicle:
    vid: str
    v0_factor: float          # driver's desired-speed factor vs. speed limit
    headway: float            # IDM desired time headway T [s]
    a_max: float              # IDM max acceleration [m/s^2]
    trips_left: int           # extra city trips before leaving
    phase: int = 0            # GPS reporting phase for resting vehicles
    b_comf: float = 2.0
    s0: float = 2.0
    length: float = 4.5
    route: list = field(default_factory=list)
    idx: int = 0
    pos: float = 0.0
    speed: float = 0.0
    state: str = "pending"    # pending | driving | parked | garage | exited
    to_gate: bool = False
    stop_at_end: bool = False
    stop_wait: float = 0.0
    stop_timer: float = 0.0
    node: int = -1
    rest_until: float = 0.0
    rest_xy: tuple = (0.0, 0.0)


class VehicleSimulation:
    def __init__(self, cfg: dict, net: RoadNetwork | None = None):
        self.cfg = cfg
        self.net = net or build_city(cfg["network"])
        self.rng = np.random.default_rng(cfg["seed"])
        self.dt = cfg["sim"]["dt_s"]
        self.t = 0.0
        self.t0 = datetime.fromisoformat(cfg["sim"]["start_datetime"])
        self.lat0 = cfg["region"]["center"]["lat"]
        self.lon0 = cfg["region"]["center"]["lon"]
        self.edge_veh = {e.eid: [] for e in self.net.edges}
        self.active_edge_ids: set[int] = set()
        self.pending: list[Vehicle] = []
        self.resting: list[Vehicle] = []
        self.n_spawned = 0
        self.n_exited = 0
        self.burst = 1.0
        self._gps_error: dict[str, tuple[float, float]] = {}
        self._issued_ids: set[str] = set()
        self._rest_anchor_grid: dict[tuple[int, int, int], list[tuple[float, float]]] = {}
        self._rest_anchor_cell: dict[str, tuple[int, int, int, tuple[float, float]]] = {}

        # busier and quieter gates, and a bias of destinations toward the center
        # Real-scenario loaders attach empirical entry/destination weights.
        # The synthetic fallback retains the original stochastic weights.
        supplied_gate_w = getattr(self.net, "gate_weights", None)
        self.gate_w = (np.asarray(supplied_gate_w, dtype=float)
                       if supplied_gate_w is not None else
                       self.rng.dirichlet(np.full(len(self.net.gates), 4.0)))
        rad = np.array([math.hypot(*self.net.nodes[n]) for n in self.net.city_nodes])
        w = np.exp(-rad / 2500.0) + 0.15
        supplied_dest_w = getattr(self.net, "destination_weights", None)
        self.dest_w = (np.asarray(supplied_dest_w, dtype=float)
                       if supplied_dest_w is not None else w / w.sum())
        self.od_dest_weights = getattr(self.net, "od_dest_weights", {})
        self._init_residents()

    # ---------- helpers ----------
    def _new_device_id(self) -> str:
        """Seeded opaque identifier; does not expose vehicle creation order."""
        while True:
            token = int(self.rng.integers(0, 2**48))
            candidate = f"dev_{token:012x}"
            if candidate not in self._issued_ids:
                self._issued_ids.add(candidate)
                return candidate

    def _new_vehicle(self) -> Vehicle:
        r = self.rng
        self.n_spawned += 1
        p = self.cfg["behaviour"]["extra_trips_probs"]
        if getattr(self.net, "empirical_demand", False):
            p = [1.0] + [0.0] * (len(p) - 1)
        return Vehicle(
            vid=self._new_device_id(),
            v0_factor=float(np.clip(r.normal(1.0, 0.1), 0.7, 1.3)),
            headway=float(r.uniform(1.0, 1.8)),
            a_max=float(r.uniform(1.0, 2.0)),
            trips_left=int(r.choice(len(p), p=p)),
            phase=int(r.integers(0, 3600)),
        )

    def _rest_xy(self, node: int, device_id: str):
        x, y = self.net.nodes[node]
        # Avoid placing resting devices at the same GPS anchor. The spacing is
        # an approximate curb/lot separation, not a parking-capacity model.
        cell = 4.0
        for _ in range(100):
            ang, rad = self.rng.uniform(0, 2 * math.pi), self.rng.uniform(5, 18)
            candidate = (x + rad * math.cos(ang), y + rad * math.sin(ang))
            ix, iy = math.floor(candidate[0] / cell), math.floor(candidate[1] / cell)
            nearby = (a for gx in range(ix-1, ix+2) for gy in range(iy-1, iy+2)
                      for a in self._rest_anchor_grid.get((node, gx, gy), ()))
            if all(math.dist(candidate, a) >= cell for a in nearby):
                key = (node, ix, iy)
                self._rest_anchor_grid.setdefault(key, []).append(candidate)
                self._rest_anchor_cell[device_id] = (*key, candidate)
                return candidate
        # Extremely crowded synthetic node: place a further fallback anchor.
        ang = self.rng.uniform(0, 2 * math.pi)
        candidate = (x + 25.0 * math.cos(ang), y + 25.0 * math.sin(ang))
        ix, iy = math.floor(candidate[0] / cell), math.floor(candidate[1] / cell)
        key = (node, ix, iy)
        self._rest_anchor_grid.setdefault(key, []).append(candidate)
        self._rest_anchor_cell[device_id] = (*key, candidate)
        return candidate

    def _release_rest_anchor(self, v: Vehicle):
        entry = self._rest_anchor_cell.pop(v.vid, None)
        if entry is None:
            return
        node, ix, iy, point = entry
        key = (node, ix, iy)
        bucket = self._rest_anchor_grid.get(key, [])
        try: bucket.remove(point)
        except ValueError: pass
        if not bucket: self._rest_anchor_grid.pop(key, None)

    def _start_rest(self, v: Vehicle, node: int):
        b = self.cfg["behaviour"]
        garage = self.rng.random() < b["garage_prob"]
        med = b["garage_median_s"] if garage else b["parked_median_s"]
        dur = max(60.0, float(self.rng.lognormal(math.log(med), b["rest_sigma"])))
        v.state = "garage" if garage else "parked"
        v.node, v.rest_until, v.rest_xy = node, self.t + dur, self._rest_xy(node, v.vid)
        self.resting.append(v)

    def _init_residents(self):
        """Synthetic fallback only; empirical route demand defines trip starts."""
        if getattr(self.net, "empirical_demand", False):
            return
        n = self.rng.poisson(self.cfg["behaviour"]["initial_resting_mean"])
        for _ in range(n):
            v = self._new_vehicle()
            self._start_rest(v, int(self.rng.choice(self.net.city_nodes, p=self.dest_w)))
            v.rest_until = self.t + float(self.rng.exponential(1200.0))  # residual rest

    def _plan_leg(self, v: Vehicle, node: int, force_city: bool = False) -> bool:
        for _ in range(5):
            city = force_city or v.trips_left > 0
            if city:
                od = self.od_dest_weights.get(node)
                if od:
                    od_nodes, od_weights = od
                    dest = int(self.rng.choice(od_nodes, p=od_weights))
                else:
                    dest = int(self.rng.choice(self.net.city_nodes, p=self.dest_w))
            else:
                dest = int(self.rng.choice(self.net.gates))
            route = self.net.shortest_route(node, dest)
            if route:
                if city and not force_city:
                    v.trips_left -= 1
                v.route, v.idx, v.to_gate, v.node = route, 0, not city, node
                return True
        return False

    def _draw_stop(self, v: Vehicle):
        d = self.cfg["driving"]
        last = v.idx == len(v.route) - 1
        v.stop_at_end = (not last) and self.rng.random() < d["intersection_stop_prob"]
        v.stop_wait = float(self.rng.uniform(*d["stop_wait_s"]))
        v.stop_timer = 0.0

    def _try_spawn(self, v: Vehicle) -> bool:
        e = self.net.edges[v.route[0]]
        lane = self.edge_veh[e.eid]
        if lane and min(o.pos for o in lane) < v.length + v.s0 + 2:
            return False  # entry blocked (queue at the gate)
        v.idx, v.pos, v.state = 0, 0.0, "driving"
        v.speed = min(8.0, e.speed_limit * v.v0_factor)
        self._draw_stop(v)
        lane.append(v)
        self.active_edge_ids.add(e.eid)
        return True

    def arrival_rate(self) -> float:
        """Vehicles per second entering the city (non-homogeneous)."""
        a = self.cfg["arrivals"]
        empirical = getattr(self.net, "arrival_rate_profile", None)
        if empirical is not None:
            minute_of_day = (self.t0.hour * 60 + self.t0.minute + self.t / 60) % 1440
            slot = int(minute_of_day // 10) % len(empirical)
            return float(empirical[slot]) * a.get("dataset_scale", 1.0) * a.get("density_multiplier", 1.0)
        h = self.t0.hour + self.t0.minute / 60 + self.t / 3600
        prof = a["floor"] + (1 - a["floor"]) * math.exp(-0.5 * ((h - a["peak_hour"]) / a["width_h"]) ** 2)
        return a["peak_per_hour"] * a["density_multiplier"] * prof / 3600.0

    # ---------- dynamics ----------
    def _leader(self, v: Vehicle, e, lane, i):
        gap, lv = None, 0.0
        if i > 0:
            o = lane[i - 1]
            gap, lv = o.pos - o.length - v.pos, o.speed
        elif v.idx + 1 < len(v.route):
            nl = self.edge_veh[v.route[v.idx + 1]]
            if nl:
                o = min(nl, key=lambda q: q.pos)
                g = (e.length - v.pos) + o.pos - o.length
                if g < 150:
                    gap, lv = g, o.speed
        if v.stop_at_end:
            g = e.length - v.pos
            if gap is None or g < gap:
                gap, lv = g, 0.0
        return gap, lv

    def _accel(self, v: Vehicle, e, gap, lv) -> float:
        v0 = e.speed_limit * v.v0_factor
        free = 1.0 - (v.speed / v0) ** 4
        if gap is None:
            a = v.a_max * free
        else:
            gap = max(gap, 0.1)
            s_star = v.s0 + max(0.0, v.speed * v.headway
                                + v.speed * (v.speed - lv) / (2 * math.sqrt(v.a_max * v.b_comf)))
            a = v.a_max * (free - (s_star / gap) ** 2)
        if v.speed > 0.5:
            a += self.rng.normal(0.0, self.cfg["driving"]["accel_noise_std"])
        return max(a, -9.0)

    def _move_vehicles(self):
        dt = self.dt
        for eid in sorted(self.active_edge_ids):
            lane = self.edge_veh[eid]
            if not lane:
                continue
            e = self.net.edges[eid]
            lane.sort(key=lambda q: -q.pos)
            accs = [self._accel(v, e, *self._leader(v, e, lane, i)) for i, v in enumerate(lane)]
            for i, v in enumerate(lane):
                ns = max(0.0, v.speed + accs[i] * dt)
                npos = v.pos + 0.5 * (v.speed + ns) * dt
                if i > 0:  # never overlap with the vehicle in front
                    o = lane[i - 1]
                    lim = o.pos - o.length - 0.1
                    if npos > lim:
                        npos, ns = max(v.pos, lim), min(ns, o.speed)
                v.pos, v.speed = npos, ns
                if v.stop_at_end and v.speed < 0.3 and e.length - v.pos < 3.0:
                    v.stop_timer += dt
                    if v.stop_timer >= v.stop_wait:
                        v.stop_at_end = False

    def _handle_edge_ends(self):
        done = [(v, eid) for eid in sorted(self.active_edge_ids)
                for v in self.edge_veh[eid] if v.pos >= self.net.edges[eid].length]
        self.rng.shuffle(done)
        exits = []
        for v, eid in done:
            e = self.net.edges[eid]
            if v.stop_at_end:
                v.pos, v.speed = e.length, 0.0
                continue
            if v.idx == len(v.route) - 1:               # reached the leg's destination
                self.edge_veh[eid].remove(v)
                if not self.edge_veh[eid]:
                    self.active_edge_ids.discard(eid)
                if v.to_gate or getattr(self.net, "empirical_demand", False):
                    v.state = "exited"
                    self.n_exited += 1
                    exits.append(self._record(v, *self.net.nodes[e.v]))
                elif self.rng.random() < self.cfg["behaviour"]["rest_prob"]:
                    self._start_rest(v, e.v)
                elif self._plan_leg(v, e.v):            # short stop only, keep going
                    v.state = "pending"
                    self.pending.append(v)
                continue
            nxt = v.route[v.idx + 1]
            nl = self.edge_veh[nxt]
            if nl and min(o.pos for o in nl) < v.length + v.s0:
                v.pos, v.speed = e.length, 0.0           # next edge full: wait
                continue
            self.edge_veh[eid].remove(v)
            if not self.edge_veh[eid]:
                self.active_edge_ids.discard(eid)
            v.pos = min(v.pos - e.length, self.net.edges[nxt].length)
            v.idx += 1
            self._draw_stop(v)
            nl.append(v)
            self.active_edge_ids.add(nxt)
        return exits

    # ---------- reporting ----------
    def _driving_xy(self, v: Vehicle):
        e = self.net.edges[v.route[v.idx]]
        shape = e.shape or (self.net.nodes[e.u], self.net.nodes[e.v])
        # Interpolate by cumulative polyline length, preserving curved SUMO roads.
        lengths = [math.dist(a, b) for a, b in zip(shape, shape[1:])]
        total = sum(lengths) or 1.0
        target = min(max(v.pos / max(e.length, 1e-9), 0.0), 1.0) * total
        walked = 0.0
        x, y, tx, ty = shape[-1][0], shape[-1][1], 1.0, 0.0
        for segment_index, (a, b, seg_len) in enumerate(zip(shape, shape[1:], lengths)):
            if walked + seg_len >= target or segment_index == len(lengths) - 1:
                f = 0.0 if seg_len == 0 else min(1.0, max(0.0, (target-walked)/seg_len))
                x, y = a[0] + (b[0]-a[0])*f, a[1] + (b[1]-a[1])*f
                norm = max(seg_len, 1e-9)
                tx, ty = (b[0]-a[0])/norm, (b[1]-a[1])/norm
                break
            walked += seg_len
        off = self.cfg["driving"]["lane_offset_m"]
        return x + ty * off, y - tx * off

    def _record(self, v: Vehicle, x: float, y: float) -> dict:
        gps = self.cfg["gps"]
        # Correlated receiver error: a slowly varying per-device bias avoids
        # independent 3 m jumps that become implausible velocities at 1 Hz.
        sigma = float(gps["noise_std_m"])
        rho = float(gps.get("noise_correlation", 0.98))
        rho = min(0.9999, max(0.0, rho))
        bx, by = self._gps_error.get(v.vid, (0.0, 0.0))
        innovation = sigma * math.sqrt(1.0 - rho * rho)
        bx = rho * bx + float(self.rng.normal(0.0, innovation))
        by = rho * by + float(self.rng.normal(0.0, innovation))
        self._gps_error[v.vid] = (bx, by)
        x += bx
        y += by
        converter = getattr(self.net, "to_latlon", None)
        lat, lon = converter(x, y) if converter else meters_to_latlon(x, y, self.lat0, self.lon0)
        # Public boundary: expose only fields obtainable from a phone or
        # vehicle GPS receiver. Internal state, route, speed, x/y and edge IDs
        # never cross into the downstream GNN component.
        observation = validate_observation({
            "timestamp": (self.t0 + timedelta(seconds=self.t)).isoformat(),
            "device_id": v.vid,
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
        })
        if v.state == "exited":
            self._gps_error.pop(v.vid, None)
        return observation

    def counts(self) -> dict:
        return {
            "driving": sum(len(self.edge_veh[eid]) for eid in self.active_edge_ids),
            "parked": sum(v.state == "parked" for v in self.resting),
            "garage": sum(v.state == "garage" for v in self.resting),
            "queued_at_entry": len(self.pending),
            "spawned_total": self.n_spawned, "exited_total": self.n_exited,
        }

    # ---------- main loop ----------
    def step(self) -> list[GPSObservation]:
        r, dt = self.rng, self.dt
        if self.t % 60 == 0:                              # bursty (over-dispersed) arrivals
            sg = self.cfg["arrivals"]["burstiness_sigma"]
            self.burst = float(r.lognormal(-0.5 * sg * sg, sg))
        for _ in range(r.poisson(self.arrival_rate() * self.burst * dt)):
            v = self._new_vehicle()
            gate = int(r.choice(self.net.gates, p=self.gate_w))
            if self._plan_leg(v, gate, force_city=True):
                self.pending.append(v)

        awake = [v for v in self.resting if v.rest_until <= self.t]
        for v in awake:                                   # random end of rest
            if self._plan_leg(v, v.node):
                self.resting.remove(v)
                self._release_rest_anchor(v)
                v.state = "pending"
                self.pending.append(v)
            else:
                v.rest_until = self.t + 60.0
        self.pending = [v for v in self.pending if not self._try_spawn(v)]

        self._move_vehicles()
        exits = self._handle_edge_ends()
        self.t += dt

        # Exit observations belong to the end of this simulation step.
        for record in exits:
            record["timestamp"] = (
                self.t0 + timedelta(seconds=self.t)
            ).isoformat()

        gi = self.cfg["gps"].get("reporting_interval_s", self.cfg["gps"].get("driving_interval_s", 1))
        tick = int(round(self.t))
        recs = []
        if tick % gi == 0:
            for eid in sorted(self.active_edge_ids):
                for v in self.edge_veh[eid]:
                    recs.append(self._record(v, *self._driving_xy(v)))
        if tick % gi == 0:
            for v in self.resting:
                recs.append(self._record(v, *v.rest_xy))
        return recs + exits

    def stream(self, duration_s: float):
        """Yield (simulation_clock_s, GPS-only observations) each step."""
        while self.t < duration_s:
            yield self.t, self.step()
