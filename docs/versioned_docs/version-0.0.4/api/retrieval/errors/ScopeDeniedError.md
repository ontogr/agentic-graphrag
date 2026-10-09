---
title: agrag.retrieval.errors.ScopeDeniedError
sidebar_label: ScopeDeniedError
---

# `agrag.retrieval.errors.ScopeDeniedError` \{#agrag-retrieval-errors-ScopeDeniedError}

Bases: <code>[RetrievalError](RetrievalError.md)</code>

A request asked for data outside the caller's permitted scope.

The caller's scope is an authorization boundary the requesting
layer can narrow but never widen. Raised instead of searching the
wider scope or silently running the request unrestricted, so a
caller can report the refusal rather than answer from data it was
never allowed to see.
