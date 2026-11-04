"""Launch a live GPS-only vehicle simulation map dashboard (stdlib only).

Run from the project root: python run_dashboard.py --host 127.0.0.1 --port 8050
The browser receives only device_id, timestamp, latitude and longitude.
"""
from __future__ import annotations
import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from src.vehicle_sim import VehicleSimulation
from src.road_network import build_city
from src.sumo_scenario import load_tapas_scenario

ROOT = Path(__file__).resolve().parent


def make_sim(net_path: str | None = None, routes_path: str | None = None):
    cfg = json.loads((ROOT / "config/sim_config.json").read_text())
    if bool(net_path) != bool(routes_path):
        raise ValueError("Provide both net and routes, or neither")
    if net_path:
        net, _ = load_tapas_scenario(net_path, routes_path)
        cfg["region"]["center"] = {"lat": net.geo_center[0], "lon": net.geo_center[1]}
    else:
        net = build_city(cfg["network"])
    return VehicleSimulation(cfg, net=net), cfg


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "GPSMobilityDashboard/1.0"

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            html = (ROOT / "templates/index.html").read_bytes()
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html))); self.end_headers(); self.wfile.write(html)
        elif parsed.path == "/health":
            body = json.dumps({"status": "ok", "gps_schema": ["device_id", "timestamp", "latitude", "longitude"]}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        elif parsed.path == "/stream":
            self.stream_positions(parse_qs(parsed.query))
        else:
            self.send_error(404)

    def stream_positions(self, query):
        duration = max(1, min(int(query.get("duration", [3600])[0]), 86400))
        speed = max(0.1, min(float(query.get("speed", [1.0])[0]), 20.0))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        def send(payload):
            self.wfile.write(("data: " + json.dumps(payload, separators=(",", ":")) + "\n\n").encode())
            self.wfile.flush()

        try:
            sim, cfg = make_sim(self.server.net_path, self.server.routes_path)
            send({"type": "meta", "center": cfg["region"]["center"], "duration_s": duration,
                  "speed_multiplier": speed,
                  "network": "TAPASCologne SUMO network" if self.server.net_path else "synthetic radial/ring fallback"})
            wall_start = time.monotonic()
            while sim.t < duration:
                tick_start = time.monotonic()
                _, observations = next(sim.stream(min(duration, sim.t + 1)))
                # Only the strict public GPS contract crosses the browser boundary.
                send({"type": "positions", "sim_time_s": sim.t, "observations": observations})
                delay = (1.0 / speed) - (time.monotonic() - tick_start)
                if delay > 0:
                    time.sleep(delay)
            send({"type": "complete", "wall_clock_s": round(time.monotonic() - wall_start, 2)})
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as exc:
            try: send({"type": "error", "message": str(exc)})
            except (BrokenPipeError, ConnectionResetError): pass

    def log_message(self, fmt, *args):
        print("[dashboard] " + fmt % args)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live GPS vehicle simulation map")
    parser.add_argument("--host", default="127.0.0.1", help="Loopback only; remote binding is intentionally disabled")
    parser.add_argument("--port", type=int, default=8050)
    parser.add_argument("--net", help="Optional local SUMO .net.xml; configured at startup, never via URL")
    parser.add_argument("--routes", help="Optional local SUMO .rou.xml; configured at startup, never via URL")
    args = parser.parse_args()
    import ipaddress
    try: is_loopback = ipaddress.ip_address(args.host).is_loopback
    except ValueError: is_loopback = args.host.lower() == "localhost"
    if not is_loopback:
        parser.error("Dashboard is restricted to loopback addresses (127.0.0.1/::1); remote binding is disabled")
    if bool(args.net) != bool(args.routes):
        parser.error("Pass both --net and --routes, or neither")
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    server.net_path, server.routes_path = args.net, args.routes
    print(f"Live GPS map: http://{args.host}:{args.port}")
    print("Map tiles require internet access; GPS stream is generated locally.")
    print("Security: loopback-only server; dataset paths are accepted only as startup arguments.")
    try: server.serve_forever()
    except KeyboardInterrupt: print("\nStopping dashboard…")
    finally: server.server_close()
