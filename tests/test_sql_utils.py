"""
Tests for SQL utility functions.

These tests verify the correct handling of SQL comments,
which is critical for statement splitting in DDL validation.
"""

import pytest
import sys
from pathlib import Path

# Add src path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "notebooks" / "pyscripts"))

from sql_utils import (
    CommentState,
    remove_sql_comments,
    remove_sql_comments_preserve_lines,
    split_sql_statements,
)


class TestRemoveSqlComments:
    """Tests for remove_sql_comments function."""

    def test_empty_string(self):
        """Empty input should return empty string."""
        assert remove_sql_comments("") == ""
        assert remove_sql_comments(None) is None

    def test_no_comments(self):
        """SQL without comments should be unchanged."""
        sql = "SELECT * FROM table1"
        assert remove_sql_comments(sql) == sql

    def test_line_comment_basic(self):
        """Basic line comment removal."""
        sql = "SELECT * FROM t -- this is a comment"
        result = remove_sql_comments(sql)
        assert result == "SELECT * FROM t "

    def test_line_comment_at_end(self):
        """Line comment at end of statement."""
        sql = "SELECT 1; -- comment"
        result = remove_sql_comments(sql)
        assert result == "SELECT 1; "

    def test_line_comment_multiple_lines(self):
        """Multiple line comments on separate lines."""
        sql = """SELECT * -- comment 1
FROM t -- comment 2
WHERE x = 1"""
        result = remove_sql_comments(sql)
        # Line comments are removed but trailing space before comment remains
        assert "comment 1" not in result
        assert "comment 2" not in result
        assert "SELECT *" in result
        assert "FROM t" in result
        assert "WHERE x = 1" in result

    def test_block_comment_inline(self):
        """Inline block comment removal."""
        sql = "SELECT /* comment */ * FROM t"
        result = remove_sql_comments(sql)
        assert result == "SELECT  * FROM t"

    def test_block_comment_multiline(self):
        """Multi-line block comment removal."""
        sql = """SELECT /*
multi
line
comment
*/ * FROM t"""
        result = remove_sql_comments(sql)
        assert result == "SELECT  * FROM t"

    def test_block_comment_multiline_preserve_lines(self):
        """Multi-line block comment with line preservation."""
        sql = """SELECT /*
multi
line
*/ * FROM t"""
        result = remove_sql_comments(sql, preserve_line_count=True)
        # Should have same number of lines
        assert result.count('\n') == sql.count('\n')

    def test_header_comment_with_dashes(self):
        """
        Header comment pattern with dashes inside block comment.

        This is a critical test case: The closing pattern
        `- ---------------------------------------------------------------*/`
        contains `--` but it should NOT be treated as a line comment
        because it's inside a block comment.
        """
        sql = """/*----------------------------------------------------------------
# FILE_NAME     :  sample_view.sql
# FUNCTION      :  Create View SQL script for sample data
- ---------------------------------------------------------------*/

CREATE OR REPLACE VIEW test_view"""
        result = remove_sql_comments(sql)
        # The block comment should be completely removed
        assert "/*" not in result
        assert "*/" not in result
        assert "FILE_NAME" not in result
        assert "CREATE OR REPLACE VIEW test_view" in result

    def test_mixed_comments(self):
        """Mix of block and line comments."""
        sql = """SELECT /* block */ a, -- line comment
b /* another block */
FROM t"""
        result = remove_sql_comments(sql)
        # Comments removed, trailing spaces may remain
        assert "/* block */" not in result
        assert "line comment" not in result
        assert "/* another block */" not in result
        assert "SELECT" in result
        assert "FROM t" in result

    def test_double_dash_inside_block_comment(self):
        """Double dash inside block comment should not start line comment."""
        sql = "/* comment -- with dashes */ SELECT 1"
        result = remove_sql_comments(sql)
        assert result == " SELECT 1"

    def test_block_markers_inside_line_comment(self):
        """Block comment markers inside line comment should be ignored."""
        sql = "SELECT 1 -- /* this is not a block comment */"
        result = remove_sql_comments(sql)
        assert result == "SELECT 1 "

    def test_string_with_comment_markers_single_quote(self):
        """Comment markers inside single-quoted strings should be preserved."""
        sql = "SELECT '/* not a comment */' FROM t"
        result = remove_sql_comments(sql)
        assert result == sql

    def test_string_with_comment_markers_double_quote(self):
        """Comment markers inside double-quoted strings should be preserved."""
        sql = 'SELECT "-- not a comment" FROM t'
        result = remove_sql_comments(sql)
        assert result == sql

    def test_escaped_single_quote(self):
        """Escaped single quotes should be handled correctly."""
        sql = "SELECT 'it''s -- a test' FROM t"
        result = remove_sql_comments(sql)
        assert result == sql

    def test_escaped_double_quote(self):
        """Escaped double quotes should be handled correctly."""
        sql = 'SELECT "test""value -- here" FROM t'
        result = remove_sql_comments(sql)
        assert result == sql

    def test_number_marker_comments(self):
        """Number marker comments like /* 10 */ should be removed."""
        sql = """SELECT
  col1
/* 10 */
  , col2
  , col3"""
        result = remove_sql_comments(sql)
        assert "/* 10 */" not in result
        assert "col1" in result
        assert "col2" in result

    def test_inline_comment_after_column(self):
        """Inline block comment after column definition."""
        sql = "  , customer_id       /* Customer ID column      */"
        result = remove_sql_comments(sql)
        assert result == "  , customer_id       "
        assert "Customer ID" not in result


