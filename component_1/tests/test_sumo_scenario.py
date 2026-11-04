from pathlib import Path
from src.sumo_scenario import load_tapas_scenario


def test_tiny_sumo_fixture(tmp_path: Path):
    net = tmp_path / 'tiny.net.xml'
    routes = tmp_path / 'tiny.rou.xml'
    net.write_text('''<net><location netOffset="0,0" projParameter="+proj=utm +zone=32 +ellps=WGS84 +datum=WGS84 +units=m +no_defs +type=crs"/>
      <junction id="a" x="0" y="0"/><junction id="b" x="100" y="0"/><junction id="c" x="200" y="0"/>
      <edge id="e0" from="a" to="b"><lane id="e0_0" speed="13.9" length="100"/></edge>
      <edge id="e1" from="b" to="c"><lane id="e1_0" speed="13.9" length="100"/></edge>
      <edge id="e2" from="c" to="b"><lane id="e2_0" speed="13.9" length="100"/></edge>
      <edge id="e3" from="b" to="a"><lane id="e3_0" speed="13.9" length="100"/></edge>
    </net>''')
    routes.write_text('''<routes>
      <route id="r0" edges="e0 e1"/>
      <vehicle id="v0" depart="25200" route="r0"/>
      <vehicle id="v1" depart="25800" route="r0"/>
    </routes>''')
    network, meta = load_tapas_scenario(net, routes)
    assert len(network.edges) == 4
    assert meta['accepted_route_records'] == 2
    assert abs(network.arrival_rate_profile[42] - 1 / 600) < 1e-12
    assert abs(network.arrival_rate_profile[43] - 1 / 600) < 1e-12
    assert network.gates
    assert network.od_dest_weights


def test_inline_route_fixture(tmp_path: Path):
    net = tmp_path / 'inline.net.xml'
    routes = tmp_path / 'inline.rou.xml'
    net.write_text('''<net><location netOffset="0,0" projParameter="+proj=utm +zone=32 +ellps=WGS84 +datum=WGS84 +units=m +no_defs +type=crs"/><junction id="a" x="0" y="0"/><junction id="b" x="10" y="0"/><junction id="c" x="20" y="0"/><edge id="x" from="a" to="b"><lane speed="10" length="10"/></edge><edge id="y" from="b" to="c"><lane speed="10" length="10"/></edge></net>''')
    routes.write_text('''<routes><vehicle id="v" depart="0"><route edges="x y"/></vehicle></routes>''')
    network, meta = load_tapas_scenario(net, routes)
    assert meta['accepted_route_records'] == 1


def test_sumo_projection_and_polyline_shape_are_preserved(tmp_path: Path):
    net_file = tmp_path / "geo.net.xml"
    routes_file = tmp_path / "geo.rou.xml"
    net_file.write_text("""<net>
      <location netOffset="0,0" projParameter="+proj=utm +zone=32 +ellps=WGS84 +datum=WGS84 +units=m +no_defs +type=crs"/>
      <junction id="a" x="356000" y="5640000"/><junction id="b" x="356100" y="5640000"/><junction id="c" x="356200" y="5640000"/>
      <edge id="e0" from="a" to="b"><lane id="l0" speed="13" length="100" shape="356000,5640000 356050,5640020 356100,5640000"/></edge>
      <edge id="e1" from="b" to="c"><lane id="l1" speed="13" length="100"/></edge>
      <connection from="e0" to="e1"/>
    </net>""")
    routes_file.write_text('<routes><vehicle id="v" depart="0"><route edges="e0 e1"/></vehicle></routes>')
    net, _ = load_tapas_scenario(net_file, routes_file)
    lat, lon = net.to_latlon(0, 0)
    assert 50.8 < lat < 51.1 and 6.7 < lon < 7.2
    assert len(net.edges[0].shape) == 3
    assert net.turn_data_present
    assert net.shortest_route(net.edges[0].u, net.edges[1].v) == [0, 1]
    from src.vehicle_sim import VehicleSimulation
    import json
    from pathlib import Path
    cfg = json.loads(Path("config/sim_config.json").read_text())
    sim = VehicleSimulation(cfg, net=net)
    assert sim.resting == []  # empirical trip demand does not invent initial residents
    assert sim._new_vehicle().trips_left == 0  # one observed OD trip, no synthetic extra legs
