"""Split generated API pages by object and give them ids, links, and valid HTML."""

from __future__ import annotations

import posixpath
import re
import sys
from pathlib import Path


HEADING = re.compile(
    r"^(#{1,6}) `(agrag[\w.]*)`(?: \\?\{#[\w-]*\})?[ \t]*$", re.MULTILINE
)
LINK = re.compile(r"\[([^\]]+)\]\(#([^)\s]+)\)")
# griffe2md writes admonitions as <details class="note" markdown="1">. The docs site
# adds its own class to <details>, so a second class attribute breaks the HTML.
DETAILS = re.compile(r'<details class="[^"]*"( open)? markdown="1">')


def anchor_id(name: str) -> str:
    """Return the heading id for a dotted name; ids cannot contain dots."""
    return name.replace(".", "-")


SECTION = re.compile(r"^(#{2,6}) `(agrag[\w.]*)`")
SUBMODULE = re.compile(r"^- \[\*\*\w+\*\*\]\(#([\w.-]+)\)")


class _Node:
    """One heading of a generated page with the lines up to its first child."""

    def __init__(self, level: int, name: str, line: str) -> None:
        self.level = level
        self.name = name
        self.lines = [line]
        self.children: list[_Node] = []

    def all_lines(self) -> list[str]:
        """Return this node's lines followed by those of every descendant."""
        return self.lines + [x for c in self.children for x in c.all_lines()]


def _demote(lines: list[str], by: int) -> str:
    """Join lines, moving every heading outside code fences up by ``by`` levels."""
    out, in_fence = [], False
    for line in lines:
        if line.startswith("```"):
            in_fence = not in_fence
        heading = by and not in_fence and re.match(r"#{2,6} ", line)
        out.append(line[by:] if heading else line)
    return "\n".join(out).rstrip() + "\n"


def _emit(
    out: dict[str, str],
    node: _Node,
    folder: str,
    head: list[str],
    modules: set[str],
) -> None:
    """Write the pages of ``node`` and its descendants into ``out``."""
    taken = {node.name.rsplit(".", 1)[-1].lower()} | {
        c.name.rsplit(".", 1)[-1].lower()
        for c in node.children
        if anchor_id(c.name) in modules
    }
    for child in node.children:
        short = child.name.rsplit(".", 1)[-1]
        if anchor_id(child.name) in modules:
            _emit(out, child, f"{folder}/{short}", _front(child.name, short), modules)
            continue
        # Routes ignore case, and a page named like its folder becomes the
        # folder index. An object named like the folder or a sibling
        # module gets a suffix to avoid both.
        stem = f"{short}-ref" if short.lower() in taken else short
        out[f"{folder}/{stem}"] = _demote(
            _front(child.name, short) + [""] + child.all_lines(),
            child.level - 1,
        )
    out[f"{folder}/index"] = _demote(
        head + [""] * bool(head) + node.lines, node.level - 1
    )


def split(pages: dict[str, str]) -> dict[str, str]:
    """Split each package page into one page per module, class, and function.

    griffe2md writes a package as one long page. The result is a folder per
    module whose ``index`` holds the module summary. Each class or function
    gets its own page in that folder, titled by the object, with its members
    as headings. Each submodule gets a folder of its own.

    Args:
        pages: Package page text keyed by package name (file stem).

    Returns:
        Page text keyed by path without extension, such as ``pkg/index``,
        ``pkg/Name``, or ``pkg/submodule/index``.
    """
    out: dict[str, str] = {}
    for package, text in pages.items():
        front: list[str] = []
        root: _Node | None = None
        stack: list[_Node] = []
        modules: set[str] = set()
        in_fence = in_modules = False
        for line in text.splitlines():
            if line.startswith("```"):
                in_fence = not in_fence
            if not in_fence and line.startswith("**"):
                in_modules = line == "**Modules:**"
            match = SUBMODULE.match(line) if in_modules and not in_fence else None
            if match:
                modules.add(anchor_id(match[1]))
            heading = None if in_fence else SECTION.match(line)
            if heading is None:
                (stack[-1].lines if stack else front).append(line)
                continue
            node = _Node(len(heading[1]), heading[2], line)
            while stack and stack[-1].level >= node.level:
                stack.pop()
            if stack:
                stack[-1].children.append(node)
            else:
                root = node
            stack.append(node)
        if root is None:
            continue

        _emit(out, root, package, front, modules)
    return out


def _front(name: str, label: str) -> list[str]:
    """Return the front matter lines for a generated page."""
    return ["---", f"title: {name}", f"sidebar_label: {label}", "---"]


def rewrite(pages: dict[str, str]) -> dict[str, str]:
    """Rewrite each page so every link to a documented name resolves.

    griffe2md emits same-page fragment links for every name, but Docusaurus
    ids never match them. This gives each heading an explicit, MDX-escaped
    id (dots become hyphens, since ids cannot contain dots), points links at
    the page that owns the name, and drops links to names with no page
    (builtins, other libraries, undocumented modules), keeping their text.
    It also drops the class and markdown attributes that griffe2md puts on
    ``<details>`` blocks.

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

    # Docusaurus gives the page title no id, so a link to one targets the page.
    titles = {
        anchor_id(m[2])
        for text in pages.values()
        for m in HEADING.finditer(text)
        if m[1] == "#"
    }

    def rewrite_page(name: str, text: str) -> str:
        def link(match: re.Match[str]) -> str:
            label, target = match.groups()
            anchor = anchor_id(target)
            page = owner.get(anchor)
            if page is None:
                return label
            if page == name:
                return label if anchor in titles else f"[{label}](#{anchor})"
            path = posixpath.relpath(f"{page}.md", posixpath.dirname(name) or ".")
            return (
                f"[{label}]({path})"
                if anchor in titles
                else f"[{label}]({path}#{anchor})"
            )

        text = HEADING.sub(lambda m: f"{m[1]} `{m[2]}` \\{{#{anchor_id(m[2])}}}", text)
        return DETAILS.sub(lambda m: f"<details{m[1] or ''}>", LINK.sub(link, text))

    return {name: rewrite_page(name, text) for name, text in pages.items()}


def shorten(pages: dict[str, str]) -> dict[str, str]:
    """Show only the last name segment in each heading below the page title.

    The page title keeps the full dotted name. The heading id keeps it too, so
    links still resolve.
    """
    return {
        key: HEADING.sub(
            lambda m: (
                m[0] if m[1] == "#" else m[0].replace(m[2], m[2].rsplit(".", 1)[-1], 1)
            ),
            text,
        )
        for key, text in pages.items()
    }


def main(api_dir: str) -> int:
    """Split every generated module page in ``api_dir`` and rewrite the results.

    The hand-written top-level ``index.md`` stays as it is.
    """
    root = Path(api_dir)
    paths = [p for p in sorted(root.glob("*.md")) if p.name != "index.md"]
    pages = shorten(rewrite(split({p.stem: p.read_text() for p in paths})))
    for path in paths:
        path.unlink()
    for key, text in pages.items():
        target = root / f"{key}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