class TestRemoveSqlCommentsPreserveLines:
    """Tests for remove_sql_comments_preserve_lines function."""

    def test_line_count_preserved(self):
        """Line count should be preserved after comment removal."""
        sql = """SELECT /*
comment
here
*/ * FROM t"""
        result, has_unclosed = remove_sql_comments_preserve_lines(sql)
        assert result.count('\n') == sql.count('\n')
        assert not has_unclosed

    def test_unclosed_block_comment(self):
        """Should detect unclosed block comments."""
        sql = "SELECT /* unclosed comment"
        result, has_unclosed = remove_sql_comments_preserve_lines(sql)
        assert has_unclosed

    def test_closed_block_comment(self):
        """Should not flag properly closed comments."""
        sql = "SELECT /* closed */ * FROM t"
        result, has_unclosed = remove_sql_comments_preserve_lines(sql)
        assert not has_unclosed


class TestSplitSqlStatements:
    """Tests for split_sql_statements function."""

    def test_empty_content(self):
        """Empty content should return empty list."""
        assert split_sql_statements("") == []
        assert split_sql_statements(None) == []

    def test_single_statement_with_semicolon(self):
        """Single statement with trailing semicolon."""
        sql = "SELECT * FROM t;"
        result = split_sql_statements(sql)
        assert len(result) == 1
        assert result[0] == "SELECT * FROM t"

    def test_single_statement_without_semicolon(self):
        """Single statement without trailing semicolon."""
        sql = "SELECT * FROM t"
        result = split_sql_statements(sql)
        assert len(result) == 1
        assert result[0] == "SELECT * FROM t"

    def test_multiple_statements(self):
        """Multiple statements separated by semicolons."""
        sql = """SELECT 1;
SELECT 2;
SELECT 3;"""
        result = split_sql_statements(sql)
        assert len(result) == 3
        assert result[0] == "SELECT 1"
        assert result[1] == "SELECT 2"
        assert result[2] == "SELECT 3"

    def test_semicolon_in_string(self):
        """Semicolon inside string should not split statement."""
        # Note: split_sql_statements works line-by-line, so multiple
        # statements on a single line will be kept together
        sql = """SELECT 'a;b' FROM t;
SELECT 2;"""
        result = split_sql_statements(sql)
        assert len(result) == 2
        assert "a;b" in result[0]

    def test_semicolon_in_block_comment(self):
        """Semicolon inside block comment should not split statement."""
        sql = """SELECT /* comment; with semicolon */ 1;
SELECT 2;"""
        result = split_sql_statements(sql)
        assert len(result) == 2

    def test_semicolon_in_line_comment(self):
        """Semicolon inside line comment should not split statement."""
        sql = """SELECT 1 -- comment; here
;
SELECT 2;"""
        result = split_sql_statements(sql)
        assert len(result) == 2

    def test_multiline_statement(self):
        """Multi-line statement should be kept together."""
        sql = """SELECT
    col1,
    col2
FROM
    table1;"""
        result = split_sql_statements(sql)
        assert len(result) == 1
        assert "col1" in result[0]
        assert "col2" in result[0]

    def test_create_view_with_header_comment(self):
        """
        CREATE VIEW statement with header comment block.

        This tests a real-world pattern where the header comment
        contains dashes that look like line comments but are
        inside a block comment.
        """
        sql = """/*----------------------------------------------------------------
# FILE_NAME     :  sample_view.sql
- ---------------------------------------------------------------*/

CREATE OR REPLACE VIEW test_schema.test_view
  (
    col1
  , col2
  )
AS
SELECT
    a,
    b
FROM source_table
;"""
        result = split_sql_statements(sql)
        assert len(result) == 1
        # The statement should include the header comment
        assert "CREATE OR REPLACE VIEW" in result[0]

    def test_preserve_original_comments(self):
        """Original comments should be preserved in output."""
        sql = """SELECT /* keep this */ 1;"""
        result = split_sql_statements(sql)
        assert len(result) == 1
        assert "/* keep this */" in result[0]


