"""Deterministic safety checks for LLM-generated PostgreSQL queries."""

import re
from dataclasses import dataclass

from data_agent.utils.observability import observed_operation


@dataclass(frozen=True)
class SQLSafetyResult:
    is_safe: bool
    reason: str


_TOKEN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*|;")
_WRITE_KEYWORDS = {
    "ALTER",
    "CALL",
    "CLUSTER",
    "COMMENT",
    "COPY",
    "CREATE",
    "DELETE",
    "DO",
    "DROP",
    "GRANT",
    "INSERT",
    "LISTEN",
    "LOAD",
    "LOCK",
    "MERGE",
    "NOTIFY",
    "REFRESH",
    "REINDEX",
    "RESET",
    "REVOKE",
    "SECURITY",
    "SET",
    "TRUNCATE",
    "UNLISTEN",
    "UPDATE",
    "VACUUM",
}
_DENIED_FUNCTIONS = {
    "DBLINK",
    "LO_EXPORT",
    "LO_IMPORT",
    "NEXTVAL",
    "PG_LOGDIR_LS",
    "PG_LS_DIR",
    "PG_READ_BINARY_FILE",
    "PG_READ_FILE",
    "PG_SLEEP",
    "SETVAL",
}


def _strip_literals_and_comments(query: str) -> str:
    """Replace literals, quoted identifiers, and comments with whitespace."""
    output: list[str] = []
    index = 0
    length = len(query)

    while index < length:
        current = query[index]
        following = query[index + 1] if index + 1 < length else ""

        if current == "-" and following == "-":
            output.extend("  ")
            index += 2
            while index < length and query[index] not in "\r\n":
                output.append(" ")
                index += 1
            continue

        if current == "/" and following == "*":
            output.extend("  ")
            index += 2
            depth = 1
            while index < length and depth:
                next_character = query[index + 1] if index + 1 < length else ""
                if query[index] == "/" and next_character == "*":
                    depth += 1
                    output.extend("  ")
                    index += 2
                elif query[index] == "*" and next_character == "/":
                    depth -= 1
                    output.extend("  ")
                    index += 2
                else:
                    output.append("\n" if query[index] in "\r\n" else " ")
                    index += 1
            continue

        if current in {"'", '"'}:
            quote = current
            output.append(" ")
            index += 1
            while index < length:
                output.append("\n" if query[index] in "\r\n" else " ")
                if query[index] == quote:
                    if index + 1 < length and query[index + 1] == quote:
                        output.append(" ")
                        index += 2
                        continue
                    index += 1
                    break
                index += 1
            continue

        if current == "$":
            delimiter_match = re.match(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$", query[index:])
            if delimiter_match:
                delimiter = delimiter_match.group(0)
                end = query.find(delimiter, index + len(delimiter))
                if end == -1:
                    output.extend(" " * (length - index))
                    break
                block_end = end + len(delimiter)
                output.extend(
                    "\n" if character in "\r\n" else " " for character in query[index:block_end]
                )
                index = block_end
                continue

        output.append(current)
        index += 1

    return "".join(output)


@observed_operation(
    "sql.validate",
    attributes={"db.operation.type": "select"},
    failure_when=lambda result: not result.is_safe,
)
def validate_read_only_sql(query: str) -> SQLSafetyResult:
    """Allow exactly one read-only SELECT statement (optionally using WITH)."""
    if not query or not query.strip():
        return SQLSafetyResult(False, "The generated SQL query is empty.")

    tokens = [
        match.group(0).upper()
        for match in _TOKEN_PATTERN.finditer(_strip_literals_and_comments(query))
    ]
    if not tokens:
        return SQLSafetyResult(False, "The generated SQL query contains no executable statement.")

    semicolons = [position for position, token in enumerate(tokens) if token == ";"]
    if len(semicolons) > 1 or (semicolons and semicolons[0] != len(tokens) - 1):
        return SQLSafetyResult(False, "Only one SQL statement may be executed.")

    statement_tokens = [token for token in tokens if token != ";"]
    if not statement_tokens or statement_tokens[0] not in {"SELECT", "WITH"}:
        return SQLSafetyResult(False, "Only SELECT queries are allowed.")

    forbidden = next(
        (token for token in statement_tokens if token in _WRITE_KEYWORDS),
        None,
    )
    if forbidden:
        return SQLSafetyResult(False, f"Forbidden SQL operation detected: {forbidden}.")

    denied_function = next(
        (token for token in statement_tokens if token in _DENIED_FUNCTIONS),
        None,
    )
    if denied_function:
        return SQLSafetyResult(False, f"Unsafe database function detected: {denied_function}.")

    if "INTO" in statement_tokens:
        return SQLSafetyResult(False, "SELECT INTO is not allowed.")

    for position, token in enumerate(statement_tokens[:-1]):
        if token == "FOR" and any(
            candidate in {"UPDATE", "SHARE"}
            for candidate in statement_tokens[position + 1 : position + 4]
        ):
            return SQLSafetyResult(False, "Row-locking SELECT queries are not allowed.")

    return SQLSafetyResult(True, "The query passed deterministic read-only validation.")
