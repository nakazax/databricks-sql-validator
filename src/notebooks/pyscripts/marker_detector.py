"""
Detect parameter markers and template variables in SQL text.

Returns a human-readable string describing the markers found, or None
if none are present.  Downstream consumers can use the non-None value
to distinguish marker-caused validation failures from real syntax errors.
"""

import re
from typing import List, Optional, Tuple

MARKER_PATTERNS: List[Tuple[str, "re.Pattern[str]"]] = [
    ("template_var", re.compile(r"@([A-Za-z0-9_]+)@")),
    ("named_param", re.compile(r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)")),
    ("positional", re.compile(r"\?")),
    ("widget", re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_.]*)\}")),
    ("jinja", re.compile(r"\{\{[\s]*[\w.]+[\s]*\}\}")),
    ("placeholder", re.compile(r"_PLACEHOLDER_")),
]


def detect_markers(sql_text: str) -> Optional[str]:
    """Return a description string of detected markers, or None if clean.

    Examples:
        >>> detect_markers("SELECT @TBL@.col FROM @TBL@")
        'template_var: @TBL@'
        >>> detect_markers("SELECT * FROM t WHERE id = :user_id")
        'named_param: :user_id'
        >>> detect_markers("SELECT 1")
        # returns None
    """
    if not sql_text:
        return None

    findings: List[str] = []

    for kind, pattern in MARKER_PATTERNS:
        matches = pattern.findall(sql_text)
        if not matches:
            continue

        if kind == "template_var":
            tokens = sorted(set(f"@{m}@" for m in matches))
            findings.append(f"template_var: {', '.join(tokens)}")
        elif kind == "named_param":
            tokens = sorted(set(f":{m}" for m in matches))
            findings.append(f"named_param: {', '.join(tokens)}")
        elif kind == "positional":
            findings.append(f"positional: ? (x{len(matches)})")
        elif kind == "widget":
            tokens = sorted(set(f"${{{m}}}" for m in matches))
            findings.append(f"widget: {', '.join(tokens)}")
        elif kind == "jinja":
            tokens = sorted(set(matches))
            findings.append(f"jinja: {', '.join(tokens)}")
        elif kind == "placeholder":
            findings.append(f"placeholder: _PLACEHOLDER_ (x{len(matches)})")

    return "; ".join(findings) if findings else None
