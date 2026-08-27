# Google Style Docstrings And Comments

Use the Google Python Style Guide as the governing policy for docstrings and
use the examples below as the preferred local formatting examples.

Diátaxis is primarily for docs pages. For docstrings, apply only the lightweight
version below: prefer precise reference-style API facts, with brief explanation
or examples only when they help the caller use the API correctly.

## Required docstring rules

- Always use triple double quotes (`"""`) for docstrings.
- Start each docstring with a one-line summary ending in `.`, `?`, or `!`.
  Keep the summary on one physical line no longer than 88 characters.
- Write docstrings as deliberate API documentation a senior engineer would keep
  in the codebase, not as agent notes about what was found, tried, fixed, or
  verified.
- If more detail follows the summary, add one blank line before the longer
  description.
- Function and method docstrings are required for public APIs, nontrivial
  functions, and functions with non-obvious logic. Small private helpers may use
  a one-line docstring when their signature and name are clear.
- Test module docstrings are not optional. Add them so that they provide useful
  context, such as what is being tested, unusual setup, dependencies, or how to run/update fixtures.
  Do not add boilerplate docstrings such as `"""Tests for foo."""`.
- Document call semantics and caller-visible side effects, not implementation
  details. Put implementation notes in comments near the code.
- Explain purpose, behavior, edge cases, and constraints. Do not restate the
  function, class, or parameter names in prose.
- Keep docstrings synchronized with code changes. Update docstrings whenever a
  code change makes existing documentation stale.
- If a docstring exceeds the 88-character line limit, rewrite it concisely. Do
  not truncate text or wrap awkwardly mid-phrase.
- Use either descriptive style (`"""Fetches rows."""`) or imperative style
  (`"""Fetch rows."""`) consistently within a file.

## Inline comments

- Inline comments must explain why the code exists, not what the code does.
- Add comments only when they explain non-obvious business logic,
  medical-domain constraints, safety concerns, algorithms, performance
  tradeoffs, library workarounds, or temporary hacks with ticket references.
  Prefer clearer code over comments for ordinary control flow.
- Do not leave AI-slop comments: no progress notes, literal findings,
  self-congratulation, implementation transcripts, or statements that something
  "works". Comments should read like concise guidance from a human maintainer.
- Do not place comments at the end of code lines. If a comment describes a
  specific line or block, put the comment on the preceding line aligned with
  the code it describes.
- Do not add comments for self-explanatory code, trivial operations, changelog
  notes, or closing-brace/block markers.
- Do not use visual separator comments, such as `# ------- text -------` or
  `# ------------`.
- Do not write comments that merely restate code, such as `# increment x` above
  `x += 1`.
- Write comments in clear, professional prose with normal grammar and
  punctuation. Avoid dramatic language, all-caps emphasis, and boilerplate.

## Diátaxis influence on docstrings

- Default to reference-style precision: what the object is, what the caller can
  rely on, parameters, return values, raised interface exceptions, side effects,
  constraints, and edge cases.
- Add brief explanation only when context is necessary to use the API correctly,
  such as a non-obvious invariant, algorithm choice, medical-domain assumption,
  or safety constraint.
- Add short examples only when they materially clarify common usage. Keep them
  canonical, not exhaustive.
- Do not turn docstrings into tutorials or how-to guides. If a learner needs a
  walkthrough, write or link to a docs page instead.

## Sections

- Use section headers ending with a colon, such as `Args:`, `Returns:`,
  `Yields:`, `Raises:`, `Attributes:`, `Examples:`, and `Note:`.
- Use `Yields:` instead of `Returns:` for generators.
- Omit `Returns:` when the function returns only `None`, or when a one-line
  summary that starts with `Return`, `Returns`, `Yield`, or `Yields` fully
  describes the return value.
- In `Args:`, list every parameter by name. Do not repeat obvious types already
  provided by the function signature.
- List variable arguments as `*args` and `**kwargs`.
- Do not include `self` or `cls` in `Args:`.
- In `Raises:`, list only exceptions that are relevant to the public interface.
  Do not document exceptions that occur only when callers violate the documented
  API contract.
- Use a hanging indent of either two or four spaces inside sections. Be
  consistent within a file. This project prefers the four-space style shown
  below.

## Classes, exceptions, and properties

- Classes should have a docstring describing what an instance represents.
- Exception class docstrings should describe what the exception represents, not
  start with boilerplate such as `Raised when...`.
- Pydantic models and settings classes should use class docstrings with an
  `Attributes:` section for public fields. For environment-backed settings,
  include the environment variable name in the field description, such as
  `Env: NEO4J_URI`.
- Public attributes, excluding properties, should be documented in an
  `Attributes:` section or inline near the attribute declaration. Do not mix the
  two styles within the same class/module.
- Document `__init__` parameters either in the class docstring or in the
  `__init__` docstring. Do not duplicate both forms.
- Document properties in the getter. If the setter has notable behavior, mention
  it in the getter docstring.
