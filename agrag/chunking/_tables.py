from collections.abc import Callable

from agrag.common.data_models.document import Unit


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("\\", "\\\\").replace("|", "\\|")


def _line(cells: list[str], width: int) -> str:
    padded = [*cells, *[""] * (width - len(cells))]
    return "| " + " | ".join(_cell(cell) for cell in padded) + " |"


def would_exceed(used: int, cost: int, size: int) -> bool:
    return used + cost > size


def table_texts(unit: Unit, size: int, count_tokens: Callable[[str], int]) -> list[str]:
    if not unit.rows:
        return []
    width = max(len(row) for row in unit.rows)
    head = [
        _line(unit.header, width),
        "| " + " | ".join(["---"] * width) + " |",
    ]
    body = [_line(row, width) for row in unit.rows[unit.header_row_count :]]

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
