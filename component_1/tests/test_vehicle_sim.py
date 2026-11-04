import copy, json
from pathlib import Path
from src.road_network import build_city
from src.vehicle_sim import VehicleSimulation

CFG = json.loads(Path('config/sim_config.json').read_text())


def test_same_seed_reproduces_stream():
    cfg = copy.deepcopy(CFG)
    a = VehicleSimulation(cfg, net=build_city(cfg['network']))
    b = VehicleSimulation(copy.deepcopy(cfg), net=build_city(cfg['network']))
    out_a, out_b = [], []
    for _, rows in a.stream(120): out_a.extend(rows)
    for _, rows in b.stream(120): out_b.extend(rows)
    assert out_a == out_b


def test_resting_emitted_gps_position_is_stationary_without_measurement_noise():
    cfg = copy.deepcopy(CFG)
    cfg['gps']['noise_std_m'] = 0.0
    sim = VehicleSimulation(cfg, net=build_city(cfg['network']))
    v = sim._new_vehicle()
    node = sim.net.city_nodes[0]
    sim._start_rest(v, node)
    first = sim._record(v, *v.rest_xy)
    sim.t += 1
    second = sim._record(v, *v.rest_xy)
    assert (first['latitude'], first['longitude']) == (second['latitude'], second['longitude'])


def test_public_stream_contains_only_gps_observation_fields():
    from src.gps_contract import GPS_FIELDS, validate_observation
    cfg = copy.deepcopy(CFG)
    sim = VehicleSimulation(cfg, net=build_city(cfg['network']))
    rows = []
    for _, batch in sim.stream(30):
        rows.extend(batch)
    assert rows
    assert all(set(row) == set(GPS_FIELDS) for row in rows)
    assert all(-90 <= row['latitude'] <= 90 for row in rows)
    assert all(-180 <= row['longitude'] <= 180 for row in rows)
    assert all(validate_observation(row) == row for row in rows)


def test_gps_contract_rejects_simulator_internal_fields():
    import pytest
    from src.gps_contract import validate_observation
    with pytest.raises(ValueError, match='schema mismatch'):
        validate_observation({
            'device_id': 'device_1', 'timestamp': '2026-01-01T07:00:00',
            'latitude': 50.0, 'longitude': 6.0, 'speed': 10.0,
        })


def test_gps_noise_is_temporally_correlated_and_does_not_create_large_stationary_jumps():
    import math
    cfg = copy.deepcopy(CFG)
    cfg['gps']['noise_std_m'] = 3.0
    cfg['gps']['noise_correlation'] = 0.98
    sim = VehicleSimulation(cfg, net=build_city(cfg['network']))
    v = sim._new_vehicle()
    fixes = []
    for i in range(1200):
        sim.t = float(i)
        fixes.append(sim._record(v, 0.0, 0.0))
    speeds = []
    for a, b in zip(fixes, fixes[1:]):
        dy = math.radians(b['latitude'] - a['latitude']) * 6371000
        dx = math.radians(b['longitude'] - a['longitude']) * 6371000 * math.cos(math.radians(a['latitude']))
        speeds.append(math.hypot(dx, dy))
    assert float(__import__('numpy').percentile(speeds, 95)) < 3.0


def test_resting_devices_use_same_one_second_reporting_cadence():
    cfg = copy.deepcopy(CFG)
    sim = VehicleSimulation(cfg, net=build_city(cfg['network']))
    v = sim._new_vehicle()
    sim._start_rest(v, sim.net.city_nodes[0])
    v.rest_until = 10000
    rows = sim.step()
    assert any(r['device_id'] == v.vid for r in rows)


def test_device_ids_are_opaque_not_sequential_and_reproducible():
    cfg = copy.deepcopy(CFG)
    a = VehicleSimulation(cfg, net=build_city(cfg['network']))
    b = VehicleSimulation(copy.deepcopy(cfg), net=build_city(cfg['network']))
    ids_a = [a._new_vehicle().vid for _ in range(20)]
    ids_b = [b._new_vehicle().vid for _ in range(20)]
    assert ids_a == ids_b
    assert len(set(ids_a)) == 20
    assert ids_a[0] != 'device_000001'


def test_rest_anchors_are_not_coincident():
    cfg = copy.deepcopy(CFG)
    sim = VehicleSimulation(cfg, net=build_city(cfg['network']))
    for _ in range(30):
        v = sim._new_vehicle()
        sim._start_rest(v, sim.net.city_nodes[0])
    anchors = [v.rest_xy for v in sim.resting]
    for i, a in enumerate(anchors):
        for b in anchors[i+1:]:
            assert __import__('math').dist(a, b) >= 4.0


def test_vehicles_do_not_overlap_on_same_edge_after_steps():
    cfg = copy.deepcopy(CFG)
    sim = VehicleSimulation(cfg, net=build_city(cfg['network']))
    for _ in range(180):
        sim.step()
        for lane in sim.edge_veh.values():
            ordered = sorted(lane, key=lambda v: -v.pos)
            for front, rear in zip(ordered, ordered[1:]):
                assert front.pos - front.length >= rear.pos - 1e-6