class TestRealWorldPatterns:
    """Tests with real-world SQL patterns."""

    def test_file_header_pattern(self):
        """
        Test the file header pattern commonly used in SQL files.

        The key issue is that the closing line:
        `- ---------------------------------------------------------------*/`
        contains `--` but it's inside the block comment.
        """
        header = """/*----------------------------------------------------------------
# FILE_NAME     :  sample_view.sql
# FUNCTION      :  Create View SQL script for sample data
# INPUT         :  source_table
# OUTPUT        :  target_view
# CREATED BY    :  developer
# DATE CREATED  :  2024/01/01
# MODIFIED BY   :
# DATE MODIFIED :
- ---------------------------------------------------------------*/"""

        result = remove_sql_comments(header)
        # All content should be removed (only whitespace remains)
        assert result.strip() == ""
        assert "/*" not in result
        assert "*/" not in result

    def test_view_with_column_comments(self):
        """Test a view definition with inline comments for each column."""
        sql = """/*----------------------------------------------------------------
# FILE_NAME     :  sample_view.sql
- ---------------------------------------------------------------*/

CREATE OR REPLACE VIEW schema1.sample_view    /* schema1.sample_view */
  (
    file_date         /* File date column            */
  , customer_id       /* Customer ID                 */
/* 10 */
  , balance           /* Account balance             */
  )

AS

SELECT
   /* File date column            */
     T1.file_date
   /* Customer ID                 */
   , T1.customer_id
/* 10 */
   , SUM ( T1.amount )

FROM
  schema2.source_table AS T1

GROUP BY
    T1.file_date
  , T1.customer_id
;"""

        # Test comment removal
        cleaned = remove_sql_comments(sql)
        assert "/*" not in cleaned
        assert "*/" not in cleaned
        assert "File date column" not in cleaned
        assert "CREATE OR REPLACE VIEW" in cleaned
        assert "T1.file_date" in cleaned

        # Test statement splitting
        statements = split_sql_statements(sql)
        assert len(statements) == 1
        # Original comments should be preserved in the statement
        assert "/* File date column" in statements[0]

    def test_consecutive_block_comments(self):
        """Multiple consecutive block comments."""
        sql = "/* comment 1 */ /* comment 2 */ SELECT 1"
        result = remove_sql_comments(sql)
        assert result == "  SELECT 1"

    def test_nested_like_pattern(self):
        """Pattern that looks nested but isn't (SQL doesn't support nested comments)."""
        sql = "/* outer /* inner */ SELECT 1"
        result = remove_sql_comments(sql)
        # First */ ends the comment
        assert result == " SELECT 1"

    def test_dash_separator_line_inside_block(self):
        """Dash separator line that looks like multiple line comments."""
        sql = """/*
------------------------------------------------------------
  Section Header
------------------------------------------------------------
*/
SELECT 1"""
        result = remove_sql_comments(sql)
        assert "---" not in result
        assert "Section Header" not in result
        assert "SELECT 1" in result
