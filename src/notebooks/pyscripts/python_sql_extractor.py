"""
Extract SQL statements from Python source code by parsing spark.sql() calls.

Uses AST analysis to find spark.sql() invocations, resolve simple variable
assignments, and handle f-strings and string concatenation. Unresolved
variables are replaced with _PLACEHOLDER_ so downstream marker detection
can flag them.
"""

import ast
from typing import List, Optional


class SparkSQLExtractor:
    """Extract SQL strings from spark.sql() calls in Python source code."""

    def __init__(self) -> None:
        self.sql_statements: List[str] = []
        self.variables: dict = {}

    def extract(self, source_code: str) -> List[str]:
        """Parse Python source and return extracted SQL strings.

        Raises ValueError on Python syntax errors.
        """
        tree = ast.parse(source_code)
        self.sql_statements = []
        self.variables = {}
        self._walk(tree)
        return [self._clean(sql) for sql in self.sql_statements]

    # ------------------------------------------------------------------
    # AST walking
    # ------------------------------------------------------------------

    def _walk(self, node: ast.AST) -> None:
        for child in ast.walk(node):
            if isinstance(child, ast.Assign):
                self._visit_assign(child)
            elif isinstance(child, ast.Call):
                self._visit_call(child)

    def _visit_assign(self, node: ast.Assign) -> None:
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            value = self._extract_value(node.value)
            if value is not None:
                self.variables[node.targets[0].id] = value

    def _visit_call(self, node: ast.Call) -> None:
        if not (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "sql"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "spark"
        ):
            return
        if len(node.args) != 1:
            return
        sql = self._extract_value(node.args[0])
        if sql is not None:
            self.sql_statements.append(sql)

    # ------------------------------------------------------------------
    # Value extraction
    # ------------------------------------------------------------------

    def _extract_value(self, node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.JoinedStr):
            return self._process_fstring(node)
        if isinstance(node, ast.Name):
            return self.variables.get(node.id, "_PLACEHOLDER_")
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left = self._extract_value(node.left)
            right = self._extract_value(node.right)
            if left is not None and right is not None:
                return left + right
        return None

    def _process_fstring(self, node: ast.JoinedStr) -> str:
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(str(value.value))
            elif isinstance(value, ast.FormattedValue):
                resolved = self._extract_value(value.value)
                parts.append(resolved if resolved is not None else "_PLACEHOLDER_")
            else:
                parts.append("_PLACEHOLDER_")
        return "".join(parts)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    @staticmethod
    def _clean(sql: str) -> str:
        """Normalise whitespace but keep the SQL otherwise intact."""
        return " ".join(sql.split())


def extract_sql_from_python(source_code: str) -> List[str]:
    """Public convenience function.

    Returns a list of SQL strings extracted from *source_code*.
    Raises ``ValueError`` on Python syntax errors.
    """
    if not source_code or not source_code.strip():
        return []
    try:
        extractor = SparkSQLExtractor()
        return extractor.extract(source_code)
    except SyntaxError as e:
        raise ValueError(f"Python syntax error: {e}") from e
