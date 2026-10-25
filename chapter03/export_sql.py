"""Export already-canonical source records into a standalone plain SQL script."""
import re

from foundations_lab import ContractError, Ledger, load_fixture
from historical_lab import Query
from sqlite_lab import SQL, SCHEMA, connect


# Skip SQL literals, quoted identifiers, and comments when finding parameters.
# Replacements are made in one pass over the original, trusted query template;
# parameter-looking text inside an inserted customer literal is never rescanned.
SQL_TOKENS = re.compile(
    r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|`(?:``|[^`])*`|\[[^\]]*\]"
    r"|--[^\n]*|/\*.*?\*/|:(?P<parameter>[A-Za-z_][\w$]*)",
    re.DOTALL,
)


def standalone_script(ledger: Ledger, query: Query) -> str:
    connection = connect(ledger, query)
    try:
        # SQLite quotes ordinary values, including embedded apostrophes.
        # quote(TEXT) truncates at NUL: preserve such strings as UTF-8 bytes
        # cast back to TEXT instead, for both source records and query values.
        def literal(value):
            if isinstance(value, str) and "\x00" in value:
                return "CAST(X'" + value.encode("utf-8").hex() + "' AS TEXT)"
            return connection.execute("SELECT quote(?)", (value,)).fetchone()[0]

        literals = {name: literal(value) for name, value in query.parameters().items()}

        def bind(match):
            name = match.group("parameter")
            if name is None:
                return match.group(0)
            if name not in literals:
                raise ContractError(f"standalone SQL template has undeclared parameter :{name}")
            return literals[name]

        statements = ["-- Canonical source versions validated by the unchanged foundation ledger.", SCHEMA]
        for row in ledger.history:
            values = (row.event_id, row.revision, row.customer_id, row.event_time,
                      row.available_at, row.amount, row.op)
            statements.append("INSERT INTO revisions VALUES (" + ", ".join(literal(v) for v in values) + ");")
        query_text = SQL_TOKENS.sub(bind, SQL)
        statements.append(query_text.rstrip())
        return "\n".join(statements) + "\n"
    finally:
        connection.close()


if __name__ == "__main__":
    print(standalone_script(load_fixture(), Query("C1", 540, 600, 600)), end="")
