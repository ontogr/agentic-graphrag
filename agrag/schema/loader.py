"""Load a GraphSchema from a dict, a label list, JSON, YAML, a path or a preset."""

import difflib
import json
import logging
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, NamedTuple

import yaml

from agrag.common.data_models.graph_schema import (
    Cardinality,
    GraphSchema,
    PropertySpec,
)
from agrag.schema.canonical import build_schema, dump_schema
from agrag.schema.errors import Issues, SchemaIssue, SchemaLoadError
from agrag.schema.shorthand import (
    TOP_LEVEL_KEYS,
    Draft,
    JsonObject,
    check_keys,
    describe,
    join_path,
    read_entities,
    read_relations,
    read_text,
    split_list,
)


logger = logging.getLogger(__name__)

SchemaSource = GraphSchema | Mapping[str, Any] | Sequence[Any] | Path | str

DEFAULT_NAME = "custom"
DEFAULT_VERSION = "1"

_FILE_SUFFIXES = (".json", ".yaml", ".yml", ".ttl")
_BASE_PREFIX = "extends."
_MODEL_LISTS = ("name", "version", "entities", "relations")

# The names that schema= and extends= accept in place of a path.
_NAMED_SCHEMAS: dict[str, GraphSchema] = {}


class _Raw(NamedTuple):
    data: JsonObject
    name: str
    origin: str | None


class _Child(NamedTuple):
    name: str
    version: str
    entities: list[Draft]
    relations: list[Draft]
    exclude: list[str]
    extras: JsonObject


class _Merged(NamedTuple):
    entities: dict[str, tuple[str, JsonObject]]
    relations: dict[str, tuple[str, JsonObject]]


def _fail(message: str, source: str | None = None) -> SchemaLoadError:
    return SchemaLoadError([SchemaIssue("schema", message)], source=source)


def _parse_json(text: str, source: str | None) -> object:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise _fail(
            f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}.", source
        ) from exc


def _parse_yaml(text: str, source: str | None) -> object:
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise _fail(f"invalid YAML: {exc}.", source) from exc


def _read_file(path: Path) -> object:
    suffix = path.suffix.lower()
    if suffix == ".ttl":
        from agrag.schema.formats.dispatch import read_owl_file  # noqa: PLC0415

        return read_owl_file(path)
    if suffix not in _FILE_SUFFIXES:
        shown = repr(path.suffix) if path.suffix else "files without a suffix"
        raise _fail(
            f"cannot read {shown} files. Use a .json, .yaml, .yml or .ttl file.",
            str(path),
        )
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise _fail("the file does not exist.", str(path)) from exc
    except UnicodeDecodeError as exc:
        raise _fail(f"cannot decode the file as UTF-8: {exc}.", str(path)) from exc
    except OSError as exc:
        raise _fail(f"cannot read the file: {exc.strerror}.", str(path)) from exc
    if suffix == ".json":
        return _parse_json(text, str(path))
    return _parse_yaml(text, str(path))


def _from_parsed(parsed: object, name: str, origin: str | None) -> _Raw:
    if isinstance(parsed, Mapping):
        return _Raw(dict(parsed), name, origin)
    if isinstance(parsed, list):
        issues = Issues()
        data = split_list(parsed, issues)
        if issues:
            raise issues.error(origin)
        return _Raw(data, name, origin)
    raise _fail(
        f"a schema file must hold a mapping or a list, got {describe(parsed)}.", origin
    )


def _read_source(source: SchemaSource) -> GraphSchema | _Raw:
    if isinstance(source, GraphSchema):
        return source
    if isinstance(source, Mapping):
        return _Raw(dict(source), DEFAULT_NAME, None)
    if isinstance(source, str):
        text = source.strip()
        if text in _NAMED_SCHEMAS:
            return _NAMED_SCHEMAS[text]
        if text.startswith(("{", "[")):
            return _from_parsed(_parse_json(text, None), DEFAULT_NAME, None)
        if not (text.lower().endswith(_FILE_SUFFIXES) or Path(text).is_file()):
            names = ", ".join(sorted(_NAMED_SCHEMAS))
            presets = f"a preset name ({names}), " if names else ""
            raise _fail(
                f"unknown schema {text!r}. Pass {presets}a path to a .json, "
                ".yaml, .yml or .ttl file, a dict, or a list of labels."
            )
        path = Path(text)
    elif isinstance(source, Path):
        path = source
    elif isinstance(source, (list, tuple)):
        issues = Issues()
        data = split_list(source, issues)
        if issues:
            raise issues.error()
        return _Raw(data, DEFAULT_NAME, None)
    else:
        raise _fail(
            f"cannot load a schema from {describe(source)}. Pass a GraphSchema, a "
            "dict, a list of labels, a preset name or a path."
        )
    return _from_parsed(_read_file(path), path.stem, str(path))


