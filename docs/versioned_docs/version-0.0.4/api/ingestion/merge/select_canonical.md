---
title: agrag.ingestion.merge.select_canonical
sidebar_label: select_canonical
---

# `agrag.ingestion.merge.select_canonical` \{#agrag-ingestion-merge-select_canonical}

```python
select_canonical(entities:list[Entity], entity_type:EntityType | None) -> tuple[Entity, list[Entity]]
```

Return the canonical survivor and the rest, from two or more entities.

Schema-completeness (fewest missing declared fields) first, then earliest
created_at, then lexicographically smallest id.

**Parameters:**

- **entities** (<code>list\[[Entity](../../common/data_models/entity/Entity-ref.md)\]</code>) – The entities to choose from.
- **entity_type** (<code>[EntityType](../../common/data_models/graph_schema/EntityType.md) | None</code>) – The schema type for this label, if declared.

**Returns:**

- <code>tuple\[[Entity](../../common/data_models/entity/Entity-ref.md), list\[[Entity](../../common/data_models/entity/Entity-ref.md)\]\]</code> – The survivor and the absorbed entities.
