---
title: agrag.ingestion.resolved_entities.ResolvedEntityWriteError
sidebar_label: ResolvedEntityWriteError
---

# `agrag.ingestion.resolved_entities.ResolvedEntityWriteError` \{#agrag-ingestion-resolved_entities-ResolvedEntityWriteError}

Bases: <code>Exception</code>

A job wrote its match edges but not the resolved entity built from them.

The edges carry the job's tag. Committing the job would publish matches
whose resolved entity is missing, so the job must fail as a whole under
every error policy.
