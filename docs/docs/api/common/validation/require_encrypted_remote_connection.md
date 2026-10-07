---
title: agrag.common.validation.require_encrypted_remote_connection
sidebar_label: require_encrypted_remote_connection
---

# `agrag.common.validation.require_encrypted_remote_connection` \{#agrag-common-validation-require_encrypted_remote_connection}

```python
require_encrypted_remote_connection(*, url:str, has_credential:bool, encrypted_schemes:Collection[str], require_encryption:bool = False) -> None
```

Reject a plaintext connection to a non-local host carrying a credential.

A scheme outside `encrypted_schemes` sends everything on the
connection, including any configured credential, unencrypted. That is
the normal, safe shape of local development against a Docker Compose
service on localhost, but the same plaintext default pointed at a real
remote host would leak credentials and data to network interception.
Loopback hosts are always allowed, regardless of scheme or credential.

Without `require_encryption`, a connection carrying no credential is
always allowed: many production deployments run an unauthenticated
backend on a private network (a VPC, a cluster-internal service) and
rely on network segmentation rather than transport encryption, and this
check cannot distinguish that from a public host from the URL alone.
`require_encryption` opts a deployment out of that default, for a
stricter posture where every non-local connection must be encrypted
regardless of credential.

**Parameters:**

- **url** (<code>str</code>) – The connection URL or URI to check.
- **has_credential** (<code>bool</code>) – Whether a credential (API key, token, password) is
  configured for this connection.
- **encrypted_schemes** (<code>Collection\[str\]</code>) – The URL schemes considered encrypted for this
  backend, for example `{"https"}` or `{"bolt+s", "neo4j+s"}`.
- **require_encryption** (<code>bool</code>) – When `True`, reject plaintext to a non-local
  host even without a configured credential.

**Raises:**

- <code>ValueError</code> – `url` uses a scheme outside `encrypted_schemes`, its
  host is not loopback, and either `has_credential` or
  `require_encryption` is `True`.
