"""
SQL utility functions for DDL validation.

This module provides functions for handling SQL comments properly,
which is essential for correct statement splitting and validation.
"""

from enum import Enum
from typing import Tuple


class CommentState(Enum):
    """State machine states for SQL comment parsing."""
    NORMAL = "normal"
    IN_BLOCK_COMMENT = "in_block_comment"
    IN_LINE_COMMENT = "in_line_comment"
    IN_STRING_SINGLE = "in_string_single"
    IN_STRING_DOUBLE = "in_string_double"


def remove_sql_comments(sql_text: str, preserve_line_count: bool = False) -> str:
    """
    Remove both block comments (/* ... */) and line comments (-- ...) from SQL text.

    This function uses a state machine approach to correctly handle:
    - Block comments that span multiple lines
    - Line comments (-- to end of line)
    - Nested comment-like patterns inside strings
    - Comment delimiters inside other comments (e.g., -- inside /* */)

    Args:
        sql_text: The SQL text to clean.
        preserve_line_count: If True, replace comments with spaces/newlines to
                            preserve line numbers for error reporting.

    Returns:
        The SQL text with comments removed.

    Examples:
        >>> remove_sql_comments("SELECT * FROM t -- comment")
        'SELECT * FROM t '
        >>> remove_sql_comments("SELECT /* comment */ * FROM t")
        'SELECT  * FROM t'
        >>> remove_sql_comments("/* multi\\nline */ SELECT")
        ' SELECT'
    """
    if not sql_text:
        return sql_text

    result = []
    state = CommentState.NORMAL
    i = 0
    n = len(sql_text)

    while i < n:
        char = sql_text[i]
        next_char = sql_text[i + 1] if i + 1 < n else ''

        if state == CommentState.NORMAL:
            if char == '/' and next_char == '*':
                # Start of block comment
                state = CommentState.IN_BLOCK_COMMENT
                if preserve_line_count:
                    result.append(' ')
                i += 2
                continue
            elif char == '-' and next_char == '-':
                # Start of line comment
                state = CommentState.IN_LINE_COMMENT
                i += 2
                continue
            elif char == "'":
                # Start of single-quoted string
                state = CommentState.IN_STRING_SINGLE
                result.append(char)
                i += 1
                continue
            elif char == '"':
                # Start of double-quoted string
                state = CommentState.IN_STRING_DOUBLE
                result.append(char)
                i += 1
                continue
            else:
                result.append(char)
                i += 1
                continue

        elif state == CommentState.IN_BLOCK_COMMENT:
            if char == '*' and next_char == '/':
                # End of block comment
                state = CommentState.NORMAL
                if preserve_line_count:
                    result.append(' ')
                i += 2
                continue
            elif char == '\n':
                # Preserve newlines in block comments for line count preservation
                if preserve_line_count:
                    result.append('\n')
                i += 1
                continue
            else:
                # Inside block comment, skip character
                if preserve_line_count:
                    result.append(' ' if char != '\n' else '\n')
                i += 1
                continue

        elif state == CommentState.IN_LINE_COMMENT:
            if char == '\n':
                # End of line comment
                state = CommentState.NORMAL
                result.append('\n')
                i += 1
                continue
            else:
                # Inside line comment, skip character
                i += 1
                continue

        elif state == CommentState.IN_STRING_SINGLE:
            if char == "'" and next_char == "'":
                # Escaped single quote
                result.append("''")
                i += 2
                continue
            elif char == "'":
                # End of single-quoted string
                state = CommentState.NORMAL
                result.append(char)
                i += 1
                continue
            else:
                result.append(char)
                i += 1
                continue

        elif state == CommentState.IN_STRING_DOUBLE:
            if char == '"' and next_char == '"':
                # Escaped double quote
                result.append('""')
                i += 2
                continue
            elif char == '"':
                # End of double-quoted string
                state = CommentState.NORMAL
                result.append(char)
                i += 1
                continue
            else:
                result.append(char)
                i += 1
                continue

    return ''.join(result)


def remove_sql_comments_preserve_lines(sql_text: str) -> Tuple[str, bool]:
    """
    Remove SQL comments while preserving line structure.

    This is useful for statement splitting where we need to match
    original line numbers with cleaned line numbers.

    Args:
        sql_text: The SQL text to clean.

    Returns:
        A tuple of (cleaned_text, has_unclosed_comment).
        has_unclosed_comment is True if there's an unclosed block comment.
    """
    cleaned = remove_sql_comments(sql_text, preserve_line_count=True)

    # Check for unclosed block comment by comparing states
    state = CommentState.NORMAL
    for i, char in enumerate(sql_text):
        next_char = sql_text[i + 1] if i + 1 < len(sql_text) else ''

        if state == CommentState.NORMAL:
            if char == '/' and next_char == '*':
                state = CommentState.IN_BLOCK_COMMENT
            elif char == "'":
                state = CommentState.IN_STRING_SINGLE
            elif char == '"':
                state = CommentState.IN_STRING_DOUBLE
        elif state == CommentState.IN_BLOCK_COMMENT:
            if char == '*' and next_char == '/':
                state = CommentState.NORMAL
        elif state == CommentState.IN_STRING_SINGLE:
            if char == "'" and next_char == "'":
                continue
            elif char == "'":
                state = CommentState.NORMAL
        elif state == CommentState.IN_STRING_DOUBLE:
            if char == '"' and next_char == '"':
                continue
            elif char == '"':
                state = CommentState.NORMAL

    has_unclosed = state == CommentState.IN_BLOCK_COMMENT
    return cleaned, has_unclosed


def split_sql_statements(content: str) -> list:
    """
    Split SQL content into individual statements by semicolon.

    This function properly handles:
    - Block comments (/* ... */) containing semicolons
    - Line comments (-- ...) containing semicolons
    - String literals containing semicolons
    - Multi-line statements

    The original SQL text (including comments) is preserved in the output.

    Args:
        content: The SQL content to split.

    Returns:
        A list of SQL statements (without trailing semicolons).
    """
    if not content:
        return []

    # Get cleaned version for semicolon detection
    clean_content = remove_sql_comments(content, preserve_line_count=True)

    statements = []
    current_stmt = []
    clean_lines = clean_content.split('\n')
    original_lines = content.split('\n')

    for i, line in enumerate(original_lines):
        current_stmt.append(line)
        clean_line = clean_lines[i] if i < len(clean_lines) else ''

        # Check if cleaned line ends with semicolon (outside comments/strings)
        if clean_line.rstrip().endswith(';'):
            stmt = '\n'.join(current_stmt).strip()
            # Remove trailing semicolon
            if stmt.endswith(';'):
                stmt = stmt[:-1].strip()
            # Skip if statement is only comments (nothing left after removing comments)
            stmt_cleaned = remove_sql_comments(stmt).strip()
            if stmt and stmt_cleaned:
                statements.append(stmt)
            current_stmt = []

    # Handle last statement (may not have semicolon)
    if current_stmt:
        stmt = '\n'.join(current_stmt).strip()
        if stmt.endswith(';'):
            stmt = stmt[:-1].strip()
        # Skip if statement is only comments
        stmt_cleaned = remove_sql_comments(stmt).strip()
        if stmt and stmt_cleaned:
            statements.append(stmt)

    return statements
