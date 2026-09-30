"""Give generated API pages stable heading ids and working cross-page links."""

from __future__ import annotations

import re
import sys
from pathlib import Path


HEADING = re.compile(
    r"^(#{2,6}) `(agrag[\w.]*)`(?: \\?\{#[\w-]*\})?[ \t]*$", re.MULTILINE
)
LINK = re.compile(r"\[([^\]]+)\]\(#([^)\s]+)\)")


def anchor_id(name: str) -> str:
    """Return the heading id for a dotted name; ids cannot contain dots."""
    return name.replace(".", "-")


def rewrite(pages: dict[str, str]) -> dict[str, str]:
    """Rewrite each page so every link to a documented name resolves.

    griffe2md emits same-page fragment links for every name, but Docusaurus
    ids never match them. This gives each heading an explicit, MDX-escaped
    id (dots become hyphens, since ids cannot contain dots), points links at
    the page that owns the name, and drops links to names with no page
    (builtins, other libraries, undocumented modules), keeping their text.

    Args:
        pages: Page text keyed by page name (file stem).

    Returns:
        The rewritten text, keyed the same way.
    """
    owner = {
        anchor_id(m[2]): name
        for name, text in pages.items()
        for m in HEADING.finditer(text)
    }

    def rewrite_page(name: str, text: str) -> str:
        def link(match: re.Match[str]) -> str:
            label, target = match.groups()
            anchor = anchor_id(target)
            page = owner.get(anchor)
            if page is None:
                return label
            if page == name:
                return f"[{label}](#{anchor})"
            return f"[{label}]({page}.md#{anchor})"

        text = HEADING.sub(lambda m: f"{m[1]} `{m[2]}` \\{{#{anchor_id(m[2])}}}", text)
        return LINK.sub(link, text)

    return {name: rewrite_page(name, text) for name, text in pages.items()}


def main(api_dir: str) -> int:
    """Rewrite every generated page in ``api_dir``, leaving ``index.md`` alone."""
    paths = [p for p in sorted(Path(api_dir).glob("*.md")) if p.name != "index.md"]
    pages = rewrite({p.stem: p.read_text() for p in paths})
    for path in paths:
        path.write_text(pages[path.stem])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
