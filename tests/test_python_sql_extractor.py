"""Tests for python_sql_extractor module."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "notebooks" / "pyscripts"))

from python_sql_extractor import extract_sql_from_python


class TestBasicExtraction:
    """Basic spark.sql() extraction."""

    def test_simple_select(self):
        code = 'spark.sql("SELECT 1")'
        assert extract_sql_from_python(code) == ["SELECT 1"]

    def test_single_quoted(self):
        code = "spark.sql('SELECT 1')"
        assert extract_sql_from_python(code) == ["SELECT 1"]

    def test_multiline_string(self):
        code = '''spark.sql("""
            SELECT *
            FROM table1
            WHERE id = 1
        """)'''
        result = extract_sql_from_python(code)
        assert len(result) == 1
        assert "SELECT * FROM table1 WHERE id = 1" == result[0]

    def test_multiple_calls(self):
        code = '''
spark.sql("SELECT 1")
spark.sql("SELECT 2")
spark.sql("SELECT 3")
'''
        result = extract_sql_from_python(code)
        assert len(result) == 3
        assert result[0] == "SELECT 1"
        assert result[1] == "SELECT 2"
        assert result[2] == "SELECT 3"


class TestVariableResolution:
    """Variable assignment resolution."""

    def test_variable_reference(self):
        code = '''
query = "SELECT * FROM t"
spark.sql(query)
'''
        result = extract_sql_from_python(code)
        assert result == ["SELECT * FROM t"]

    def test_string_concatenation(self):
        code = '''
table = "my_table"
query = "SELECT * FROM " + table
spark.sql(query)
'''
        result = extract_sql_from_python(code)
        assert len(result) == 1
        assert result[0] == "SELECT * FROM my_table"

    def test_fstring(self):
        code = '''
table = "my_table"
spark.sql(f"SELECT * FROM {table}")
'''
        result = extract_sql_from_python(code)
        assert len(result) == 1
        assert result[0] == "SELECT * FROM my_table"

    def test_unresolved_variable(self):
        code = '''
spark.sql(unknown_var)
'''
        result = extract_sql_from_python(code)
        assert len(result) == 1
        assert "_PLACEHOLDER_" in result[0]

    def test_unresolved_fstring_variable(self):
        code = '''
spark.sql(f"SELECT * FROM {unknown_table}")
'''
        result = extract_sql_from_python(code)
        assert len(result) == 1
        assert "_PLACEHOLDER_" in result[0]


class TestEdgeCases:
    """Edge cases and error handling."""

    def test_no_spark_sql(self):
        code = '''
x = 1 + 2
print("hello")
'''
        assert extract_sql_from_python(code) == []

    def test_empty_string(self):
        assert extract_sql_from_python("") == []

    def test_whitespace_only(self):
        assert extract_sql_from_python("   \n\n  ") == []

    def test_python_syntax_error(self):
        code = "def foo(:\n  pass"
        with pytest.raises(ValueError, match="Python syntax error"):
            extract_sql_from_python(code)

    def test_non_spark_sql_call(self):
        """Other .sql() calls should be ignored."""
        code = '''
conn.sql("SELECT 1")
df.sql("SELECT 2")
'''
        assert extract_sql_from_python(code) == []

    def test_spark_sql_no_args(self):
        """spark.sql() with no arguments should be skipped."""
        code = "spark.sql()"
        assert extract_sql_from_python(code) == []

    def test_spark_sql_multiple_args(self):
        """spark.sql() with multiple args should be skipped."""
        code = 'spark.sql("SELECT 1", "extra")'
        assert extract_sql_from_python(code) == []

    def test_numeric_arg(self):
        """spark.sql() with non-string constant should be skipped."""
        code = "spark.sql(123)"
        assert extract_sql_from_python(code) == []

    def test_mixed_content(self):
        """File with both spark.sql() and other code."""
        code = '''
import os

table_name = "users"
df = spark.read.table(table_name)

spark.sql(f"DROP TABLE IF EXISTS {table_name}")

result = df.count()
print(result)

spark.sql("CREATE TABLE test (id INT)")
'''
        result = extract_sql_from_python(code)
        assert len(result) == 2
        assert "DROP TABLE IF EXISTS users" == result[0]
        assert "CREATE TABLE test (id INT)" == result[1]
