---
title: agrag.retrieval.ScopeDeniedError
sidebar_label: ScopeDeniedError
---

# `agrag.retrieval.ScopeDeniedError` \{#agrag-retrieval-ScopeDeniedError}

Bases: <code>[RetrievalError](errors/RetrievalError.md)</code>

A request asked for data outside the caller's permitted scope.

The caller's scope is an authorization boundary the requesting
layer can narrow but never widen. Raised instead of searching the
wider scope or silently running the request unrestricted, so a
caller can report the refusal rather than answer from data it was
never allowed to see.
