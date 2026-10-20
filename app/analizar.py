"""SLI/SLO + AIOps no supervisado + triage sin remediación automática."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from sklearn.ensemble import IsolationForest

SLO_OBJETIVO = 0.99
UMBRAL_LATENCIA_MS = 200


def leer_jsonl(ruta: Path) -> list[dict]:
    with ruta.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def percentil_95(valores):
    ordenados = sorted(valores)
    if not ordenados:
        raise ValueError("La colección no puede estar vacía")
    return ordenados[math.ceil(0.95 * len(ordenados)) - 1]


def es_buena(solicitud):
    return (200 <= solicitud["status_code"] < 400 and
            solicitud["latency_ms"] < UMBRAL_LATENCIA_MS)


def atributos(solicitud):
    return [
        float(solicitud["latency_ms"]),
        float(solicitud["status_code"] >= 500),
    ]


def analizar_registros(baseline: list[dict], evaluacion: list[dict]) -> dict:
    base = [x for x in baseline if x.get("event_type") == "http_request"]
    solicitudes = [x for x in evaluacion if x.get("event_type") == "http_request"]
    auditoria = [x for x in evaluacion if x.get("event_type") ==
                 "security_control_deleted_SIMULATED"]
    if len(base) < 30 or not solicitudes:
        raise ValueError("Faltan registros de entrenamiento o evaluación")
    modelo = IsolationForest(n_estimators=100, contamination=0.02, random_state=42)
    modelo.fit([atributos(x) for x in base])
    pred = modelo.predict([atributos(x) for x in solicitudes])
    anomalos = [solicitudes[i] for i, p in enumerate(pred) if p == -1]
    buenos = sum(es_buena(x) for x in solicitudes)
    total = len(solicitudes)
    p95 = percentil_95([x["latency_ms"] for x in solicitudes])
    sli = buenos / total
    presupuesto = (1 - SLO_OBJETIVO) * total
    gasto = total - buenos
    incumple = sli < SLO_OBJETIVO
    tasa_anomalias = len(anomalos) / total
    abrir_incidente = incumple or tasa_anomalias > 0.10 or bool(auditoria)
    severidad = ("alta" if sli < 0.90 else "media") if abrir_incidente else "sin-incidente"
    ejemplos = [{"trace_id": x["trace_id"], "latency_ms": x["latency_ms"],
                 "status_code": x["status_code"]} for x in anomalos[:5]]
    return {
        "muestra": total, "buenas": buenos, "sli": round(sli, 4),
        "slo": SLO_OBJETIVO, "umbral_ms": UMBRAL_LATENCIA_MS,
        "p95_ms": p95, "presupuesto_errores_solicitudes": round(presupuesto, 2),
        "consumo_errores_solicitudes": gasto, "cumple_slo": not incumple,
        "anomalias_ml": len(anomalos), "tasa_anomalias": round(tasa_anomalias, 4),
        "ejemplos_trazas_anomalas": ejemplos,
        "eventos_auditoria_simulados": len(auditoria),
        "actor_evento_auditoria": auditoria[0]["actor"] if auditoria else None,
        "auditoria_esta_autorizada": auditoria[0]["authorized"] if auditoria else None,
        "incidente": {"abrir": abrir_incidente, "severidad": severidad,
                      "estado": "pendiente-validacion-humana" if abrir_incidente else "no-aplica",
                      "contencion_automatica": False},
        "mttd": "No medido: detección por lote, no alerta en tiempo real",
        "mttr": "No medido: no se ejecutó recuperación real",
    }


def crear_resumen(r: dict) -> str:
    estado = "CUMPLE" if r["cumple_slo"] else "INCUMPLE"
    return "\n".join([
        "# Informe de observabilidad y AIOps (laboratorio sintético)", "",
        f"- Solicitudes evaluadas: **{r['muestra']}**",
        f"- SLI (solicitud 2xx/3xx con latencia < {r['umbral_ms']} ms): **{r['sli']:.2%}**",
        f"- SLO del ejercicio: **{r['slo']:.0%}**; estado: **{estado}**",
        f"- Latencia p95: **{r['p95_ms']} ms**",
        f"- Presupuesto de solicitudes malas: **{r['presupuesto_errores_solicitudes']}**",
        f"- Solicitudes malas observadas: **{r['consumo_errores_solicitudes']}**",
        f"- Anomalías IsolationForest: **{r['anomalias_ml']}** ({r['tasa_anomalias']:.2%})",
        f"- Eventos de auditoría simulados: **{r['eventos_auditoria_simulados']}**",
        f"- Incidente propuesto: **{r['incidente']['abrir']}**, "
        f"severidad **{r['incidente']['severidad']}**",
        "- Respuesta: **triaje y documentación; ninguna contención automática**", "",
        "## Observaciones y límites", "",
        "El modelo IsolationForest ofrece detección estadística, no causalidad ni "
        "evidencia definitiva de ataque. El evento de auditoría es ficticio y "
        "está marcado como autorizado para fines didácticos.",
        "MTTD y MTTR no se miden con la ejecución por lotes.", "",
        "## Correlación de trazas", "",
        "Consultar `datos/trazas.jsonl` por `trace_id` de "
        "`ejemplos_trazas_anomalas` en `resultados/informe.json`. "
        "Los spans son **simulados**, no exportaciones OTLP de OpenTelemetry.", "",
        "## Revisión humana / cierre", "",
        "- [ ] Verificar si el cambio estaba autorizado",
        "- [ ] Revisar `trace_id`, solicitudes y degradación del SLI",
        "- [ ] Proponer acción correctiva reversible (sin ejecutarla)",
        "- [ ] Registrar hipótesis, responsable y postmortem",
        "",
    ])


def ejecutar(datos: Path, resultados: Path, exigir_slo: bool):
    baseline = leer_jsonl(datos / "baseline.jsonl")
    evaluacion = leer_jsonl(datos / "evaluacion.jsonl")
    r = analizar_registros(baseline, evaluacion)
    resultados.mkdir(parents=True, exist_ok=True)
    (resultados / "informe.json").write_text(
        json.dumps(r, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    resumen = crear_resumen(r)
    (resultados / "resumen.md").write_text(resumen, encoding="utf-8")
    print(resumen)
    if exigir_slo and not r["cumple_slo"]:
        print("BLOQUEO SRE: el escenario incumple el SLO de calidad.")
        raise SystemExit(2)
    return r


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--datos", default="datos")
    parser.add_argument("--resultados", default="resultados")
    parser.add_argument("--exigir-slo", action="store_true")
    args = parser.parse_args()
    ejecutar(Path(args.datos), Path(args.resultados), args.exigir_slo)
