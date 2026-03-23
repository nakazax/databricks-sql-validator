"""Tests for marker_detector module."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "notebooks" / "pyscripts"))

from marker_detector import detect_markers


class TestTemplateVars:
    """@VAR@ template variable detection."""

    def test_single_var(self):
        result = detect_markers("SELECT * FROM @TBL@")
        assert result is not None
        assert "template_var" in result
        assert "@TBL@" in result

    def test_multiple_vars(self):
        result = detect_markers("SELECT @COL@ FROM @TBL@")
        assert "@COL@" in result
        assert "@TBL@" in result

    def test_duplicate_vars(self):
        result = detect_markers("SELECT @TBL@.a, @TBL@.b FROM @TBL@")
        # Should deduplicate
        assert result.count("@TBL@") == 1


class TestNamedParams:
    """Named parameter (:param) detection."""

    def test_single_param(self):
        result = detect_markers("SELECT * FROM t WHERE id = :user_id")
        assert result is not None
        assert "named_param" in result
        assert ":user_id" in result

    def test_double_colon_not_matched(self):
        """PostgreSQL-style ::int cast should not be detected as named param."""
        result = detect_markers("SELECT col::int FROM t")
        assert result is None

    def test_multiple_params(self):
        result = detect_markers("SELECT * FROM t WHERE a = :x AND b = :y")
        assert ":x" in result
        assert ":y" in result


class TestPositionalParams:
    """Positional parameter (?) detection."""

    def test_single_question_mark(self):
        result = detect_markers("SELECT * FROM t WHERE id = ?")
        assert result is not None
        assert "positional" in result

    def test_multiple_question_marks(self):
        result = detect_markers("SELECT * FROM t WHERE a = ? AND b = ?")
        assert "x2" in result


class TestWidgets:
    """Databricks widget (${var}) detection."""

    def test_widget(self):
        result = detect_markers("SELECT * FROM ${catalog}.${schema}.t")
        assert result is not None
        assert "widget" in result
        assert "${catalog}" in result
        assert "${schema}" in result


class TestJinja:
    """Jinja template ({{ var }}) detection."""

    def test_jinja_var(self):
        result = detect_markers("SELECT * FROM {{ table_name }}")
        assert result is not None
        assert "jinja" in result

    def test_jinja_no_spaces(self):
        result = detect_markers("SELECT * FROM {{table_name}}")
        assert result is not None
        assert "jinja" in result


class TestPlaceholder:
    """_PLACEHOLDER_ detection (from python extractor)."""

    def test_placeholder(self):
        result = detect_markers("SELECT * FROM _PLACEHOLDER_")
        assert result is not None
        assert "placeholder" in result
        assert "_PLACEHOLDER_" in result

    def test_multiple_placeholders(self):
        result = detect_markers("SELECT _PLACEHOLDER_ FROM _PLACEHOLDER_")
        assert "x2" in result


class TestCleanSQL:
    """SQL without any markers."""

    def test_plain_sql(self):
        assert detect_markers("SELECT 1") is None

    def test_normal_query(self):
        assert detect_markers("SELECT * FROM catalog.schema.table WHERE id = 1") is None

    def test_empty(self):
        assert detect_markers("") is None

    def test_none(self):
        assert detect_markers(None) is None


class TestMultipleMarkerTypes:
    """SQL with multiple marker types."""

    def test_template_and_named(self):
        result = detect_markers("SELECT * FROM @TBL@ WHERE id = :user_id")
        assert "template_var" in result
        assert "named_param" in result

    def test_all_types(self):
        sql = "SELECT @COL@ FROM {{ tbl }} WHERE a = :x AND b = ? AND c = ${w} AND d = _PLACEHOLDER_"
        result = detect_markers(sql)
        assert "template_var" in result
        assert "named_param" in result
        assert "positional" in result
        assert "widget" in result
        assert "jinja" in result
        assert "placeholder" in result
