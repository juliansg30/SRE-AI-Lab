# Laboratorio gratuito: Observabilidad, SRE y AIOps

## Requisitos
- Python 3.11+ e Internet solamente para descargar `scikit-learn` o ejecutar GitHub Actions.
- Cuenta gratuita de GitHub para la fase CI. Repositorio público **solo con datos sintéticos**; en un repositorio privado aplican las cuotas del plan.
- El flujo usa GitHub Actions con un runner estándar `ubuntu-latest`, sin secretos ni permisos de escritura.

## Ejecución local desde la carpeta raíz
```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m app.generar --escenario normal
python -m app.analizar --exigir-slo
python -m app.generar --escenario degradado
python -m app.analizar
```
Para observar cómo una compuerta de fiabilidad bloquea la degradación (salida no cero):
```bash
python -m app.analizar --exigir-slo
```
El último comando está **diseñado para devolver código 2** cuando el escenario es degradado. Es un resultado esperado, no un error del instalador.

## Archivos y significado
- `app/generar.py`: genera logs JSONL, trazas **simuladas** correlacionadas y un evento de auditoría **ficticio**.
- `app/analizar.py`: indicador SLI, SLO, presupuesto de errores en solicitudes e IA de detección con `IsolationForest`.
- `tests/test_laboratorio.py`: pruebas reproducibles para control normal y escenario degradado.
- `.github/workflows/observabilidad.yml`: ejecución automática en push a `main` y manual con selección de escenario.
- `resultados/resumen.md`, `resultados/informe.json`: resultados generados, no se deben versionar.

**Importante**: en este prototipo, los `span_id`/`trace_id` son **simulados**, no trazas instrumentadas por OpenTelemetry. El escenario modela logs y eventos de auditoría, pero no constituye un SIEM, SOC de producción ni un sistema de respuesta autónoma. No mide MTTD ni MTTR reales y no ejecuta cambios de red ni remediación. El modelo ML detecta datos atípicos, no prueba por sí solo un ataque.

## GitHub Actions (interfaz web)
1. Crear un repositorio nuevo en GitHub, público únicamente por tratarse de datos fabricados. Seleccionar rama `main`.
2. Subir **todo el contenido** conservando la estructura `.github/workflows/observabilidad.yml` (la carpeta oculta puede requerir activar mostrar ocultos).
3. Abrir `Actions`, habilitar acciones cuando se solicite y elegir `Observabilidad SRE y AIOps - laboratorio`.
4. Seleccionar `Run workflow` → `escenario=normal`, esperar job exitoso. Repetir `escenario=degradado`.
5. Revisar `Summary` y el archivo de evidencias en la sección `Artifacts` de cada ejecución.
6. Para experimentar con el bloqueo real, editar temporalmente el workflow y eliminar el `if` de la ejecución de análisis para que ambos escenarios usen `--exigir-slo`; correr degradado y observar un job rojo con artefactos publicados por `if: always()`. Revertir el archivo luego.

## Fuentes de consulta
- GitHub Actions: https://docs.github.com/en/actions
- Costos y gratuidad: https://docs.github.com/en/billing/concepts/product-billing/github-actions
- Workflow syntax: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- IsolationForest: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html
- OpenTelemetry (fase de ampliación): https://opentelemetry.io/docs/
