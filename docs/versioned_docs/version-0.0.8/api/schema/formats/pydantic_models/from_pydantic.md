---
title: agrag.schema.formats.pydantic_models.from_pydantic
sidebar_label: from_pydantic
---

# `agrag.schema.formats.pydantic_models.from_pydantic` \{#agrag-schema-formats-pydantic_models-from_pydantic}

```python
from_pydantic(models:Sequence[type[BaseModel]], *, name:str = 'custom', version:str = '1') -> ImportResult
```

Read a schema from Pydantic model classes.

Each class is an entity type: the class name is the label and the
docstring is the description. A base class in `models` becomes a parent,
and the child keeps only the fields it adds or overrides. A field typed
as another class in `models`, alone or in a list, is a relation named
after the field in upper case, from the class to the field type. Any
other field is a property. A field without a default, and not optional,
is required. A `Literal` or `Enum` field becomes a property with
`enum` values. A single-valued relation field gets a limit of one per
source, and `max_length` on a list field sets the limit.
`Field(description=...)` is the description of a property or relation.

**Parameters:**

- **models** (<code>Sequence\[type\[BaseModel\]\]</code>) – The classes to read. Every class that a field refers to must
  be in this sequence.
- **name** (<code>str</code>) – The schema name.
- **version** (<code>str</code>) – The schema version.

**Returns:**

- <code>[ImportResult](../result/ImportResult.md)</code> – The schema and a warning for each field or description it dropped.

**Raises:**

- <code>[SchemaLoadError](../../errors/SchemaLoadError.md)</code> – The classes do not form a valid schema, for example a
  class named `Chunk`. The message lists every problem.
