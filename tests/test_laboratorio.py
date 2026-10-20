"""Pruebas unitarias del SLO, del caos y del detector."""
import unittest

from app.analizar import analizar_registros, es_buena, percentil_95
from app.generar import generar_registros


class LaboratorioSRETests(unittest.TestCase):
    def test_percentil_95(self):
        self.assertEqual(percentil_95(list(range(1, 101))), 95)

    def test_buena_solicitud_requiere_exito_y_latencia(self):
        self.assertTrue(es_buena({"status_code": 200, "latency_ms": 95}))
        self.assertFalse(es_buena({"status_code": 503, "latency_ms": 95}))
        self.assertFalse(es_buena({"status_code": 200, "latency_ms": 250}))

    def test_control_normal_cumple(self):
        base, _ = generar_registros("normal", n=200, semilla=10)
        normales, _ = generar_registros("normal", n=120, semilla=42)
        r = analizar_registros(base, normales)
        self.assertTrue(r["cumple_slo"])
        self.assertFalse(r["incidente"]["abrir"])

    def test_caos_abre_incidente_sin_contencion(self):
        base, _ = generar_registros("normal", n=200, semilla=10)
        anomalias, trazas = generar_registros("degradado", n=120, semilla=42)
        r = analizar_registros(base, anomalias)
        self.assertFalse(r["cumple_slo"])
        self.assertTrue(r["incidente"]["abrir"])
        self.assertFalse(r["incidente"]["contencion_automatica"])
        self.assertEqual(r["eventos_auditoria_simulados"], 1)
        self.assertTrue(r["auditoria_esta_autorizada"])
        self.assertTrue(all(len(s["trace_id"]) == 32 for s in trazas))


if __name__ == "__main__":
    unittest.main()