- An overridden method may omit a docstring when decorated with `@override` and
  the base method contract is unchanged. Add a docstring when the override
  changes or refines caller-visible behavior.

## Types and annotations

- PEP 484 type annotations are required for typed public APIs.
- When parameters, attributes, and return values are annotated, do not repeat
  obvious types in the docstring.
- Include type information in docstrings only when annotations are absent or
  insufficient to explain accepted values, units, shapes, or other semantics.

## Project examples

Use these local patterns when documenting common agrag component types.

### Pydantic data model

```python
class Entity(DataPoint):
    """A resolved medical entity from the knowledge graph.

    Identity is ``(canonical_name, label)``. An entity may accumulate aliases
    and provenance records across resolution runs.

    Attributes:
        name: Surface-form name as extracted from source text.
        label: Medical entity type from the schema, such as ``Disease`` or
            ``Drug``.
        canonical_name: Resolved canonical identifier, or ``None`` before the
            resolve stage.
        aliases: Known alternate names.
        provenance: Extraction provenance records with surface forms, chunk ids,
            and character offsets.

    Note:
        Entities below the configured confidence threshold are filtered during
        normalization and do not reach aggregation or resolution.
    """
```

### Settings class

```python
class Neo4jSettings(BaseSettings):
    """Neo4j connection configuration.

    All fields are overridable via environment variables with the ``NEO4J_``
    prefix.

    Attributes:
        uri: Bolt connection URI. Env: ``NEO4J_URI``.
        user: Database username. Env: ``NEO4J_USER``.
        password: Database password. Env: ``NEO4J_PASSWORD``.
        database: Target database name. Env: ``NEO4J_DATABASE``.
    """
```

### Pipeline node or complex algorithm

```python
async def normalize_node(state: ExtractionState) -> ExtractionState:
    """Deduplicate and normalize extracted entities and relations per chunk.

    Collapses duplicate entity and relation keys within a chunk, merges
    provenance, and filters low-confidence or too-short entities.

    Args:
        state: Pipeline state carrying per-chunk extraction results.

    Returns:
        Updated pipeline state with ``normalized_chunks`` populated.

    Note:
        Normalization is deterministic, makes no LLM calls, and is safe to
        re-run on already-normalized state.
    """
```

The following block is the upstream Sphinx/Napoleon `example_google.py`, kept
only to show section structure and syntax. It does not follow this project's
style: it repeats types in docstrings (`param1 (int):`) and uses `:obj:`
reStructuredText, both of which the rules above forbid. Defer to the project
examples above; use this block for section-header reference only.

