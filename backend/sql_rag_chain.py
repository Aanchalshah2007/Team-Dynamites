"""NL -> validated SELECT-only SQL -> DB -> answer text (architecture §2.3).

On UnsafeSQLError or DB error, the caller (orchestrator) must speak the
failure aloud -- never stay silent, never guess at a hardware spec.
"""

import re
import sqlite3
from dataclasses import dataclass

import config
import llm_client

_FORBIDDEN_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|DETACH|PRAGMA|REPLACE|"
    r"TRUNCATE|VACUUM|GRANT|REVOKE)\b",
    re.IGNORECASE,
)
_TABLE_REF = re.compile(r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)

_SQL_SYSTEM_PROMPT = f"""You translate natural-language questions about lab
hardware into a single SQLite SELECT statement.

Schema:
  sensors(id, name, sensor_type, measurement_range, operating_voltage, interface, response_time)
  actuators(id, name, actuator_type, range_or_capacity, operating_voltage, control_interface, response_time)

Rules:
- Only query tables: {", ".join(config.ALLOWED_TABLES)}.
- Output exactly one SELECT statement, nothing else -- no markdown, no explanation.
- Never write INSERT/UPDATE/DELETE/DDL statements.
"""

_ANSWER_SYSTEM_PROMPT = """You answer a lab technician's spoken question about
hardware specs using only the query results provided. Keep the answer short,
spoken-friendly (no markdown, no bullet points), and grounded strictly in the
given rows. If the rows are empty, say the part/spec wasn't found."""


class UnsafeSQLError(Exception):
    """Raised when generated SQL fails the SELECT-only / allow-list validation."""


@dataclass
class SqlRagResult:
    question: str
    sql: str
    rows: list[tuple]
    answer: str


def _generate_sql(question: str) -> str:
    raw = llm_client.complete(_SQL_SYSTEM_PROMPT, question, max_tokens=256).strip()
    # Strip accidental markdown fences if the model adds them anyway.
    raw = re.sub(r"^```(sql)?|```$", "", raw, flags=re.IGNORECASE | re.MULTILINE).strip()
    return raw


def _validate_sql(sql: str) -> None:
    if not sql.strip().upper().startswith("SELECT"):
        raise UnsafeSQLError("Generated statement is not a SELECT.")
    if _FORBIDDEN_KEYWORDS.search(sql):
        raise UnsafeSQLError("Generated statement contains a forbidden keyword.")
    if ";" in sql.strip().rstrip(";"):
        raise UnsafeSQLError("Generated statement contains multiple statements.")
    referenced = {m.group(1).lower() for m in _TABLE_REF.finditer(sql)}
    allowed = {t.lower() for t in config.ALLOWED_TABLES}
    if not referenced or not referenced.issubset(allowed):
        raise UnsafeSQLError(
            f"Generated statement references table(s) outside allow-list: {referenced - allowed}"
        )


def _run_query(sql: str) -> list[tuple]:
    conn = sqlite3.connect(config.DB_PATH)
    try:
        cursor = conn.execute(sql)
        return cursor.fetchall()
    finally:
        conn.close()


def _summarize(question: str, sql: str, rows: list[tuple]) -> str:
    rows_text = "\n".join(str(r) for r in rows) if rows else "(no rows)"
    prompt = f"Question: {question}\nSQL: {sql}\nRows:\n{rows_text}"
    return llm_client.complete(_ANSWER_SYSTEM_PROMPT, prompt, max_tokens=256).strip()


def answer(question: str) -> SqlRagResult:
    """Full NL -> SQL -> DB -> spoken-answer pipeline for one turn.

    Raises UnsafeSQLError on a validation failure and sqlite3.Error on a DB
    failure -- both are the orchestrator's cue to speak the failure aloud
    rather than silently dropping the turn.
    """
    sql = _generate_sql(question)
    _validate_sql(sql)
    rows = _run_query(sql)
    text = _summarize(question, sql, rows)
    return SqlRagResult(question=question, sql=sql, rows=rows, answer=text)