def _version(value: object, issues: Issues) -> str:
    if value is None:
        return DEFAULT_VERSION
    if (
        isinstance(value, (str, int, float))
        and not isinstance(value, bool)
        and str(value).strip()
    ):
        return str(value).strip()
    issues.add("version", f"version must be text or a number, got {describe(value)}.")
    return DEFAULT_VERSION


def _exclude(value: object, issues: Issues) -> list[str]:
    if value is None:
        return []
    items = [value] if isinstance(value, str) else value
    if not isinstance(items, (list, tuple)):
        issues.add("exclude", f"expected a list of labels, got {describe(value)}.")
        return []
    labels = []
    for index, item in enumerate(items):
        label = read_text(item, f"exclude[{index}]", issues, "label")
        if label is not None:
            labels.append(label)
    return labels


def _read_child(data: JsonObject, default_name: str, issues: Issues) -> _Child:
    check_keys(data, TOP_LEVEL_KEYS, "", issues)
    name = default_name
    if data.get("name") is not None:
        name = read_text(data["name"], "name", issues, "name") or default_name
    return _Child(
        name=name,
        version=_version(data.get("version"), issues),
        entities=read_entities(data.get("entities"), "entities", issues),
        relations=read_relations(data.get("relations"), "relations", issues),
        exclude=_exclude(data.get("exclude"), issues),
        extras={
            key: value
            for key, value in data.items()
            if key in TOP_LEVEL_KEYS
            and key not in (*_MODEL_LISTS, "extends", "exclude")
        },
    )


def _enum_loosened(old_enum: object, new_enum: object) -> bool:
    """Return whether a child widens the allowed values of a property."""
    if new_enum is None and isinstance(old_enum, (list, tuple)) and old_enum:
        try:
            set(old_enum)
        except TypeError:
            return False
        return True
    if not isinstance(old_enum, (list, tuple)) or not old_enum:
        return False
    if not isinstance(new_enum, (list, tuple)) or not new_enum:
        return False
    try:
        return not set(new_enum) <= set(old_enum)
    except TypeError:
        return False


def _normalized_spec(spec: object) -> PropertySpec | None:
    """Validate a raw property spec, or return None when it is invalid."""
    if not isinstance(spec, Mapping):
        return None
    try:
        return PropertySpec.model_validate(dict(spec))
    except Exception:
        return None


def _loosened(base: JsonObject, new: JsonObject) -> list[str]:
    """List the ways ``new`` loosens the property constraints of ``base``."""
    problems: list[str] = []
    raw_new_properties = new.get("properties", {})
    if not isinstance(raw_new_properties, Mapping):
        return problems
    raw_base_properties = base.get("properties", {})
    if not isinstance(raw_base_properties, Mapping):
        return problems
    for name, old in raw_base_properties.items():
        if not isinstance(old, Mapping):
            continue
        spec = raw_new_properties.get(name)
        if spec is None:
            problems.append(f"drops property {name!r}")
            continue
        if not isinstance(spec, Mapping):
            continue
        shaped = _normalized_spec(spec)
        if shaped is None:
            continue
        if shaped.type != old.get("type"):
            problems.append(
                f"changes the type of property {name!r} from {old.get('type')!r} "
                f"to {shaped.type!r}"
            )
        if old.get("required", False) is True and not shaped.required:
            problems.append(f"makes property {name!r} optional")
        if _enum_loosened(old.get("enum"), shaped.enum):
            problems.append(f"widens the allowed values of property {name!r}")
    return problems


def _relation_loosened(base: JsonObject, new: JsonObject) -> list[str]:
    """List the ways ``new`` loosens the cardinality limits of ``base``."""
    base_limits = base.get("cardinality") or {}
    new_limits = new.get("cardinality") or {}
    if not isinstance(base_limits, Mapping) or not isinstance(new_limits, Mapping):
        return []
    try:
        shaped = Cardinality.model_validate(dict(new_limits))
    except Exception:
        return []
    problems: list[str] = []
    for key, side, updated in (
        ("max_per_source", "source", shaped.max_per_source),
        ("max_per_target", "target", shaped.max_per_target),
    ):
        limit = base_limits.get(key)
        if limit is None or isinstance(limit, bool) or not isinstance(limit, int):
            continue
        if updated is None:
            problems.append(f"removes the cardinality limit on the {side} side")
        elif updated > limit:
            problems.append(f"raises the cardinality limit on the {side} side")
    return problems