```python
"""Example Google style docstrings.

This module demonstrates documentation as specified by the `Google Python
Style Guide`_. Docstrings may extend over multiple lines. Sections are created
with a section header and a colon followed by a block of indented text.

Example:
    Examples can be given using either the ``Example`` or ``Examples``
    sections. Sections support any reStructuredText formatting, including
    literal blocks::

        $ python example_google.py

Section breaks are created by resuming unindented text. Section breaks
are also implicitly created anytime a new section starts.

Attributes:
    module_level_variable1 (int): Module level variables may be documented in
        either the ``Attributes`` section of the module docstring, or in an
        inline docstring immediately following the variable.

        Either form is acceptable, but the two should not be mixed. Choose
        one convention to document module level variables and be consistent
        with it.

Todo:
    * For module TODOs
    * You have to also use ``sphinx.ext.todo`` extension

.. _Google Python Style Guide:
   http://google.github.io/styleguide/pyguide.html

"""

module_level_variable1 = 12345

module_level_variable2 = 98765
"""int: Module level variable documented inline.

The docstring may span multiple lines. The type may optionally be specified
on the first line, separated by a colon.
"""


def function_with_types_in_docstring(param1, param2):
    """Example function with types documented in the docstring.

    `PEP 484`_ type annotations are supported. If attribute, parameter, and
    return types are annotated according to `PEP 484`_, they do not need to be
    included in the docstring:

    Args:
        param1 (int): The first parameter.
        param2 (str): The second parameter.

    Returns:
        bool: The return value. True for success, False otherwise.

    .. _PEP 484:
        https://www.python.org/dev/peps/pep-0484/

    """


def function_with_pep484_type_annotations(param1: int, param2: str) -> bool:
    """Example function with PEP 484 type annotations.

    Args:
        param1: The first parameter.
        param2: The second parameter.

    Returns:
        The return value. True for success, False otherwise.

    """


def module_level_function(param1, param2=None, *args, **kwargs):
    """This is an example of a module level function.

    Function parameters should be documented in the ``Args`` section. The name
    of each parameter is required. The type and description of each parameter
    is optional, but should be included if not obvious.

    If \*args or \*\*kwargs are accepted,
    they should be listed as ``*args`` and ``**kwargs``.

    The format for a parameter is::

        name (type): description
            The description may span multiple lines. Following
            lines should be indented. The "(type)" is optional.

            Multiple paragraphs are supported in parameter
            descriptions.

    Args:
        param1 (int): The first parameter.
        param2 (:obj:`str`, optional): The second parameter. Defaults to None.
            Second line of description should be indented.
        *args: Variable length argument list.
        **kwargs: Arbitrary keyword arguments.

    Returns:
        bool: True if successful, False otherwise.

        The return type is optional and may be specified at the beginning of
        the ``Returns`` section followed by a colon.

        The ``Returns`` section may span multiple lines and paragraphs.
        Following lines should be indented to match the first line.

        The ``Returns`` section supports any reStructuredText formatting,
        including literal blocks::

            {
                'param1': param1,
                'param2': param2
            }

    Raises:
        AttributeError: The ``Raises`` section is a list of all exceptions
            that are relevant to the interface.
        ValueError: If `param2` is equal to `param1`.

    """
    if param1 == param2:
        raise ValueError('param1 may not be equal to param2')
    return True


def example_generator(n):
    """Generators have a ``Yields`` section instead of a ``Returns`` section.

    Args:
        n (int): The upper limit of the range to generate, from 0 to `n` - 1.

    Yields:
        int: The next number in the range of 0 to `n` - 1.

    Examples:
        Examples should be written in doctest format, and should illustrate how
        to use the function.

        >>> print([i for i in example_generator(4)])
        [0, 1, 2, 3]

    """
    for i in range(n):
        yield i


class ExampleError(Exception):
    """Exceptions are documented in the same way as classes.

    The __init__ method may be documented in either the class level
    docstring, or as a docstring on the __init__ method itself.

    Either form is acceptable, but the two should not be mixed. Choose one
    convention to document the __init__ method and be consistent with it.

    Note:
        Do not include the `self` parameter in the ``Args`` section.

    Args:
        msg (str): Human readable string describing the exception.
        code (:obj:`int`, optional): Error code.

    Attributes:
        msg (str): Human readable string describing the exception.
        code (int): Exception error code.

    """

    def __init__(self, msg, code):
        self.msg = msg
        self.code = code


class ExampleClass(object):
    """The summary line for a class docstring should fit on one line.

    If the class has public attributes, they may be documented here
    in an ``Attributes`` section and follow the same formatting as a
    function's ``Args`` section. Alternatively, attributes may be documented
    inline with the attribute's declaration (see __init__ method below).

    Properties created with the ``@property`` decorator should be documented
    in the property's getter method.

    Attributes:
        attr1 (str): Description of `attr1`.
        attr2 (:obj:`int`, optional): Description of `attr2`.

    """

    def __init__(self, param1, param2, param3):
        """Example of docstring on the __init__ method.

        The __init__ method may be documented in either the class level
        docstring, or as a docstring on the __init__ method itself.

        Either form is acceptable, but the two should not be mixed. Choose one
        convention to document the __init__ method and be consistent with it.

        Note:
            Do not include the `self` parameter in the ``Args`` section.

        Args:
            param1 (str): Description of `param1`.
            param2 (:obj:`int`, optional): Description of `param2`. Multiple
                lines are supported.
            param3 (:obj:`list` of :obj:`str`): Description of `param3`.

        """
        self.attr1 = param1
        self.attr2 = param2
        self.attr3 = param3  #: Doc comment *inline* with attribute

        #: list of str: Doc comment *before* attribute, with type specified
        self.attr4 = ['attr4']

        self.attr5 = None
        """str: Docstring *after* attribute, with type specified."""

    @property
    def readonly_property(self):
        """str: Properties should be documented in their getter method."""
        return 'readonly_property'

    @property
    def readwrite_property(self):
        """:obj:`list` of :obj:`str`: Properties with both a getter and setter
        should only be documented in their getter method.

        If the setter method contains notable behavior, it should be
        mentioned here.
        """
        return ['readwrite_property']

    @readwrite_property.setter
    def readwrite_property(self, value):
        value

    def example_method(self, param1, param2):
        """Class methods are similar to regular functions.

        Note:
            Do not include the `self` parameter in the ``Args`` section.

        Args:
            param1: The first parameter.
            param2: The second parameter.

        Returns:
            True if successful, False otherwise.

        """
        return True

    def __special__(self):
        """By default special members with docstrings are not included.

        Special members are any methods or attributes that start with and
        end with a double underscore. Any special member with a docstring
        will be included in the output, if
        ``napoleon_include_special_with_doc`` is set to True.

        This behavior can be enabled by changing the following setting in
        Sphinx's conf.py::

            napoleon_include_special_with_doc = True

        """
        pass

    def __special_without_docstring__(self):
        pass

    def _private(self):
        """By default private members are not included.

        Private members are any methods or attributes that start with an
        underscore and are *not* special. By default they are not included
        in the output.

        This behavior can be changed such that private members *are* included
        by changing the following setting in Sphinx's conf.py::

            napoleon_include_private_with_doc = True

        """
        pass

    def _private_without_docstring(self):
        pass
```
