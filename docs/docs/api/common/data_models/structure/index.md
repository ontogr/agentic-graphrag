---
title: agrag.common.data_models.structure
sidebar_label: structure
---

# `agrag.common.data_models.structure` \{#agrag-common-data_models-structure}

Stable keys, node ids, reading order and ancestry for the sections of a Document.

**Functions:**

- [**ancestors**](ancestors.md) – Return the index of a section and of each section above it.
- [**chunk_id**](chunk_id.md) – Return the id of a chunk.
- [**common_ancestor**](common_ancestor.md) – Return the lowest section that contains all the given sections.
- [**heading_paths**](heading_paths.md) – Return the non-empty headings from the top to each section.
- [**node_id**](node_id.md) – Return the id of the node that holds `key` in one document version.
- [**reading_positions**](reading_positions.md) – Number every heading and unit of a document in reading order.
- [**section_keys**](section_keys.md) – Return one stable key for each section.
- [**source_node_id**](source_node_id.md) – Return the id of the Source node for a file.
- [**unit_keys**](unit_keys.md) – Return a stable key for each table and figure.
- [**version_id**](version_id.md) – Return the id of one version of a document, as `PART_OF` edges use it.

**Attributes:**

- [**FIGURE_LABEL**](FIGURE_LABEL.md) –
- [**HAS_CHILD**](HAS_CHILD.md) –
- [**HAS_DOCUMENT**](HAS_DOCUMENT.md) –
- [**PART_OF**](PART_OF.md) –
- [**SECTION_LABEL**](SECTION_LABEL.md) –
- [**SOURCE_LABEL**](SOURCE_LABEL.md) –
- [**TABLE_LABEL**](TABLE_LABEL.md) –
