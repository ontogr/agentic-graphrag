---
title: agrag.agents.middleware
sidebar_label: middleware
---

# `agrag.agents.middleware` \{#agrag-agents-middleware}

Agent middleware for composing models and bounding the research loop.

**Classes:**

- [**HideToolsMiddleware**](HideToolsMiddleware.md) – Remove tools by name from every model request.
- [**RequireVerdictMiddleware**](RequireVerdictMiddleware.md) – Ask again when the verifier answers in prose instead of with its verdict.
- [**ResearchAttemptLimiter**](ResearchAttemptLimiter.md) – Cap how many times the planner may re-delegate after verification.
- [**RoundRobinModelMiddleware**](RoundRobinModelMiddleware.md) – Rotate across the configured chat models, one model per call.
- [**VerifierEvidenceMiddleware**](VerifierEvidenceMiddleware.md) – Give the verifier the evidence text behind each key a task cites.
