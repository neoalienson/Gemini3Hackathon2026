"""
Fetch table schemas and data cubes for all data sources.
Used by the insight exploration planning agent to inject context.
"""
import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from .models import DataSource, DataCube, Table, DataSourceType

logger = logging.getLogger(__name__)


def _get_bigquery_schema(db: Session, db_source: DataSource) -> list[dict[str, Any]]:
    """Fetch schema from BigQuery using INFORMATION_SCHEMA."""
    try:
        from google.cloud import bigquery
        from google.oauth2 import service_account
    except ImportError:
        logger.warning("google-cloud-bigquery not installed, skipping BigQuery schema")
        return []

    if not db_source.dataset:
        return []

    project = db_source.project_id or db_source.host
    dataset_name = db_source.dataset
    credentials = None
    if db_source.password:
        try:
            service_account_info = json.loads(db_source.password)
            credentials = service_account.Credentials.from_service_account_info(
                service_account_info
            )
        except json.JSONDecodeError:
            return []

    try:
        if credentials:
            client = bigquery.Client(
                credentials=credentials,
                project=project,
                location=db_source.location,
            )
        else:
            client = bigquery.Client(
                project=project,
                location=db_source.location,
            )

        columns_query = f"""
            SELECT table_name, column_name, data_type, is_nullable, ordinal_position
            FROM `{project}.{dataset_name}`.INFORMATION_SCHEMA.COLUMNS
            ORDER BY table_name, ordinal_position
        """
        columns_result = list(client.query(columns_query))
        tables_map: dict[str, dict] = {}
        for row in columns_result:
            table_name = row["table_name"]
            column_name = row["column_name"]
            data_type = row["data_type"]
            if table_name not in tables_map:
                tables_map[table_name] = {
                    "name": table_name,
                    "schema": dataset_name,
                    "columns": [],
                    "row_count": 0,
                    "description": None,
                }
            tables_map[table_name]["columns"].append({
                "name": column_name,
                "type": data_type,
                "primary_key": False,
                "foreign_key": None,
                "description": None,
            })
        return list(tables_map.values())
    except Exception as e:
        logger.exception("Failed to fetch BigQuery schema: %s", e)
        return []


def fetch_schema_and_cubes(db: Session) -> str:
    """
    Fetch table schemas and data cubes for all data sources.
    Returns a JSON-formatted string for injection into the planning agent prompt.
    """
    data_sources = db.query(DataSource).all()
    result: list[dict[str, Any]] = []

    for ds in data_sources:
        tables: list[dict] = []
        if ds.type == DataSourceType.bigquery:
            tables = _get_bigquery_schema(db, ds)
        else:
            db_tables = db.query(Table).filter(Table.data_source_id == ds.id).all()
            for t in db_tables:
                cols = t.columns_json or []
                tables.append({
                    "name": t.name,
                    "schema": t.schema_name,
                    "columns": cols,
                    "row_count": t.row_count or 0,
                    "description": t.description,
                })

        cubes = db.query(DataCube).filter(DataCube.data_source_id == ds.id).all()
        cubes_list = [
            {
                "id": c.id,
                "name": c.name,
                "description": c.description or "",
                "query": c.query,
                "dimensions": c.dimensions_json or [],
                "measures": c.measures_json or [],
            }
            for c in cubes
        ]

        ds_def = {
            "id": ds.id,
            "name": ds.name,
            "type": ds.type.value,
            "host": ds.host,
            "port": ds.port,
            "database": ds.database,
            "project_id": ds.project_id,
            "dataset": ds.dataset,
            "location": ds.location,
            "tables": tables,
            "data_cubes": cubes_list,
        }
        result.append(ds_def)

    return json.dumps(result, indent=2)
