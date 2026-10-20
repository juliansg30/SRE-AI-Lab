"""Telemetría sintética; NO llama endpoints, Azure ni sistemas institucionales."""
from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path


def generar_registros(escenario: str, n: int = 120, semilla: int = 42):
    """Genera eventos de solicitud y spans simulados con trace_id consistente."""
    if escenario not in ("normal", "degradado"):
        raise ValueError("Escenario desconocido")
    rng = random.Random(semilla)
    base = datetime.now(timezone.utc).replace(microsecond=0)
    eventos, trazas = [], []
    for i in range(n):
        fallo_inyectado = escenario == "degradado" and i >= n // 2
        latencia = max(30, round(rng.gauss(95, 18)))
        if fallo_inyectado:
            latencia += 260 + rng.randint(0, 130)
        # Un error controlado en cada 167 solicitudes normales; en la fase de
        # caos, un HTTP 503 por cada tres solicitudes de la segunda mitad.
        error = ((i + 1) % 167 == 0) or (fallo_inyectado and i % 3 == 0)
        marca = (base + timedelta(seconds=i)).isoformat()
        trace_id = f"{i + 1 + semilla * 1000000:032x}"
        request_id = f"sol-{i + 1:04d}"
        codigo = 503 if error else 200
        eventos.append({
            "timestamp": marca,
            "event_type": "http_request",
            "service": "catalogo-api",
            "request_id": request_id,
            "trace_id": trace_id,
            "method": "GET",
            "path": "/productos",
            "status_code": codigo,
            "latency_ms": latencia,
            "fault_injected": fallo_inyectado,
        })
        trazas += [
            {"timestamp": marca, "trace_id": trace_id,
             "span_id": f"{(i + 1) * 2:016x}", "parent_span_id": None,
             "service": "api-gateway", "duration_ms": latencia + 8},
            {"timestamp": marca, "trace_id": trace_id,
             "span_id": f"{(i + 1) * 2 + 1:016x}",
             "parent_span_id": f"{(i + 1) * 2:016x}",
             "service": "catalogo-api", "duration_ms": latencia},
        ]
    if escenario == "degradado":
        i = n // 2
        eventos.append({
            "timestamp": (base + timedelta(seconds=i)).isoformat(),
            "event_type": "security_control_deleted_SIMULATED",
            "service": "lab-auditoria", "request_id": "aud-0001",
            "trace_id": eventos[i]["trace_id"],
            "resource_id": "SIMULADO/firewall/lab/regla-proteccion",
            "actor": "estudiante-laboratorio", "authorized": True,
            "note": "Caso ficticio; no se elimina ningún recurso real.",
        })
    return eventos, trazas


def guardar_jsonl(ruta: Path, registros: list[dict]):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8") as f:
        for registro in registros:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def generar_archivos(escenario: str, salida: Path):
    base, _ = generar_registros("normal", n=200, semilla=10)
    evaluacion, trazas = generar_registros(escenario, n=120, semilla=42)
    guardar_jsonl(salida / "baseline.jsonl", base)
    guardar_jsonl(salida / "evaluacion.jsonl", evaluacion)
    guardar_jsonl(salida / "trazas.jsonl", trazas)
    print(f"Escenario: {escenario}. Generados {len(base)} registros de entrenamiento, "
          f"{len(evaluacion)} eventos evaluados y {len(trazas)} spans simulados.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--escenario", choices=["normal", "degradado"],
                        default="normal")
    parser.add_argument("--salida", default="datos")
    args = parser.parse_args()
    generar_archivos(args.escenario, Path(args.salida))
