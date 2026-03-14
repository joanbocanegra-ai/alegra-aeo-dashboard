# Alegra AEO — Golden Stack Dashboard

Dashboard interactivo para monitoreo de Answer Engine Optimization (AEO) de Alegra en motores de IA.

## Arquitectura

- **SQLite** (`aeo_data.db`): Base de datos con 3 tablas (metricas, marcas, dominios)
- **Streamlit** (`app.py`): Dashboard interactivo con Plotly charts
- **HTML** (`index.html`): Versión estática desplegable sin servidor

## Tablas de datos

| Tabla | Descripción | Registros |
|-------|-------------|-----------|
| `metricas` | KPIs por prompt × motor | 4 |
| `marcas` | Marcas mencionadas por prompt × motor | 22 |
| `dominios` | Dominios citados por prompt × motor | 32 |

## Deploy en Streamlit Community Cloud

1. Subir este directorio a un repositorio de GitHub
2. Ir a [share.streamlit.io](https://share.streamlit.io)
3. Conectar el repositorio y seleccionar `app.py`
4. El `requirements.txt` y `.streamlit/config.toml` se detectan automáticamente

## Ejecución local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Regenerar datos

```bash
python create_db.py  # Recrea la base de datos desde cero
```

## Filtros disponibles

- **País**: Filtrar por mercado (MX, CO, etc.)
- **Funnel**: TOFU, MOFU, BOFU
- **Categoría**: Branded, Contabilidad, Facturación, etc.
- **Motor**: ChatGPT Search, Google AI Overview
