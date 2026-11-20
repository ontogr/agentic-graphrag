---
title: agrag.schema.shorthand
sidebar_label: shorthand
---

# `agrag.schema.shorthand` \{#agrag-schema-shorthand}

Readers that turn every accepted notation into canonical dicts.

**Classes:**

- [**Draft**](Draft.md) – A type read from a source, with the path it was read from.

**Functions:**

- [**check_keys**](check_keys.md) – Record an issue for every key outside `allowed`.
- [**describe**](describe.md) – Name the type of a value for an error message.
- [**join_path**](join_path.md) – Append a key to a path.
- [**parse_pattern**](parse_pattern.md) – Read `Source->Target` text into `[source, target]` pairs.
- [**parse_relation**](parse_relation.md) – Read `Source-LABEL->Target` text.
- [**read_entities**](read_entities.md) – Read the `entities` value in any accepted form.
- [**read_relations**](read_relations.md) – Read the `relations` value in any accepted form.
- [**read_text**](read_text.md) – Return a stripped non-empty string, or record an issue and return `None`.
- [**split_list**](split_list.md) – Split a native list into entity labels and relations.

**Attributes:**

- [**DEFAULT_PROPERTY_TYPE**](DEFAULT_PROPERTY_TYPE.md) –
- [**ENTITY_KEYS**](ENTITY_KEYS.md) –
- [**JsonObject**](JsonObject.md) –
- [**PROPERTY_KEYS**](PROPERTY_KEYS.md) –
- [**RELATION_KEYS**](RELATION_KEYS.md) –
- [**TOP_LEVEL_KEYS**](TOP_LEVEL_KEYS.md) –
