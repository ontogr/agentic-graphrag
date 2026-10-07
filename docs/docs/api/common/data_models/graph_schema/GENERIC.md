---
title: agrag.common.data_models.graph_schema.GENERIC
sidebar_label: GENERIC
---

# `agrag.common.data_models.graph_schema.GENERIC` \{#agrag-common-data_models-graph_schema-GENERIC}

```python
GENERIC = GraphSchema(name='generic', version='1', entities=[EntityType(label='Person', description='A named individual.'), EntityType(label='Organization', description='A company or institution.'), EntityType(label='Location', description='A place or geographic area.'), EntityType(label='Event', description='A named occurrence at a time or place.'), EntityType(label='Product', description='A named product, service, or work.')], relations=[RelationType(label='RELATED_TO', description='A generic relationship between two entities.', patterns=[(src, tgt) for src in _GENERIC_LABELS for tgt in _GENERIC_LABELS])])
```

A ready-made schema for open-domain text.

It declares five entity types (`Person`, `Organization`, `Location`,
`Event`, and `Product`) and one relation, `RELATED_TO`, allowed between any
two of them. Use it to try agrag without writing a schema.
