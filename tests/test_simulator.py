import unittest

from chargegrid.models import Charger
from chargegrid.simulator import allocate_power, energy_rate, normalize_protocol, simulate


class SimulatorTests(unittest.TestCase):
    def test_allocation_never_exceeds_available_power(self):
        chargers = [
            Charger("A", "OCPP 1.6", 22, 20, "frota"),
            Charger("B", "OCPP 2.0.1", 22, 60, "normal"),
            Charger("C", "OCPP 1.6", 22, 80, "normal"),
        ]
        result = allocate_power(chargers, 30)
        self.assertLessEqual(sum(item.allocated_kw for item in result), 30.01)

    def test_priority_and_low_battery_receive_more_power(self):
        chargers = [
            Charger("urgente", "OCPP 1.6", 22, 10, "emergencia"),
            Charger("normal", "OCPP 1.6", 22, 80, "normal"),
        ]
        result = {item.charger_id: item.allocated_kw for item in allocate_power(chargers, 20)}
        self.assertGreater(result["urgente"], result["normal"])

    def test_protocol_gateway_normalizes_legacy_version(self):
        self.assertEqual(normalize_protocol("OCPP 1.5"), "OCPP 1.6-J")

    def test_peak_tariff(self):
        rate, name = energy_rate(19, 0)
        self.assertEqual(name, "ponta")
        self.assertEqual(rate, 1.32)

    def test_solar_tariff_during_generation_window(self):
        rate, name = energy_rate(13, 25)
        self.assertEqual(name, "solar")
        self.assertEqual(rate, 0.62)

    def test_no_power_keeps_active_charger_waiting(self):
        charger = Charger("A", "OCPP 1.6", 22, 30, "normal")
        result = allocate_power([charger], 0)
        self.assertEqual(result[0].allocated_kw, 0)
        self.assertEqual(result[0].status, "aguardando")

    def test_disconnected_charger_does_not_receive_power(self):
        chargers = [
            Charger("conectado", "OCPP 1.6", 11, 50, "normal"),
            Charger("desconectado", "OCPP 1.6", 22, 10, "emergencia", connected=False),
        ]
        result = {item.charger_id: item for item in allocate_power(chargers, 40)}
        self.assertEqual(result["conectado"].allocated_kw, 11)
        self.assertEqual(result["desconectado"].allocated_kw, 0)
        self.assertEqual(result["desconectado"].status, "desconectado")

    def test_simulation_reports_avoided_overload(self):
        result = simulate(
            {
                "contract_kw": 100,
                "building_kw": 80,
                "solar_kw": 0,
                "bess_kw": 0,
                "chargers": [
                    {"charger_id": "A", "requested_kw": 30, "battery_pct": 50},
                    {"charger_id": "B", "requested_kw": 30, "battery_pct": 50},
                ],
            }
        )
        self.assertEqual(result["summary"]["allocated_kw"], 20)
        self.assertEqual(result["summary"]["avoided_overload_kw"], 40)


if __name__ == "__main__":
    unittest.main()