def _apply_exclude(
    labels: list[str], merged: _Merged, issues: Issues
) -> tuple[set[str], set[str]]:
    removed: set[str] = set()
    excluded_relations: set[str] = set()
    for index, label in enumerate(labels):
        found = False
        if label in merged.entities:
            del merged.entities[label]
            removed.add(label)
            found = True
        if label in merged.relations:
            del merged.relations[label]
            excluded_relations.add(label)
            found = True
        if not found:
            issues.add(
                f"exclude[{index}]",
                f"cannot exclude {label!r}: the base schema has no entity type or "
                "relation type with that label.",
            )
    for label, (origin, body) in list(merged.relations.items()):
        kept = [
            pair
            for pair in body["patterns"]
            if pair[0] not in removed and pair[1] not in removed
        ]
        if len(kept) == len(body["patterns"]):
            continue
        if kept:
            logger.info("Relation %s lost patterns that used excluded types.", label)
            merged.relations[label] = (origin, {**body, "patterns": kept})
        else:
            logger.info(
                "Relation %s removed: all its patterns used excluded types.", label
            )
            del merged.relations[label]
    return removed, excluded_relations


def _add_entities(
    drafts: list[Draft],
    merged: _Merged,
    base_name: str | None,
    removed: set[str],
    issues: Issues,
) -> None:
    seen: dict[str, str] = {}
    for draft in drafts:
        body = dict(draft.body)
        label = body["label"]
        marker = body.pop("override", False)
        if label in seen:
            issues.add(
                draft.path,
                f"duplicate entity type {label!r}. First declared at {seen[label]}.",
            )
            continue
        seen[label] = draft.path
        if label in removed:
            issues.add(
                draft.path,
                f"entity type {label!r} is excluded from the base schema and "
                "declared here. Remove it from 'exclude' and add 'override: true' "
                "to replace it.",
            )
        elif label not in merged.entities:
            if marker:
                issues.add(
                    join_path(draft.path, "override"),
                    _no_target(base_name, "entity", label),
                )
            else:
                merged.entities[label] = (draft.path, body)
        elif not marker:
            issues.add(draft.path, _redeclared("entity", label, base_name))
        else:
            problems = _loosened(merged.entities[label][1], body)
            if problems:
                issues.add(draft.path, _loosening("entity", label, problems))
                continue
            logger.warning("Schema replaces the base entity type %r.", label)
            merged.entities[label] = (draft.path, body)


def _add_relations(
    drafts: list[Draft],
    merged: _Merged,
    base_name: str | None,
    issues: Issues,
    *,
    excluded_relations: set[str] | None = None,
) -> None:
    seen: dict[str, str] = {}
    gone = excluded_relations if excluded_relations is not None else set()
    for draft in drafts:
        body = dict(draft.body)
        label = body["label"]
        marker = body.pop("override", False)
        extra = body.pop("add_patterns", None)
        if label in seen:
            issues.add(
                draft.path,
                f"duplicate relation type {label!r}. First declared at {seen[label]}.",
            )
            continue
        seen[label] = draft.path
        if label in gone:
            issues.add(
                draft.path,
                f"relation type {label!r} is excluded from the base schema and "
                "declared here. Remove it from 'exclude' and add 'override: true' "
                "to replace it.",
            )
            continue
        existing = merged.relations.get(label)
        if extra is not None:
            _add_patterns(
                draft,
                body,
                extra,
                existing,
                marker=marker,
                merged=merged,
                base_name=base_name,
                issues=issues,
            )
            continue
        if "patterns" not in body or not body["patterns"]:
            issues.add(
                draft.path,
                "a relation needs 'patterns'. Write at least one pair, for example "
                "patterns: ['Person->Organization'].",
            )
        elif existing is None:
            if marker:
                issues.add(
                    join_path(draft.path, "override"),
                    _no_target(base_name, "relation", label),
                )
            else:
                merged.relations[label] = (draft.path, body)
        elif not marker:
            issues.add(draft.path, _redeclared("relation", label, base_name))
        else:
            problems = _relation_loosened(existing[1], body)
            if problems:
                issues.add(draft.path, _loosening("relation", label, problems))
                continue
            logger.warning("Schema replaces the base relation type %r.", label)
            merged.relations[label] = (draft.path, body)


