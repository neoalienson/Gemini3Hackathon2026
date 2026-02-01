"""
Insight Exploration using Google ADK with Planning Agent and Data Agent.
1. Planning Agent: injects schema/cubes, generates query plan with steps.
2. Data Agent: executes plan using sql_generation, sql_execution, python_generation tools.
"""
import json
import os
import re
import logging
import tempfile
import uuid
import traceback
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

SQL_GEN_RETRY_LIMIT = 5
SQL_EXEC_RETRY_LIMIT = 5
PYTHON_GEN_RETRY_LIMIT = 5
AGENT_RETRY_LIMIT = 7  # Retry planning + data agent when generation fails


def _extract_and_parse_json(s: str) -> Any:
    """Extract and parse JSON from a string that may contain extra text or invalid control characters."""
    if s is None:
        return None
    if not isinstance(s, str):
        return s
    s = s.strip()
    if not s:
        return None

    def _try_parse(raw: str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    parsed = _try_parse(s)
    if parsed is not None:
        return parsed

    def _extract_object(txt: str, open_c: str, close_c: str):
        start = txt.find(open_c)
        if start < 0:
            return None
        depth = 0
        for i, c in enumerate(txt[start:], start):
            if c == open_c:
                depth += 1
            elif c == close_c:
                depth -= 1
                if depth == 0:
                    return txt[start : i + 1]
        return None

    extracted = _extract_object(s, "{", "}") or _extract_object(s, "[", "]")
    if extracted:
        parsed = _try_parse(extracted)
        if parsed is not None:
            return parsed
        sanitized = re.sub(r"[\x00-\x1f\x7f]", " ", extracted)
        parsed = _try_parse(sanitized)
        if parsed is not None:
            return parsed

    sanitized = re.sub(r"[\x00-\x1f\x7f]", " ", s)
    parsed = _try_parse(sanitized)
    if parsed is not None:
        return parsed

    raise json.JSONDecodeError(f"Cannot extract valid JSON from string (length={len(s)})", s, 0)


def _ensure_vertex_env():
    if os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() not in ("true", "1", "yes"):
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
    if not os.getenv("GOOGLE_CLOUD_PROJECT") and os.getenv("GCP_PROJECT"):
        os.environ["GOOGLE_CLOUD_PROJECT"] = os.environ["GCP_PROJECT"]
    if not os.getenv("GOOGLE_CLOUD_LOCATION"):
        os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"


def _get_planning_agent(context: str):
    """Create planning agent with injected schema and data cube context."""
    _ensure_vertex_env()
    model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash-lite")
    try:
        from google.adk.agents import LlmAgent
    except ImportError as e:
        raise ImportError("Google ADK not installed. pip install google-adk") from e

    instruction = f"""You are a query planning agent for a BI system. You analyze the user's question and produce a structured query plan.

## Available Data Sources, Tables, and Data Cubes (JSON)

{context}

## Your Task

1. Break down the user query into a sequence of **query instructions**. Each instruction:
   - Uses exactly ONE data source
   - Specifies which tables and/or data cubes to use
   - Describes what data to retrieve and how to get it
   - Is self-contained (no cross-source references)

2. At the end, add a **CONSOLIDATION** step that describes how to:
   - Combine all results from the above query steps
   - Link data rows from different sources
   - Apply joins, aggregations, and filtering on the combined resultset
   - Produce the final answer to the user's question

## Output Format

Produce a query plan in this exact structure:

---
QUERY_PLAN_START
## Step 1: [Brief step name]
- Data Source ID: [id from context]
- Data Source Name: [name]
- Tables: [comma-separated table names or "use data cube"]
- Data Cube ID (if applicable): [id or "none"]
- Instruction: [Detailed description of what data to retrieve and how]

## Step 2: ...
[repeat for each query step]

## CONSOLIDATION
- Instruction: [Detailed description of how to combine all CSV results, what joins/aggregations/filters to apply, and how to produce the final answer]
QUERY_PLAN_END
---

If the user's question cannot be answered with the available data sources, say so clearly and explain what is missing."""
    return LlmAgent(
        name="PlanningAgent",
        model=model_name,
        instruction=instruction,
    )


def _make_sql_generation_function(db):
    """Create sql_generation_function tool bound to db."""

    def sql_generation_function(
        query_instruction: str,
        data_source_def: str,
        table_schemas: str,
        data_cube_def_with_sql: str,
    ) -> str:
        """Generate SQL for a query instruction.
        Args:
            query_instruction: Description of what data to retrieve.
            data_source_def: JSON of data source (id, name, type, project_id, dataset, etc).
            table_schemas: JSON of table schemas (name, columns with name/type).
            data_cube_def_with_sql: JSON of data cube with 'query' (SQL) and metadata.
        Returns:
            Generated SQL string, or error message if failed after retries.
        """
        from genai.llm import generate_content

        guideline = """
SQL Generation Guidelines:
- Use BigQuery Standard SQL syntax.
- Use CTE (WITH ... AS) pattern for clarity.
- If a data cube is provided, use its SQL as a subquery in a CTE: WITH cube_data AS (data_cube_query) SELECT ...
- Restrict to tables and columns in the table schema only.
- Use fully qualified names: `project.dataset.table` or `dataset.table` when project is in data source.
- Return only the SQL, no markdown or explanation.
"""
        sql_err = ""
        for attempt in range(1, SQL_GEN_RETRY_LIMIT + 1):
            try:
                prompt = f"""{guideline}

Query instruction:
{query_instruction}

Data source definition:
{data_source_def}

Table schemas:
{table_schemas}

Data cube definition (if applicable):
{data_cube_def_with_sql}"""
                if sql_err:
                    prompt += f"""

Previous SQL failed with error:
{sql_err}

Fix the SQL and try again."""
                prompt += "\n\nGenerate the SQL query:"
                sql = generate_content(prompt, temperature=0.0).strip()
                if sql.startswith("```"):
                    lines = sql.split("\n")
                    out = []
                    in_block = False
                    for line in lines:
                        if line.strip().startswith("```"):
                            in_block = not in_block
                            continue
                        if in_block:
                            out.append(line)
                    sql = "\n".join(out) if out else sql
                sql = sql.strip().rstrip(";")

                # Validate with BigQuery dry run
                from app.models import DataSource, DataSourceType
                try:
                    ds_obj = _extract_and_parse_json(data_source_def) if isinstance(data_source_def, str) else data_source_def
                except json.JSONDecodeError as je:
                    return f"Error: Invalid JSON in data_source_def: {je}. Please pass valid JSON only (no extra text or control characters)."
                if ds_obj is None or not isinstance(ds_obj, dict):
                    return "Error: data_source_def could not be parsed. Please pass valid JSON object."
                ds_id = ds_obj.get("id")
                db_source = db.query(DataSource).filter(DataSource.id == ds_id).first()
                if not db_source:
                    return f"Error: Data source {ds_id} not found."
                if db_source.type != DataSourceType.bigquery:
                    return f"Error: Only BigQuery data sources are supported. Source {ds_id} is {db_source.type}."
                try:
                    from google.cloud import bigquery
                    from google.oauth2 import service_account
                    credentials = None
                    if db_source.password:
                        try:
                            creds_info = json.loads(db_source.password)
                            credentials = service_account.Credentials.from_service_account_info(creds_info)
                        except json.JSONDecodeError:
                            pass
                    project = db_source.project_id or db_source.host
                    client = bigquery.Client(
                        credentials=credentials,
                        project=project,
                        location=db_source.location,
                    ) if credentials else bigquery.Client(project=project, location=db_source.location)
                    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
                    client.query(sql, job_config=job_config)
                    return sql
                except Exception as e:
                    sql_err = str(e)
                    if attempt >= SQL_GEN_RETRY_LIMIT:
                        return f"SQL validation failed after {SQL_GEN_RETRY_LIMIT} attempts. Last error: {sql_err}"
            except Exception as e:
                logger.exception("sql_generation_function error: %s", e)
                if attempt >= SQL_GEN_RETRY_LIMIT:
                    return f"Error: {e}"
        return "Error: Max retries exceeded."

    return sql_generation_function


def _make_sql_execution_function(db, csv_dir: str):
    """Create sql_execution_function tool bound to db and csv_dir."""

    def sql_execution_function(
        sql: str,
        data_source_def: str,
        output_csv_filename: str,
    ) -> str:
        """Execute SQL against the data source and save result to CSV.
        Args:
            sql: SQL statement to execute.
            data_source_def: JSON of data source definition (must include id).
            output_csv_filename: Filename for output CSV (e.g. step1.csv).
        Returns:
            Success message with path, or error message.
        """
        from google.cloud import bigquery
        from google.oauth2 import service_account
        import csv
        from app.models import DataSource, DataSourceType

        try:
            try:
                ds_obj = _extract_and_parse_json(data_source_def) if isinstance(data_source_def, str) else data_source_def
            except json.JSONDecodeError as je:
                return f"Error: Invalid JSON in data_source_def: {je}. Please pass valid JSON only (no extra text or control characters)."
            if ds_obj is None or not isinstance(ds_obj, dict):
                return "Error: data_source_def could not be parsed. Please pass valid JSON object."
            ds_id = ds_obj.get("id")
            db_source = db.query(DataSource).filter(DataSource.id == ds_id).first()
            if not db_source:
                return f"Error: Data source {ds_id} not found."
            if db_source.type != DataSourceType.bigquery:
                return f"Error: Only BigQuery data sources are supported. Source {ds_id} is {db_source.type}."
            credentials = None
            if db_source.password:
                try:
                    creds_info = json.loads(db_source.password)
                    credentials = service_account.Credentials.from_service_account_info(creds_info)
                except json.JSONDecodeError:
                    pass
            project = db_source.project_id or db_source.host
            client = bigquery.Client(
                credentials=credentials,
                project=project,
                location=db_source.location,
            ) if credentials else bigquery.Client(project=project, location=db_source.location)
            query_job = client.query(sql)
            rows = list(query_job.result())
            out_path = str(Path(csv_dir) / output_csv_filename)
            if not rows:
                with open(out_path, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow([])
                return f"Success. Saved 0 rows to {out_path}"
            columns = list(rows[0].keys())
            with open(out_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=columns)
                writer.writeheader()
                for row in rows:
                    writer.writerow(dict(row))
            return f"Success. Saved {len(rows)} rows to {out_path}"
        except Exception as e:
            logger.exception("sql_execution_function error: %s", e)
            return f"SQL execution failed: {e}"

    return sql_execution_function


def _make_python_generation_function(csv_dir: str):
    """Create python_generation_function tool bound to csv_dir."""

    def python_generation_function(
        consolidation_instructions: str,
        csv_file_paths: str,
    ) -> str:
        """Generate and execute Python code to process CSV files per consolidation instructions.
        Args:
            consolidation_instructions: How to combine/process the CSV results.
            csv_file_paths: Comma-separated list of CSV file paths (or filenames in csv_dir).
        Returns:
            Result data as JSON string, or error message.
        """
        from genai.llm import generate_content

        paths = [p.strip() for p in csv_file_paths.split(",") if p.strip()]
        full_paths = []
        for p in paths:
            if os.path.isabs(p):
                full_paths.append(p)
            else:
                full_paths.append(str(Path(csv_dir) / p))

        err_msg = ""
        for attempt in range(1, PYTHON_GEN_RETRY_LIMIT + 1):
            try:
                base_prompt = f"""Generate Python code to process CSV files according to the consolidation instructions.
The code must:
1. Use pandas. Import: import pandas as pd
2. Read each CSV: pd.read_csv(path)
3. The CSV files (in order) are: {full_paths}
4. Follow the consolidation instructions exactly.
5. At the end, assign the final result to a variable named `result`.
6. If result is a DataFrame, convert: result = result.to_dict(orient='records')
7. Print the result as JSON: print(json.dumps(result))
8. Use only standard library and pandas. No other imports.
9. Return only the Python code, no markdown or explanation.

Consolidation instructions:
{consolidation_instructions}"""
                if err_msg:
                    base_prompt += f"\n\nExecution failed:\n{err_msg}\n\nFix the code and try again."
                base_prompt += "\n\nPython code:"
                code = generate_content(base_prompt, temperature=0.0).strip()
                if code.startswith("```"):
                    lines = code.split("\n")
                    out = []
                    in_block = False
                    for line in lines:
                        if "```" in line:
                            in_block = not in_block
                            continue
                        if in_block:
                            out.append(line)
                    code = "\n".join(out) if out else code
                code = code.strip()
                if not code:
                    return "Error: No code generated."

                exec_globals = {"pd": __import__("pandas"), "json": __import__("json")}
                exec_locals: dict[str, Any] = {}
                import io
                import sys
                buf = io.StringIO()
                old_stdout = sys.stdout
                sys.stdout = buf
                try:
                    exec(code, exec_globals, exec_locals)
                    sys.stdout = old_stdout
                    output = buf.getvalue()
                    result_str = output.strip() if output.strip() else None
                    if result_str is None:
                        result = exec_locals.get("result")
                        if result is not None:
                            result_str = json.dumps(result)
                    if result_str:
                        try:
                            with open(Path(csv_dir) / "consolidation_result.json", "w", encoding="utf-8") as f:
                                f.write(result_str)
                        except Exception:
                            pass
                        return result_str
                    return "No result produced."
                finally:
                    sys.stdout = old_stdout
            except Exception as e:
                err_msg = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
                if attempt >= PYTHON_GEN_RETRY_LIMIT:
                    return f"Python execution failed after {PYTHON_GEN_RETRY_LIMIT} attempts. Last error: {err_msg}"
        return "Error: Max retries exceeded."

    return python_generation_function


def _get_data_agent(db, csv_dir: str, context: str = ""):
    """Create Data Agent with sql_generation, sql_execution, python_generation tools."""
    _ensure_vertex_env()
    model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash-lite")
    try:
        from google.adk.agents import LlmAgent
    except ImportError as e:
        raise ImportError("Google ADK not installed. pip install google-adk") from e

    sql_gen = _make_sql_generation_function(db)
    sql_exec = _make_sql_execution_function(db, csv_dir)
    python_gen = _make_python_generation_function(csv_dir)

    instruction = """You are a Data Agent that executes a query plan step by step.

You will receive:
1. A query plan (between QUERY_PLAN_START and QUERY_PLAN_END) with steps to execute.
2. The full context of available data sources, tables, and data cubes (JSON below).

For each step before CONSOLIDATION:
1. Extract the data source ID, table schemas, and data cube (if any) from the context for that step.
2. Call sql_generation_function with: query_instruction (the step's Instruction), data_source_def (JSON of that data source from context), table_schemas (JSON of that source's tables), data_cube_def_with_sql (JSON of the data cube including its "query" field, or "{}" if none).
3. Call sql_execution_function with: the generated SQL, data_source_def, and output_csv_filename (e.g. step1.csv, step2.csv).
4. If sql_execution_function returns an error (e.g. "SQL execution failed: ..."), call sql_generation_function again with an updated query_instruction that includes the error: "Previous attempt failed: [error]. Fix the SQL and try again." Then call sql_execution_function again with the new SQL. Repeat until the SQL executes successfully or you have retried 5 times.
5. If any tool returns "Invalid JSON" or "could not be parsed", fix the arguments: pass valid JSON only (no extra text, markdown, or control characters). Copy the JSON object from the context exactly. Retry the tool call up to 5 times.

For the CONSOLIDATION step:
1. Call python_generation_function with: consolidation_instructions (the CONSOLIDATION Instruction), csv_file_paths (comma-separated filenames: step1.csv, step2.csv, etc).
2. The function returns the processed result.

Finally, use the result to answer the user's question clearly and provide insights. Format your response in a friendly, readable way.

## Available Data Sources, Tables, and Data Cubes (use this when calling tools)

"""
    instruction += context if context else "[]"
    return LlmAgent(
        name="DataAgent",
        model=model_name,
        instruction=instruction,
        tools=[sql_gen, sql_exec, python_gen],
    )


async def run_insight_query_stream(query: str, db):
    """
    Async generator: yields query plan (markdown), progress at each step, then final answer.
    Yields dicts: {"type": "query_plan"|"progress"|"final_answer"|"error", "content"|"message"|"step"|"detail"}
    """
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    from .insight_data import fetch_schema_and_cubes

    context = fetch_schema_and_cubes(db)
    if not context or context == "[]":
        yield {"type": "error", "content": "No data sources or schemas available. Please add data sources and sync their schemas first."}
        return

    failure_msg = "I couldn't complete the analysis. Please try again."

    for attempt in range(AGENT_RETRY_LIMIT):
        csv_dir = tempfile.mkdtemp(prefix="securebi_insight_")
        try:
            planning_agent = _get_planning_agent(context)
            session_service = InMemorySessionService()
            app_name = "securebi_insight"
            user_id = "user"
            session_id = str(uuid.uuid4())
            await session_service.create_session(
                app_name=app_name, user_id=user_id, session_id=session_id
            )
            runner = Runner(agent=planning_agent, app_name=app_name, session_service=session_service)
            user_content = types.Content(role="user", parts=[types.Part(text=query)])
            query_plan = ""
            async for event in runner.run_async(
                user_id=user_id, session_id=session_id, new_message=user_content
            ):
                if getattr(event, "is_final_response", lambda: False)():
                    if event.content and getattr(event.content, "parts", None):
                        parts = event.content.parts
                        if parts:
                            text_parts = [
                                getattr(p, "text", None) or ""
                                for p in parts
                                if getattr(p, "text", None)
                            ]
                            query_plan = "".join(text_parts).strip()
                            break

            if not query_plan:
                if attempt < AGENT_RETRY_LIMIT - 1:
                    yield {"type": "progress", "message": f"Planning failed, retrying ({attempt + 1}/{AGENT_RETRY_LIMIT})...", "detail": "retry"}
                    continue
                yield {"type": "error", "content": "Could not generate a query plan after several attempts. Please try rephrasing your question."}
                return

            if attempt == 0:
                yield {"type": "query_plan", "content": query_plan}

            data_agent = _get_data_agent(db, csv_dir, context)
            session_id2 = str(uuid.uuid4())
            await session_service.create_session(
                app_name=app_name, user_id=user_id, session_id=session_id2
            )
            runner2 = Runner(agent=data_agent, app_name=app_name, session_service=session_service)
            combined_message = f"""Query plan to execute:

{query_plan}

---
Original user question: {query}

Execute the query plan above step by step, then answer the user's question with insights."""

            user_content2 = types.Content(role="user", parts=[types.Part(text=combined_message)])
            final_text = failure_msg
            query_step = 0

            async for event in runner2.run_async(
                user_id=user_id, session_id=session_id2, new_message=user_content2
            ):
                if event.content and getattr(event.content, "parts", None):
                    for part in event.content.parts:
                        fc = getattr(part, "function_call", None) or getattr(part, "functionCall", None)
                        if fc:
                            name = (getattr(fc, "name", None) or getattr(fc, "function_name", None) or "").lower()
                            if "sql_generation" in name:
                                query_step += 1
                                yield {"type": "progress", "step": query_step, "message": "Generating SQL for query instruction...", "detail": "sql_generation"}
                            elif "sql_execution" in name:
                                yield {"type": "progress", "step": query_step, "message": "Executing SQL and saving to CSV...", "detail": "sql_execution"}
                            elif "python_generation" in name:
                                yield {"type": "progress", "step": 0, "message": "Executing consolidation step...", "detail": "consolidation"}

                if getattr(event, "is_final_response", lambda: False)():
                    if event.content and getattr(event.content, "parts", None):
                        parts = event.content.parts
                        text_parts = [
                            getattr(p, "text", None) or ""
                            for p in parts
                            if getattr(p, "text", None)
                        ]
                        final_text = "".join(text_parts).strip() or final_text
                        break

            if final_text != failure_msg:
                yield {"type": "final_answer", "content": final_text}
                try:
                    from .visualization_agent import run_visualization_agent
                    charts = run_visualization_agent(csv_dir)
                    if charts:
                        yield {"type": "visualization", "charts": charts}
                except Exception as viz_err:
                    logger.warning("Visualization agent failed: %s", viz_err)
                return

            if attempt < AGENT_RETRY_LIMIT - 1:
                yield {"type": "progress", "message": f"Analysis failed, retrying ({attempt + 1}/{AGENT_RETRY_LIMIT})...", "detail": "retry"}
        except Exception as e:
            logger.exception("run_insight_query_stream failed (attempt %s): %s", attempt + 1, e)
            if attempt < AGENT_RETRY_LIMIT - 1:
                yield {"type": "progress", "message": f"Error occurred, retrying ({attempt + 1}/{AGENT_RETRY_LIMIT})...", "detail": "retry"}
            else:
                yield {"type": "error", "content": f"Sorry, something went wrong after {AGENT_RETRY_LIMIT} attempts: {e}"}
                return
        finally:
            try:
                import shutil
                shutil.rmtree(csv_dir, ignore_errors=True)
            except Exception:
                pass

    yield {"type": "final_answer", "content": "I couldn't complete the analysis after several attempts. Please try again or rephrase your question."}
