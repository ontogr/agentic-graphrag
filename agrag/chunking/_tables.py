"""Table chunks: a whole table, or row groups that each repeat the header."""

from collections.abc import Callable

from agrag.common.data_models.document import Unit


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


def _line(cells: list[str], width: int) -> str:
    padded = [*cells, *[""] * (width - len(cells))]
    return "| " + " | ".join(_cell(cell) for cell in padded) + " |"


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
        _line(unit.header, width),
        "| " + " | ".join(["---"] * width) + " |",
    ]
    body = [_line(row, width) for row in unit.rows[head_count:]]

    def render(lines: list[str], first: bool) -> str:
        caption = [unit.caption] if first and unit.caption else []
        return "\n".join([*caption, *head, *lines])

    whole = render(body, True)
    if len(body) <= 1 or count_tokens(whole) <= size:
        return [whole]
    later_base = count_tokens(render([], False))
    groups: list[list[str]] = [[]]
    used = count_tokens(render([], True))
    for line in body:
        cost = count_tokens(line) + 1
        if groups[-1] and used + cost > size:
            groups.append([])
            used = later_base
        groups[-1].append(line)
        used += cost
    return [render(group, i == 0) for i, group in enumerate(groups)]