def _add_patterns(
    draft: Draft,
    body: JsonObject,
    extra: list[list[str]],
    existing: tuple[str, JsonObject] | None,
    *,
    marker: bool,
    merged: _Merged,
    base_name: str | None,
    issues: Issues,
) -> None:
    """Add pairs to a base relation, or report why that is not allowed."""
    label = body["label"]
    if existing is None:
        issues.add(
            draft.path,
            f"'add_patterns' needs a relation in the base schema {base_name!r}; "
            f"{label!r} is not one.",
        )
    elif "patterns" in body or marker:
        issues.add(
            draft.path,
            "use 'patterns' with 'override: true' to replace the patterns, or "
            "'add_patterns' to add to them, not both.",
        )
    else:
        blocked = sorted(
            key
            for key in body
            if key not in ("label", "description", "add_patterns", "override")
        )
        if blocked:
            issues.add(
                draft.path,
                f"'add_patterns' cannot be combined with {blocked}. Use "
                "'patterns' with 'override: true' to replace the relation, "
                "or remove these keys.",
            )
            return
        patterns = [list(pair) for pair in existing[1]["patterns"]]
        patterns.extend(pair for pair in extra if pair not in patterns)
        description = body.get("description") or existing[1].get("description", "")
        merged.relations[label] = (
            draft.path,
            {**existing[1], "description": description, "patterns": patterns},
        )


def _no_target(base_name: str | None, kind: str, label: str) -> str:
    if base_name is None:
        return "'override' needs a base schema. Set 'extends' to name one."
    return (
        f"'override' is set but the base schema {base_name!r} has no {kind} type "
        f"{label!r}. Remove 'override'."
    )


def _redeclared(kind: str, label: str, base_name: str | None) -> str:
    return (
        f"{kind} type {label!r} is already defined by the base schema "
        f"{base_name!r}. Add 'override: true' to replace it, or choose another label."
    )


def _loosening(kind: str, label: str, problems: list[str]) -> str:
    return (
        f"override of {kind} type {label!r} loosens the base definition: "
        f"{'; '.join(problems)}. Keep or tighten these constraints, or exclude "
        f"{label!r} and declare a new label."
    )


def _missing_type(name: str, labels: set[str], removed: set[str], what: str) -> str:
    if name in removed:
        return (
            f"{what} {name!r} is not a declared entity type. It was excluded; "
            "remove it from 'exclude' or stop using it."
        )
    close = difflib.get_close_matches(name, sorted(labels), n=1)
    hint = f"Did you mean {close[0]!r}?" if close else "Declare it in 'entities'."
    return f"{what} {name!r} is not a declared entity type. {hint}"


def _check_references(merged: _Merged, removed: set[str], issues: Issues) -> None:
    labels = set(merged.entities)
    for label, (origin, body) in merged.entities.items():
        for index, parent in enumerate(body["parents"]):
            if parent in labels:
                continue
            if origin.startswith(_BASE_PREFIX):
                issues.add(
                    "exclude",
                    f"cannot exclude {parent!r}: base type {label!r} has it as a "
                    f"parent. Exclude {label!r} as well.",
                )
            else:
                issues.add(
                    f"{origin}.parents[{index}]",
                    _missing_type(parent, labels, removed, "parent"),
                )
    for origin, body in merged.relations.values():
        for index, pair in enumerate(body["patterns"]):
            for end in dict.fromkeys(pair):
                if end not in labels:
                    issues.add(
                        f"{origin}.patterns[{index}]",
                        _missing_type(end, labels, removed, "pattern end"),
                    )


def _merge(base: GraphSchema | None, child: _Child, issues: Issues) -> _Merged:
    merged = _Merged({}, {})
    removed: set[str] = set()
    excluded_relations: set[str] = set()
    base_name = None if base is None else base.name
    if base is None:
        if child.exclude:
            issues.add(
                "exclude", "'exclude' needs a base schema. Set 'extends' to name one."
            )
    else:
        data = dump_schema(base)
        for body in data["entities"]:
            merged.entities[body["label"]] = (f"{_BASE_PREFIX}{body['label']}", body)
        for body in data["relations"]:
            merged.relations[body["label"]] = (f"{_BASE_PREFIX}{body['label']}", body)
        removed, excluded_relations = _apply_exclude(child.exclude, merged, issues)
    _add_entities(child.entities, merged, base_name, removed, issues)
    _add_relations(
        child.relations,
        merged,
        base_name,
        issues,
        excluded_relations=excluded_relations,
    )
    _check_references(merged, removed, issues)
    return merged


