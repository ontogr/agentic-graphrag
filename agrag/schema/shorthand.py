"""Readers that turn every accepted notation into canonical dicts."""

import difflib
import re
from collections.abc import Mapping, Sequence
from typing import Any, NamedTuple

from agrag.common.data_models.graph_schema import (
    EntityType,
    GraphSchema,
    PropertySpec,
    RelationType,
)
from agrag.schema.errors import Issues


JsonObject = dict[str, Any]

# The model's own fields come first, so a field that the model gains is
# accepted here without an edit.
TOP_LEVEL_KEYS = (*GraphSchema.model_fields, "extends", "exclude")
ENTITY_KEYS = (*EntityType.model_fields, "override")
PROPERTY_KEYS = tuple(PropertySpec.model_fields)
RELATION_KEYS = (*RelationType.model_fields, "add_patterns", "override")

DEFAULT_PROPERTY_TYPE = "string"

# Names that belong to ExtractionSettings. The first group is the settings
# fields; the second holds the names users are likely to try.
_SETTING_KEYS = frozenset(
    {
        "mode",
        "model_name",
        "dtype",
        "entity_threshold",
        "relation_threshold",
        "relation_floor",
        "band_floor",
        "label_thresholds",
        "escalation_threshold",
        "escalation_budget",
        "min_escalation_words",
        "candidates_enabled",
        "model",
        "threshold",
        "thresholds",
        "settings",
    }
)

_RELATION_RE = re.compile(
    r"^\s*(?P<source>[^-]+?)\s*-\s*(?P<label>[^-\s>]+)\s*->\s*(?P<target>.+?)\s*$"
)
_PATTERN_RE = re.compile(r"^\s*(?P<source>[^-]+?)\s*->\s*(?P<target>.+?)\s*$")
_RELATION_LABEL_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class Draft(NamedTuple):
    """A type read from a source, with the path it was read from.

    Attributes:
        path: The path of the item in the source, for error messages.
        body: The canonical dict for the item. It may hold ``override`` and,
            for a relation, ``add_patterns``.
    """

    path: str
    body: JsonObject


def join_path(path: str, key: str) -> str:
    """Append a key to a path."""
    return f"{path}.{key}" if path else key


def describe(value: object) -> str:
    """Name the type of a value for an error message."""
    return "null" if value is None else type(value).__name__


