"""Table chunks: a whole table, or row groups that each repeat the header."""

from collections.abc import Callable

from agrag.common.data_models.document import Unit


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("\\", "\\\\").replace("|", "\\|")


def _header_names(unit: Unit) -> list[str]:
    """Return one column name per column from the header rows of a table."""
    if not unit.rows:
        return []
    width = max(len(row) for row in unit.rows)
    head = unit.rows[: max(unit.header_rows, 1)]
    names: list[str] = []
    for column in range(width):
        parts = [
            row[column] for row in head if column < len(row) and row[column].strip()
        ]
        names.append(" ".join(dict.fromkeys(parts)))
    return names


def _line(cells: list[str], width: int) -> str:
    padded = [*cells, *[""] * (width - len(cells))]
    return "| " + " | ".join(_cell(cell) for cell in padded) + " |"


def would_exceed(used: int, cost: int, size: int) -> bool:
    """Return whether one more piece would pass the size.

    Args:
        used: The tokens already packed in the open chunk or row group.
        cost: The tokens the next piece adds, separators included.
        size: The most tokens in a chunk.

    Returns:
        True when packing the piece would pass ``size``.
    """
    return used + cost > size


def table_texts(unit: Unit, size: int, count_tokens: Callable[[str], int]) -> list[str]:
    """Return the chunk texts of a table.

    The table is one Markdown table when it fits in ``size`` tokens. A larger table
    becomes row groups. Every group repeats the header, and the first group starts
    with the caption. A row that is over ``size`` on its own becomes its own group.

    Args:
        unit: A table unit. The first row is the header when the loader marked no
            header rows.
        size: The most tokens in a chunk.
        count_tokens: Returns the number of tokens in a text.

    Returns:
        The chunk texts in row order. Empty when the table has no rows.
    """
    if not unit.rows:
        return []
    head_count = max(unit.header_rows, 1)
    width = max(len(row) for row in unit.rows)
    head = [
        _line(_header_names(unit), width),
        "| " + " | ".join(["---"] * width) + " |",
    ]
    body = [_line(row, width) for row in unit.rows[head_count:]]

    def render(lines: list[str], first: bool) -> str:
        caption = [unit.caption] if first and unit.caption else []
        return "\n".join([*caption, *head, *lines])

    whole = render(body, True)
    if len(body) <= 1 or count_tokens(whole) <= size:
        return [whole]
    groups: list[list[str]] = [[]]
    for line in body:
        first = len(groups) == 1
        if groups[-1] and count_tokens(render([*groups[-1], line], first)) > size:
            groups.append([])
        groups[-1].append(line)
    return [render(group, i == 0) for i, group in enumerate(groups)]