def _pick_extends(
    from_call: SchemaSource | None, from_file: object, issues: Issues
) -> SchemaSource | None:
    if from_call is not None and from_file is not None:
        issues.add(
            "extends", "'extends' is set in the file and in the call. Set it once."
        )
        return None
    chosen = from_call if from_call is not None else from_file
    if chosen is None or isinstance(
        chosen, (GraphSchema, Mapping, Sequence, Path, str)
    ):
        return chosen
    issues.add(
        "extends",
        f"extends must be a name, a path or a schema, got {describe(chosen)}.",
    )
    return None


def _resolve_base(
    base_source: SchemaSource | None, child_origin: str | None
) -> SchemaSource | None:
    """Resolve a file-declared base path against the child file directory."""
    if base_source is None or child_origin is None:
        return base_source
    folder = Path(child_origin).parent
    if isinstance(base_source, Path):
        target = base_source
    elif isinstance(base_source, str):
        text = base_source.strip()
        if (
            text in _NAMED_SCHEMAS
            or text.startswith(("{", "["))
            or Path(text).is_absolute()
        ):
            return base_source
        target = Path(text)
        if not (text.lower().endswith(_FILE_SUFFIXES) or (folder / target).is_file()):
            return base_source
    else:
        return base_source
    if target.is_absolute():
        return base_source
    return str(folder / target)


def _load(
    source: SchemaSource,
    extends: SchemaSource | None,
    stack: tuple[str, ...],
    _seen: tuple[int, ...] = (),
) -> GraphSchema:
    if isinstance(source, Mapping) and id(source) in _seen:
        raise _fail("'extends' loops back to this schema.")
    seen = (*_seen, id(source)) if isinstance(source, Mapping) else _seen
    read = _read_source(source)
    if isinstance(read, GraphSchema):
        if extends is None:
            return read.model_copy(deep=True)
        read = _Raw(dump_schema(read), read.name, None)

    key = str(Path(read.origin).resolve()) if read.origin else None
    if key is not None and key in stack:
        chain = " -> ".join((*stack, key))
        raise _fail(f"'extends' loops back to this file: {chain}.", read.origin)

    issues = Issues()
    base_source = _pick_extends(extends, read.data.get("extends"), issues)
    if issues:
        raise issues.error(read.origin)
    if base_source is not None and extends is None and read.origin is not None:
        base_source = _resolve_base(base_source, read.origin)
    base = None
    if base_source is not None:
        base = _load(base_source, None, stack if key is None else (*stack, key), seen)

    child = _read_child(read.data, read.name, issues)
    merged = _merge(base, child, issues)
    if issues:
        raise issues.error(read.origin)

    base_extras = (
        {}
        if base is None
        else {
            field: value
            for field, value in dump_schema(base).items()
            if field not in _MODEL_LISTS
        }
    )
    data: JsonObject = {
        **base_extras,
        **child.extras,
        "name": child.name,
        "version": child.version,
        "entities": [body for _, body in merged.entities.values()],
        "relations": [body for _, body in merged.relations.values()],
    }
    origins = {
        "entities": [origin for origin, _ in merged.entities.values()],
        "relations": [origin for origin, _ in merged.relations.values()],
    }
    schema = build_schema(data, origins, issues)
    if schema is None:
        raise issues.error(read.origin)
    return schema


def load_schema(
    source: SchemaSource, *, extends: SchemaSource | None = None
) -> GraphSchema:
    """Load a schema from any accepted source.

    ``source`` may be a ``GraphSchema``, a dict, a list of entity labels and
    relations, JSON text, a path to a ``.json``, ``.yaml`` or ``.yml`` file, or
    the name of a shipped schema. Shorthand is accepted at every level. The
    result is always the canonical ``GraphSchema``.

    A schema with no ``extends`` stands alone and replaces the default schema.
    With ``extends``, the schema builds on a base. A type or relation that the
    base already defines is an error unless it is marked ``override: true``,
    and an override may not loosen the base. ``exclude`` removes base types or
    relations, with the patterns that use them. ``add_patterns`` adds pairs to
    a base relation.

    Extraction settings such as thresholds are not part of a schema. A key that
    names one is an error.

    Args:
        source: The schema to load.
        extends: The base schema, as a shipped name, a path, a dict or a
            ``GraphSchema``. Do not also set ``extends`` in ``source``.

    Returns:
        The loaded schema. ``name`` defaults to ``custom`` (the file stem for a
        file) and ``version`` defaults to ``"1"``.

    Raises:
        SchemaLoadError: The source cannot be read or is invalid. The message
            lists every problem with the path to the offending key.
    """
    return _load(source, extends, ())