def read_text(value: object, path: str, issues: Issues, what: str) -> str | None:
    """Return a stripped non-empty string, or record an issue and return ``None``."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    issues.add(path, f"{what} must be a non-empty string, got {describe(value)}.")
    return None


def check_keys(
    body: Mapping[Any, object], allowed: Sequence[str], path: str, issues: Issues
) -> None:
    """Record an issue for every key outside ``allowed``."""
    for key in body:
        if key in allowed:
            continue
        where = join_path(path, str(key))
        if key == "subtypes":
            issues.add(
                where,
                "'subtypes' does not exist. Set 'parents' on each child type "
                "instead, for example parents: [Organization].",
            )
        elif key in _SETTING_KEYS:
            issues.add(
                where,
                f"{key!r} is an extraction setting, not part of a schema. Move it "
                "to ExtractionSettings (for example label_thresholds={'Vendor': "
                "0.6}); the schema only describes types.",
            )
        else:
            close = difflib.get_close_matches(str(key), allowed, n=1)
            hint = f" Did you mean {close[0]!r}?" if close else ""
            issues.add(
                where,
                f"unknown key {str(key)!r}. Allowed keys: {', '.join(allowed)}.{hint}",
            )


def _split_labels(text: str) -> list[str]:
    return [part.strip() for part in text.split("|") if part.strip()]


def _cross(sources: list[str], targets: list[str]) -> list[list[str]]:
    return [[source, target] for source in sources for target in targets]


def _add_unique(pairs: list[list[str]], new: list[list[str]]) -> None:
    for pair in new:
        if pair not in pairs:
            pairs.append(pair)


def parse_relation(text: str) -> tuple[str, list[list[str]]] | None:
    """Read ``Source-LABEL->Target`` text.

    Args:
        text: A relation string. ``|`` separates alternatives on either side.

    Returns:
        The relation label and the expanded ``[source, target]`` pairs, or
        ``None`` when the text is not a relation string.
    """
    match = _RELATION_RE.match(text)
    if match is None:
        return None
    sources = _split_labels(match["source"])
    targets = _split_labels(match["target"])
    if not sources or not targets:
        return None
    return match["label"], _cross(sources, targets)


def parse_pattern(text: str) -> list[list[str]] | None:
    """Read ``Source->Target`` text into ``[source, target]`` pairs.

    Returns:
        The expanded pairs, or ``None`` when the text has no arrow.
    """
    match = _PATTERN_RE.match(text)
    if match is None:
        return None
    sources = _split_labels(match["source"])
    targets = _split_labels(match["target"])
    if not sources or not targets:
        return None
    return _cross(sources, targets)


def _description(value: object, path: str, issues: Issues) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    issues.add(path, f"description must be text, got {describe(value)}.")
    return ""


def _flag(value: object, path: str, issues: Issues) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    issues.add(path, f"must be true or false, got {describe(value)}.")
    return False


def _parents(value: object, path: str, issues: Issues) -> list[str]:
    if value is None:
        return []
    items = [value] if isinstance(value, str) else value
    if not isinstance(items, (list, tuple)) or not all(
        isinstance(item, str) and item.strip() for item in items
    ):
        issues.add(
            path, f"parents must be a label or a list of labels, got {describe(value)}."
        )
        return []
    return [item.strip() for item in items]


def _property(value: object, path: str, issues: Issues) -> JsonObject | None:
    if value is None:
        return {"type": DEFAULT_PROPERTY_TYPE}
    if isinstance(value, str):
        return {"type": value}
    if isinstance(value, Mapping):
        check_keys(value, PROPERTY_KEYS, path, issues)
        return {"type": DEFAULT_PROPERTY_TYPE, **value}
    issues.add(path, f"expected a type name or a mapping, got {describe(value)}.")
    return None


def _note_duplicate(seen: dict[str, str], name: str, path: str, issues: Issues) -> bool:
    """Record a duplicate property name, or remember it and return False."""
    if name in seen:
        issues.add(
            path,
            f"duplicate property {name!r}. First declared at {seen[name]}.",
        )
        return True
    seen[name] = path
    return False


def _property_from_list(
    item: object, item_path: str, seen: dict[str, str], issues: Issues
) -> tuple[str, JsonObject] | None:
    """Read one property from a list item, or record why it is unusable."""
    if isinstance(item, str) and item.strip():
        name = item.strip()
        if _note_duplicate(seen, name, item_path, issues):
            return None
        return name, {"type": DEFAULT_PROPERTY_TYPE}
    if isinstance(item, Mapping) and isinstance(item.get("name"), str):
        name = item["name"]
        if _note_duplicate(seen, name, item_path, issues):
            return None
        spec = _property(
            {k: v for k, v in item.items() if k != "name"}, item_path, issues
        )
        if spec is None:
            return None
        return name, spec
    issues.add(
        item_path,
        "expected a property name or a mapping with a 'name' key, "
        f"got {describe(item)}.",
    )
    return None


def _properties(value: object, path: str, issues: Issues) -> JsonObject:
    if value is None:
        return {}
    out: JsonObject = {}
    seen: dict[str, str] = {}
    if isinstance(value, Mapping):
        for name, spec in value.items():
            item_path = join_path(path, str(name))
            if _note_duplicate(seen, str(name), item_path, issues):
                continue
            item = _property(spec, item_path, issues)
            if item is not None:
                out[str(name)] = item
        return out
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found = _property_from_list(item, f"{path}[{index}]", seen, issues)
            if found is not None:
                out[found[0]] = found[1]
        return out
    issues.add(
        path, f"expected a list or a mapping of properties, got {describe(value)}."
    )
    return out


def _entity(body: Mapping[str, object], path: str, issues: Issues) -> Draft | None:
    check_keys(body, ENTITY_KEYS, path, issues)
    label = read_text(body.get("label"), join_path(path, "label"), issues, "label")
    if label is None:
        return None
    out: JsonObject = {k: v for k, v in body.items() if k in ENTITY_KEYS}
    out["label"] = label
    out["description"] = _description(
        body.get("description"), join_path(path, "description"), issues
    )
    out["parents"] = _parents(body.get("parents"), join_path(path, "parents"), issues)
    out["properties"] = _properties(
        body.get("properties"), join_path(path, "properties"), issues
    )
    if _flag(body.get("override"), join_path(path, "override"), issues):
        out["override"] = True
    else:
        out.pop("override", None)
    return Draft(path, out)


def _entity_from_map(
    key: object, item: object, item_path: str, issues: Issues
) -> Draft | None:
    """Read one entity from a mapping value, where the key is the label."""
    if item is None or isinstance(item, str):
        body: Mapping[str, object] = {"label": key, "description": item}
    elif isinstance(item, Mapping):
        if "label" in item and item["label"] != key:
            issues.add(
                join_path(item_path, "label"),
                f"label {item['label']!r} differs from its key {key!r}. "
                "Remove 'label'.",
            )
            return None
        body = {**item, "label": key}
    else:
        issues.add(
            item_path, f"expected a description or a mapping, got {describe(item)}."
        )
        return None
    return _entity(body, item_path, issues)


def _entity_from_list(item: object, item_path: str, issues: Issues) -> Draft | None:
    """Read one entity from a list item, which may be a label or an object."""
    if isinstance(item, str):
        body: Mapping[str, object] = {"label": item}
    elif isinstance(item, Mapping):
        body = item
    else:
        issues.add(
            item_path,
            f"expected a label or a mapping with a 'label' key, got {describe(item)}.",
        )
        return None
    return _entity(body, item_path, issues)


def read_entities(value: object, path: str, issues: Issues) -> list[Draft]:
    """Read the ``entities`` value in any accepted form.

    Args:
        value: A list of labels or objects, or a mapping from label to a
            description, ``None`` or an object.
        path: The path of ``value`` in the source.
        issues: Receives every problem found.

    Returns:
        One draft for each readable entity type, in source order.
    """
    if value is None:
        return []
    drafts: list[Draft] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            draft = _entity_from_map(key, item, join_path(path, str(key)), issues)
            if draft is not None:
                drafts.append(draft)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            draft = _entity_from_list(item, f"{path}[{index}]", issues)
            if draft is not None:
                drafts.append(draft)
    else:
        issues.add(
            path,
            f"expected a list or a mapping of entity types, got {describe(value)}.",
        )
    return drafts


def _patterns(value: object, path: str, issues: Issues) -> list[list[str]]:
    items = [value] if isinstance(value, str) else value
    if not isinstance(items, (list, tuple)):
        issues.add(path, f"expected a list of patterns, got {describe(value)}.")
        return []
    out: list[list[str]] = []
    for index, item in enumerate(items):
        item_path = f"{path}[{index}]"
        if isinstance(item, str):
            pairs = parse_pattern(item)
            if pairs is None:
                issues.add(
                    item_path,
                    f"cannot read {item!r} as a pattern. Write 'Source->Target', "
                    "for example 'Person->Organization'.",
                )
                continue
            _add_unique(out, pairs)
        elif (
            isinstance(item, (list, tuple))
            and len(item) == 2
            and all(isinstance(end, str) for end in item)
        ):
            _add_unique(out, [[item[0].strip(), item[1].strip()]])
        else:
            issues.add(
                item_path,
                "expected 'Source->Target' or a [source, target] pair, "
                f"got {describe(item)}.",
            )
    return out


def _relation_label(value: object, path: str, issues: Issues) -> str | None:
    label = read_text(value, path, issues, "label")
    if label is None:
        return None
    if _RELATION_LABEL_RE.match(label) is None:
        issues.add(
            path,
            f"relation label {label!r} may hold only letters, digits and underscores.",
        )
        return None
    return label


def _relation(body: Mapping[str, object], path: str, issues: Issues) -> Draft | None:
    check_keys(body, RELATION_KEYS, path, issues)
    label = _relation_label(body.get("label"), join_path(path, "label"), issues)
    if label is None:
        return None
    out: JsonObject = {k: v for k, v in body.items() if k in RELATION_KEYS}
    out["label"] = label
    out["description"] = _description(
        body.get("description"), join_path(path, "description"), issues
    )
    for key in ("patterns", "add_patterns"):
        if key in body:
            out[key] = _patterns(body[key], join_path(path, key), issues)
    if _flag(body.get("override"), join_path(path, "override"), issues):
        out["override"] = True
    else:
        out.pop("override", None)
    return Draft(path, out)


def _add_shorthand(
    drafts: list[Draft],
    shorthand: dict[str, Draft],
    label: str,
    pairs: list[list[str]],
    item_path: str,
) -> None:
    """Merge strings and triples that share a relation label into one draft."""
    existing = shorthand.get(label)
    if existing is None:
        draft = Draft(item_path, {"label": label, "description": "", "patterns": pairs})
        shorthand[label] = draft
        drafts.append(draft)
    else:
        _add_unique(existing.body["patterns"], pairs)


def _relation_from_map(
    key: object,
    item: object,
    item_path: str,
    issues: Issues,
    *,
    drafts: list[Draft],
    shorthand: dict[str, Draft],
) -> None:
    """Read one relation from a mapping value, where the key is the label."""
    if isinstance(item, (str, list, tuple)):
        label = _relation_label(key, item_path, issues)
        before = len(issues.items)
        pairs = _patterns(item, item_path, issues)
        if label is not None and pairs:
            _add_shorthand(drafts, shorthand, label, pairs, item_path)
        elif label is not None and not pairs and len(issues.items) == before:
            issues.add(
                item_path,
                "a relation needs 'patterns'. Write at least one pair, "
                "for example patterns: ['Person->Organization'].",
            )
    elif isinstance(item, Mapping):
        if "label" in item and item["label"] != key:
            issues.add(
                join_path(item_path, "label"),
                f"label {item['label']!r} differs from its key {key!r}. "
                "Remove 'label'.",
            )
            return
        draft = _relation({**item, "label": key}, item_path, issues)
        if draft is not None:
            drafts.append(draft)
    else:
        issues.add(item_path, f"expected patterns or a mapping, got {describe(item)}.")


def _relation_from_list(
    item: object,
    item_path: str,
    issues: Issues,
    *,
    drafts: list[Draft],
    shorthand: dict[str, Draft],
) -> None:
    """Read one relation from a list item: a string, a triple or an object."""
    if isinstance(item, str):
        parsed = parse_relation(item)
        if parsed is None:
            issues.add(
                item_path,
                f"cannot read {item!r} as a relation. Write it as "
                "'Source-LABEL->Target', for example 'Person-WORKS_FOR->Organization'.",
            )
            return
        label = _relation_label(parsed[0], item_path, issues)
        if label is not None:
            _add_shorthand(drafts, shorthand, label, parsed[1], item_path)
    elif (
        isinstance(item, (list, tuple))
        and len(item) == 3
        and all(isinstance(part, str) for part in item)
    ):
        label = _relation_label(item[1].strip(), item_path, issues)
        sources, targets = _split_labels(item[0]), _split_labels(item[2])
        if label is not None and sources and targets:
            _add_shorthand(
                drafts, shorthand, label, _cross(sources, targets), item_path
            )
        elif label is not None and (not sources or not targets):
            side = "source" if not sources else "target"
            issues.add(
                item_path,
                f"relation triple has an empty {side}. Use non-empty labels, "
                "for example ('Person', 'WORKS_FOR', 'Organization').",
            )
    elif isinstance(item, Mapping):
        draft = _relation(item, item_path, issues)
        if draft is not None:
            drafts.append(draft)
    else:
        issues.add(
            item_path,
            "expected a 'Source-LABEL->Target' string, a (source, label, "
            f"target) triple or a mapping, got {describe(item)}.",
        )


def read_relations(value: object, path: str, issues: Issues) -> list[Draft]:
    """Read the ``relations`` value in any accepted form.

    Args:
        value: A list of ``Source-LABEL->Target`` strings, ``(source, label,
            target)`` triples and objects, or a mapping from label to patterns
            or to an object.
        path: The path of ``value`` in the source.
        issues: Receives every problem found.

    Returns:
        One draft for each readable relation type, in source order. Strings and
        triples with the same label share one draft.
    """
    if value is None:
        return []
    drafts: list[Draft] = []
    shorthand: dict[str, Draft] = {}
    if isinstance(value, Mapping):
        for key, item in value.items():
            _relation_from_map(
                key,
                item,
                join_path(path, str(key)),
                issues,
                drafts=drafts,
                shorthand=shorthand,
            )
        return drafts
    if not isinstance(value, (list, tuple)):
        issues.add(
            path, f"expected a list or a mapping of relations, got {describe(value)}."
        )
        return drafts
    for index, item in enumerate(value):
        _relation_from_list(
            item, f"{path}[{index}]", issues, drafts=drafts, shorthand=shorthand
        )
    return drafts


def split_list(items: Sequence[object], issues: Issues) -> JsonObject:
    """Split a native list into entity labels and relations.

    Args:
        items: Labels, ``Source-LABEL->Target`` strings and ``(source, label,
            target)`` triples, in any order.
        issues: Receives every item that is none of these.

    Returns:
        A dict with the keys ``entities`` and ``relations``.
    """
    entities: list[object] = []
    relations: list[object] = []
    for index, item in enumerate(items):
        if isinstance(item, str) and "->" in item:
            relations.append(item)
        elif isinstance(item, str):
            entities.append(item)
        elif isinstance(item, (list, tuple)) and len(item) == 3:
            relations.append(item)
        else:
            issues.add(
                f"[{index}]",
                "expected a label, a 'Source-LABEL->Target' string or a (source, "
                f"label, target) triple, got {describe(item)}.",
            )
    return {"entities": entities, "relations": relations}
