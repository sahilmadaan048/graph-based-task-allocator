"""Run Component 1. For TAPASCologne, pass the extracted SUMO .net.xml and .rou.xml."""
import argparse, json, time, csv, gzip
from collections import Counter
from pathlib import Path
from src.vehicle_sim import VehicleSimulation
from src.road_network import build_city
from src.sumo_scenario import load_tapas_scenario


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default='config/sim_config.json')
    ap.add_argument('--net', help='TAPASCologne SUMO .net.xml')
    ap.add_argument('--routes', help='TAPASCologne SUMO .rou.xml, .trips.xml, or route-demand XML')
    ap.add_argument('--output', default='data/vehicle_positions.csv.gz')
    ap.add_argument('--summary', default='data/run_summary.json')
    ap.add_argument('--duration', type=int, help='Override duration in seconds')
    ap.add_argument('--limit-records', type=int, default=0, help='Optional cap for quick smoke tests; 0 = unlimited')
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text())
    duration = args.duration or cfg['sim']['duration_s']

    if bool(args.net) != bool(args.routes):
        ap.error('Pass both --net and --routes, or neither.')
    if args.net:
        net, demand_meta = load_tapas_scenario(args.net, args.routes)
        cfg['region']['center'] = {'lat': net.geo_center[0], 'lon': net.geo_center[1]}  # actual projected network centroid
        source = 'TAPASCologne SUMO network + route demand'
    else:
        net, demand_meta = build_city(cfg['network']), None
        source = 'synthetic radial/ring fallback (NOT TAPASCologne)'

    sim = VehicleSimulation(cfg, net=net)
    peak, counts_by_10min, seen = 0, Counter(), set()
    record_count = 0
    t0 = time.time()
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    opener = gzip.open if out.suffix == '.gz' else open
    with opener(out, 'wt', newline='', encoding='utf-8') as stream_file:
        writer = csv.DictWriter(stream_file, fieldnames=['device_id', 'timestamp', 'latitude', 'longitude'])
        writer.writeheader()
        for t, recs in sim.stream(duration):
            if args.limit_records:
                recs = recs[:max(0, args.limit_records - record_count)]
            if recs:
                writer.writerows(recs)
                record_count += len(recs)
            peak = max(peak, sim.counts()['driving'])
            for r in recs:
                if r['device_id'] not in seen:
                    seen.add(r['device_id'])
                    counts_by_10min[int(t // 600)] += 1
            if args.limit_records and record_count >= args.limit_records:
                break
    elapsed = time.time() - t0
    summary = {
        'source': source, 'requested_duration_s': duration, 'simulated_duration_s': sim.t, 'wall_clock_s': round(elapsed, 3),
        'gps_records': record_count, 'unique_devices_observed': len(seen),
        'output_schema': ['device_id', 'timestamp', 'latitude', 'longitude'],
        'downstream_payload_contains_only_gps_fields': True,
        'config_seed': cfg['seed'], 'density_multiplier': cfg['arrivals'].get('density_multiplier', 1.0),
        'dataset_scale': cfg['arrivals'].get('dataset_scale', 1.0),
        'effective_empirical_arrival_multiplier': cfg['arrivals'].get('dataset_scale', 1.0) * cfg['arrivals'].get('density_multiplier', 1.0),
        'gps_noise_model': 'per-device AR(1) correlated coordinate error',
        'gps_noise_std_m': cfg['gps'].get('noise_std_m', 0.0),
        'gps_noise_correlation': cfg['gps'].get('noise_correlation', 0.0),
        'gps_reporting_interval_s': cfg['gps'].get('reporting_interval_s', cfg['sim'].get('dt_s', 1)),
        'exit_semantics': 'device stops emitting GPS fixes after its simulated trip ends; downstream must apply a no-fix timeout',
        'simulator_spawned_total': sim.n_spawned, 'simulator_exited_total': sim.n_exited,
        'peak_concurrent_driving': peak, 'final_counts': sim.counts(),
        'first_observed_device_ids_per_10min': dict(sorted(counts_by_10min.items())),
        'dataset_demand_metadata': demand_meta,
        'output_file': str(out),
        'warning': None if args.net else 'This run validates the simulator only; it does not use TAPASCologne data.'
    }
    Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
    Path(args.summary).write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))

if __name__ == '__main__':
    main()
