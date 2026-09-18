---
title: API Reference
sidebar_position: 2
---

## `agrag`

Agentic GraphRAG: graph-based RAG with agentic reasoning.

**Modules:**

- [**agents**](#agrag.agents) – Agentic layer: planner/researcher/verifier over SearchEngine.
- [**chunking**](#agrag.chunking) – Chunking helpers for the ingestion layer.
- [**common**](#agrag.common) – Common utilities and data models shared across agrag.
- [**cypher**](#agrag.cypher) – Cypher query builders for graph stores.
- [**embedding**](#agrag.embedding) – Text embedding: turn strings into dense vectors.
- [**graphdb**](#agrag.graphdb) – Graph storage backends and the build shortcut.
- [**ingestion**](#agrag.ingestion) – The ingestion package.
- [**observability**](#agrag.observability) – OpenTelemetry wiring for the ingestion layer.
- [**retrieval**](#agrag.retrieval) – Retrieval package: search engine, fusion, reranking, and retrievers.
- [**vectordb**](#agrag.vectordb) – Vector storage backends and the build shortcut.

### `agrag.agents`

Agentic layer: planner/researcher/verifier over SearchEngine.

**Modules:**

- [**build**](#agrag.agents.build) – Build the planner/researcher/verifier agent graph.
- [**ledger**](#agrag.agents.ledger) – Citation ledger: assigns and tracks stable keys for one agent run.
- [**middleware**](#agrag.agents.middleware) – Agent middleware for composing multiple chat models per strategy.
- [**model**](#agrag.agents.model) – Translate LLMClientConfig into the matching LangChain chat model.
- [**prompts**](#agrag.agents.prompts) – Agent prompt templates for planner, researcher, verifier.
- [**settings**](#agrag.agents.settings) – Env-backed LLM and loop config for the agent layer.
- [**subagents**](#agrag.agents.subagents) – Subagent definitions: planner, researcher, verifier.
- [**tools**](#agrag.agents.tools) – Agent tools: thin wrappers calling SearchEngine with fixed Recipes.

#### `agrag.agents.build`

Build the planner/researcher/verifier agent graph.

**Functions:**

- [**build_agent**](#agrag.agents.build.build_agent) – Build the planner/researcher/verifier agent graph.

##### `agrag.agents.build.build_agent`

```python
build_agent(*, engine:SearchEngine, llm_settings:AgentLLMSettings, agent_settings:AgentSettings | None = None, filters:SearchFilters | None = None) -> Any
```

Build the planner/researcher/verifier agent graph.

Constructs a LangGraph-based agent with three roles:
planner (decomposes the question), researcher (has tools),
and verifier (judges evidence sufficiency).

Each call to `ainvoke` creates a fresh `Ledger` so
citation numbering, identity mappings, and retrieved evidence
do not leak across runs.

**Parameters:**

- **engine** (<code>[SearchEngine](#agrag.retrieval.search_engine.SearchEngine)</code>) – Retrieval to expose to the researcher subagent's
  tools.
- **llm_settings** (<code>[AgentLLMSettings](#agrag.agents.settings.AgentLLMSettings)</code>) – The model every subagent role calls, via
  build_chat_model. With several clients, the remaining
  ones compose per strategy through agent middleware.
- **agent_settings** (<code>[AgentSettings](#agrag.agents.settings.AgentSettings) | None</code>) – Loop-level configuration; defaults from
  environment. The recursion limit is enforced as the
  LangGraph `recursion_limit` in the invoke config.
- **filters** (<code>[SearchFilters](#agrag.retrieval.filters.SearchFilters) | None</code>) – Retrieval scope applied to every tool search,
  e.g. document or tenant constraints. None searches
  unfiltered.

**Returns:**

- <code>[Any](#typing.Any)</code> – A compiled agent graph ready for invoke/ainvoke, or a
- <code>[Any](#typing.Any)</code> – simple single-search fallback when deepagents is not
- <code>[Any](#typing.Any)</code> – installed.

#### `agrag.agents.ledger`

Citation ledger: assigns and tracks stable keys for one agent run.

**Classes:**

- [**Ledger**](#agrag.agents.ledger.Ledger) – Assigns and tracks stable citation keys for one agent run.

##### `agrag.agents.ledger.Ledger`

```python
Ledger() -> None
```

Assigns and tracks stable citation keys for one agent run.

A key (E1, R1, C1 for entities, relations, and chunks) is
assigned the first time this run encounters that item, by
SearchResult.identity_key, and never reassigned within the run.
The agent is shown rendered evidence carrying these keys, never
raw SearchResults.

**Functions:**

- [**cite**](#agrag.agents.ledger.Ledger.cite) – Return this result's citation key, assigning one if new.
- [**render**](#agrag.agents.ledger.Ledger.render) – Return the markdown-with-key text the agent sees.
- [**resolve**](#agrag.agents.ledger.Ledger.resolve) – Return the SearchResult behind a citation key.

**Attributes:**

- [**keys**](#agrag.agents.ledger.Ledger.keys) (<code>[list](#list)\[[str](#str)\]</code>) – Return all citation keys assigned so far.

###### `agrag.agents.ledger.Ledger.cite`

```python
cite(result:SearchResult) -> str
```

Return this result's citation key, assigning one if new.

**Parameters:**

- **result** (<code>[SearchResult](#agrag.common.data_models.search_result.SearchResult)</code>) – The SearchResult to assign a key to.

**Returns:**

- <code>[str](#str)</code> – The citation key (e.g. `E1`, `C3`).

###### `agrag.agents.ledger.Ledger.keys`

```python
keys: list[str]
```

Return all citation keys assigned so far.

###### `agrag.agents.ledger.Ledger.render`

```python
render(result:SearchResult) -> str
```

Return the markdown-with-key text the agent sees.

**Parameters:**

- **result** (<code>[SearchResult](#agrag.common.data_models.search_result.SearchResult)</code>) – The SearchResult to render.

**Returns:**

- <code>[str](#str)</code> – Markdown text with the citation key and item summary.

###### `agrag.agents.ledger.Ledger.resolve`

```python
resolve(key:str) -> SearchResult | None
```

Return the SearchResult behind a citation key.

**Parameters:**

- **key** (<code>[str](#str)</code>) – The citation key to look up.

**Returns:**

- <code>[SearchResult](#agrag.common.data_models.search_result.SearchResult) | None</code> – The SearchResult, or None if the key is unknown.

#### `agrag.agents.middleware`

Agent middleware for composing multiple chat models per strategy.

**Classes:**

- [**RoundRobinModelMiddleware**](#agrag.agents.middleware.RoundRobinModelMiddleware) – Rotate across the configured chat models, one model per call.

##### `agrag.agents.middleware.RoundRobinModelMiddleware`

```python
RoundRobinModelMiddleware(models:list[Any]) -> None
```

Bases: <code>[AgentMiddleware](#langchain.agents.middleware.types.AgentMiddleware)</code>

Rotate across the configured chat models, one model per call.

Overrides the request's model on every model call so requests are
distributed across all configured clients in order.

**Functions:**

- [**awrap_model_call**](#agrag.agents.middleware.RoundRobinModelMiddleware.awrap_model_call) – Run the call against the next model in rotation.
- [**wrap_model_call**](#agrag.agents.middleware.RoundRobinModelMiddleware.wrap_model_call) – Run the call against the next model in rotation.

**Parameters:**

- **models** (<code>[list](#list)\[[Any](#typing.Any)\]</code>) – Chat models to rotate across, in configuration
  order. Must be non-empty.

**Raises:**

- <code>[ValueError](#ValueError)</code> – models is empty.

###### `agrag.agents.middleware.RoundRobinModelMiddleware.awrap_model_call`

```python
awrap_model_call(request:ModelRequest, handler:Callable[[ModelRequest], Awaitable[ModelResponse]]) -> Any
```

Run the call against the next model in rotation.

###### `agrag.agents.middleware.RoundRobinModelMiddleware.wrap_model_call`

```python
wrap_model_call(request:ModelRequest, handler:Callable[[ModelRequest], ModelResponse]) -> Any
```

Run the call against the next model in rotation.

#### `agrag.agents.model`

Translate LLMClientConfig into the matching LangChain chat model.

**Classes:**

- [**UnsupportedAgentProviderError**](#agrag.agents.model.UnsupportedAgentProviderError) – Raised when a provider has no agent-side mapping yet.

**Functions:**

- [**build_chat_model**](#agrag.agents.model.build_chat_model) – Translate one LLMClientConfig into a LangChain chat model.
- [**build_model_middleware**](#agrag.agents.model.build_model_middleware) – Build agent middleware composing multiple clients per strategy.

##### `agrag.agents.model.UnsupportedAgentProviderError`

Bases: <code>[Exception](#Exception)</code>

Raised when a provider has no agent-side mapping yet.

##### `agrag.agents.model.build_chat_model`

```python
build_chat_model(config:LLMClientConfig) -> Any
```

Translate one LLMClientConfig into a LangChain chat model.

Covers anthropic, openai, openai-generic (mapped to ChatOpenAI
with base_url set), and google-ai. The remaining LLMProvider
values are valid for BAML but have no agent-side mapping yet.

**Parameters:**

- **config** (<code>[LLMClientConfig](#agrag.llm.client_config.LLMClientConfig)</code>) – The provider, model, api_key, and base_url to use.

**Returns:**

- <code>[Any](#typing.Any)</code> – A constructed, ready-to-call BaseChatModel.

**Raises:**

- <code>[UnsupportedAgentProviderError](#agrag.agents.model.UnsupportedAgentProviderError)</code> – config.provider has no
  agent-side mapping.

##### `agrag.agents.model.build_model_middleware`

```python
build_model_middleware(clients:list[LLMClientConfig], *, strategy:Literal['single', 'fallback', 'round_robin'] = 'single') -> list[Any]
```

Build agent middleware composing multiple clients per strategy.

The agent calls `clients[0]` as its primary model. With more than
one client, the returned middleware teaches the agent loop to use
the rest: `"fallback"` tries the other clients in order when the
primary model call fails, and `"round_robin"` rotates across
every client per model call.

**Parameters:**

- **clients** (<code>[list](#list)\[[LLMClientConfig](#agrag.llm.client_config.LLMClientConfig)\]</code>) – The configured clients, in priority order.
- **strategy** (<code>[Literal](#typing.Literal)['single', 'fallback', 'round_robin']</code>) – How to compose `clients`. `"single"` ignores all
  but the first client.

**Returns:**

- <code>[list](#list)\[[Any](#typing.Any)\]</code> – Middleware for create_deep_agent/create_agent; empty when there
- <code>[list](#list)\[[Any](#typing.Any)\]</code> – is nothing to compose.

**Raises:**

- <code>[UnsupportedAgentProviderError](#agrag.agents.model.UnsupportedAgentProviderError)</code> – a client's provider has no
  agent-side mapping.

#### `agrag.agents.prompts`

Agent prompt templates for planner, researcher, verifier.

**Attributes:**

- [**PLANNER_SYSTEM**](#agrag.agents.prompts.PLANNER_SYSTEM) –
- [**RESEARCHER_SYSTEM**](#agrag.agents.prompts.RESEARCHER_SYSTEM) –
- [**VERIFIER_SYSTEM**](#agrag.agents.prompts.VERIFIER_SYSTEM) –

##### `agrag.agents.prompts.PLANNER_SYSTEM`

```python
PLANNER_SYSTEM = 'You are a research planner. Given a user question, decompose it into 2-4 focused sub-questions that a researcher can answer by searching a knowledge graph. Each sub-question should be specific and answerable independently.\n\nReturn your sub-questions as a numbered list.'
```

##### `agrag.agents.prompts.RESEARCHER_SYSTEM`

```python
RESEARCHER_SYSTEM = 'You are a researcher with access to a knowledge graph. Use the available tools to find evidence for each sub-question. Cite every claim with the citation keys (E1, C3, etc.) returned by tools. Base your answer only on evidence found through tools, not on general knowledge.\n\nWhen you have gathered enough evidence, provide a concise answer with citations.'
```

##### `agrag.agents.prompts.VERIFIER_SYSTEM`

```python
VERIFIER_SYSTEM = "You are an evidence verifier. Given a question, a set of sub-questions, and the researcher's evidence, check:\n1. Every sub-question has at least one citation.\n2. Every citation key resolves to real evidence.\n3. The answer directly addresses the original question.\n\nIf evidence is sufficient, say PASS. If not, list what is missing."
```

#### `agrag.agents.settings`

Env-backed LLM and loop config for the agent layer.

**Classes:**

- [**AgentLLMSettings**](#agrag.agents.settings.AgentLLMSettings) – LLM client config for the agent's own reasoning turns.
- [**AgentSettings**](#agrag.agents.settings.AgentSettings) – Configuration for the agent loop itself.

##### `agrag.agents.settings.AgentLLMSettings`

Bases: <code>[BaseSettings](#pydantic_settings.BaseSettings)</code>

LLM client config for the agent's own reasoning turns.

Mirrors ExtractionLLMSettings for the agent role: same shape,
same from_openai_compatible_env() convention, because the
agent's model and the extraction model are configured the same
way even though the agent calls its model through LangChain,
not BAML.

**Attributes:**

- [**clients**](#agrag.agents.settings.AgentLLMSettings.clients) (<code>[list](#list)\[[LLMClientConfig](#agrag.llm.client_config.LLMClientConfig)\]</code>) – The LLM client(s) to use. One element for a single
  provider; more than one composed per strategy through
  agent middleware.
- [**strategy**](#agrag.agents.settings.AgentLLMSettings.strategy) (<code>[Literal](#typing.Literal)['single', 'fallback', 'round_robin']</code>) – How to compose multiple clients. `"fallback"`
  tries the other clients in order when a model call fails;
  `"round_robin"` rotates across all clients per call.
  Ignored with one client.

Env prefix: `AGENT_LLM_`.

**Functions:**

- [**from_openai_compatible_env**](#agrag.agents.settings.AgentLLMSettings.from_openai_compatible_env) – Build settings from OpenAI-compatible env vars.

###### `agrag.agents.settings.AgentLLMSettings.clients`

```python
clients: list[LLMClientConfig]
```

###### `agrag.agents.settings.AgentLLMSettings.from_openai_compatible_env`

```python
from_openai_compatible_env() -> AgentLLMSettings
```

Build settings from OpenAI-compatible env vars.

Loads `.env` first, then reads `AGENT_LLM_BASE_URL`,
`AGENT_LLM_API_KEY`, and `AGENT_LLM_MODEL_ID`. When the
agent-specific variables are unset, the shared `LLM_*`
convenience variables used by the extraction role stand in, so
one `.env` can configure every LLM-backed role. The model
name defaults to `gpt-4o-mini` when neither variable names
one.

**Returns:**

- <code>[AgentLLMSettings](#agrag.agents.settings.AgentLLMSettings)</code> – AgentLLMSettings with one openai-generic client.

###### `agrag.agents.settings.AgentLLMSettings.model_config`

```python
model_config = SettingsConfigDict(env_prefix='AGENT_LLM_', env_file='.env', extra='ignore')
```

###### `agrag.agents.settings.AgentLLMSettings.strategy`

```python
strategy: Literal['single', 'fallback', 'round_robin'] = 'single'
```

##### `agrag.agents.settings.AgentSettings`

Bases: <code>[BaseSettings](#pydantic_settings.BaseSettings)</code>

Configuration for the agent loop itself.

**Attributes:**

- [**recursion_limit**](#agrag.agents.settings.AgentSettings.recursion_limit) (<code>[int](#int)</code>) – The maximum LangGraph step count before
  the loop stops and reports incomplete progress.

Env prefix: `AGENT_`.

###### `agrag.agents.settings.AgentSettings.model_config`

```python
model_config = SettingsConfigDict(env_prefix='AGENT_', env_file='.env', extra='ignore')
```

###### `agrag.agents.settings.AgentSettings.recursion_limit`

```python
recursion_limit: int = 50
```

#### `agrag.agents.subagents`

Subagent definitions: planner, researcher, verifier.

**Functions:**

- [**make_planner_prompt**](#agrag.agents.subagents.make_planner_prompt) – Return the planner subagent config.
- [**make_researcher_prompt**](#agrag.agents.subagents.make_researcher_prompt) – Return the researcher subagent config.
- [**make_verifier_prompt**](#agrag.agents.subagents.make_verifier_prompt) – Return the verifier subagent config.

##### `agrag.agents.subagents.make_planner_prompt`

```python
make_planner_prompt() -> dict[str, Any]
```

Return the planner subagent config.

**Returns:**

- <code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\]</code> – A dict with system_prompt key for the planner role.

##### `agrag.agents.subagents.make_researcher_prompt`

```python
make_researcher_prompt() -> dict[str, Any]
```

Return the researcher subagent config.

**Returns:**

- <code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\]</code> – A dict with system_prompt key for the researcher role.

##### `agrag.agents.subagents.make_verifier_prompt`

```python
make_verifier_prompt() -> dict[str, Any]
```

Return the verifier subagent config.

**Returns:**

- <code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\]</code> – A dict with system_prompt key for the verifier role.

#### `agrag.agents.tools`

Agent tools: thin wrappers calling SearchEngine with fixed Recipes.

Each tool is a LangChain-compatible callable that deepagents can
register. Tools are named for what the agent is trying to find
out, not for the retrieval method they use.

**Functions:**

- [**make_tools**](#agrag.agents.tools.make_tools) – Build the agent's tool set over one SearchEngine and Ledger.

##### `agrag.agents.tools.make_tools`

```python
make_tools(engine:'SearchEngine', ledger:'Ledger', *, filters:'SearchFilters | None' = None) -> list[Any]
```

Build the agent's tool set over one SearchEngine and Ledger.

**Parameters:**

- **engine** (<code>'SearchEngine'</code>) – The SearchEngine every tool calls.
- **ledger** (<code>'Ledger'</code>) – The citation ledger for one run.
- **filters** (<code>'SearchFilters | None'</code>) – Retrieval scope applied to every tool's search.
  Pass document or tenant constraints here so the agent
  cannot surface graph data outside them; the LLM never
  sees or chooses the scope.

**Returns:**

- <code>[list](#list)\[[Any](#typing.Any)\]</code> – A list of LangChain tool instances: search_source_text,
- <code>[list](#list)\[[Any](#typing.Any)\]</code> – look_up_entity, find_connection, explore_related,
- <code>[list](#list)\[[Any](#typing.Any)\]</code> – answer_from_graph_structure, and answer_thematic_question.

### `agrag.chunking`

Chunking helpers for the ingestion layer.

This module isolates the chonkie dependency to one import site, so the rest of the
codebase (and tests) can build a chunker without importing chonkie directly.

**Modules:**

- [**text**](#agrag.chunking.text) – Splits a text Document into Chunks with the chonkie chunker.

**Classes:**

- [**RecursiveChunker**](#agrag.chunking.RecursiveChunker) – Chunker that recursively splits text into smaller chunks, based on the provided RecursiveRules.

**Functions:**

- [**default_chunker**](#agrag.chunking.default_chunker) – Build the default text chunker.

#### `agrag.chunking.RecursiveChunker`

```python
RecursiveChunker(tokenizer:Union[str, TokenizerProtocol] = 'character', chunk_size:int = 2048, rules:RecursiveRules = RecursiveRules(), min_characters_per_chunk:int = 24) -> None
```

Bases: <code>[BaseChunker](#chonkie.chunker.base.BaseChunker)</code>

Chunker that recursively splits text into smaller chunks, based on the provided RecursiveRules.

**Parameters:**

- **tokenizer** (<code>[Union](#typing.Union)\[[str](#str), [TokenizerProtocol](#chonkie.tokenizer.TokenizerProtocol)\]</code>) – Tokenizer to use
- **chunk_size** (<code>[int](#int)</code>) – Maximum size of each chunk.
- **rules** (<code>[RecursiveRules](#chonkie.types.RecursiveRules)</code>) – Recursive rules to use for chunking.
- **min_characters_per_chunk** (<code>[int](#int)</code>) – Minimum number of characters per chunk.

**Functions:**

- [**achunk**](#agrag.chunking.RecursiveChunker.achunk) – Chunk the given text asynchronously.
- [**achunk_batch**](#agrag.chunking.RecursiveChunker.achunk_batch) – Chunk a batch of texts asynchronously.
- [**achunk_document**](#agrag.chunking.RecursiveChunker.achunk_document) – Chunk a document asynchronously.
- [**chunk**](#agrag.chunking.RecursiveChunker.chunk) – Recursively chunk text.
- [**chunk_batch**](#agrag.chunking.RecursiveChunker.chunk_batch) – Chunk a batch of texts.
- [**chunk_document**](#agrag.chunking.RecursiveChunker.chunk_document) – Chunk a document.
- [**from_recipe**](#agrag.chunking.RecursiveChunker.from_recipe) – Create a RecursiveChunker object from a recipe.

**Attributes:**

- [**chunk_size**](#agrag.chunking.RecursiveChunker.chunk_size) –
- [**min_characters_per_chunk**](#agrag.chunking.RecursiveChunker.min_characters_per_chunk) –
- [**rules**](#agrag.chunking.RecursiveChunker.rules) –
- [**sep**](#agrag.chunking.RecursiveChunker.sep) –
- [**tokenizer**](#agrag.chunking.RecursiveChunker.tokenizer) (<code>[AutoTokenizer](#chonkie.tokenizer.AutoTokenizer)</code>) – Get the tokenizer instance.

**Parameters:**

- **tokenizer** (<code>[Union](#typing.Union)\[[str](#str), [TokenizerProtocol](#chonkie.tokenizer.TokenizerProtocol)\]</code>) – Tokenizer to use
- **chunk_size** (<code>[int](#int)</code>) – Maximum size of each chunk.
- **rules** (<code>[RecursiveRules](#chonkie.types.RecursiveRules)</code>) – Recursive rules to use for chunking.
- **min_characters_per_chunk** (<code>[int](#int)</code>) – Minimum number of characters per chunk.

**Raises:**

- <code>[ValueError](#ValueError)</code> – If chunk_size \<=0
- <code>[ValueError](#ValueError)</code> – If min_characters_per_chunk < 1
- <code>[ValueError](#ValueError)</code> – If rules is not a RecursiveRules object.

##### `agrag.chunking.RecursiveChunker.achunk`

```python
achunk(text:str) -> list[Chunk]
```

Chunk the given text asynchronously.

**Parameters:**

- **text** (<code>[str](#str)</code>) – The text to chunk.

**Returns:**

- <code>[list](#list)\[[Chunk](#chonkie.types.Chunk)\]</code> – list\[Chunk\]: A list of Chunks.

##### `agrag.chunking.RecursiveChunker.achunk_batch`

```python
achunk_batch(texts:Sequence[str], show_progress:bool = True) -> list[list[Chunk]]
```

Chunk a batch of texts asynchronously.

**Parameters:**

- **texts** (<code>[Sequence](#typing.Sequence)\[[str](#str)\]</code>) – The texts to chunk.
- **show_progress** (<code>[bool](#bool)</code>) – Whether to show progress.

**Returns:**

- <code>[list](#list)\[[list](#list)\[[Chunk](#chonkie.types.Chunk)\]\]</code> – list\[list[Chunk]\]: A list of lists of Chunks.

##### `agrag.chunking.RecursiveChunker.achunk_document`

```python
achunk_document(document:Document) -> Document
```

Chunk a document asynchronously.

**Parameters:**

- **document** (<code>[Document](#chonkie.types.Document)</code>) – The document to chunk.

**Returns:**

- <code>[Document](#chonkie.types.Document)</code> – The document with chunks populated.

##### `agrag.chunking.RecursiveChunker.chunk`

```python
chunk(text:str) -> list[Chunk]
```

Recursively chunk text.

**Parameters:**

- **text** (<code>[str](#str)</code>) – Text to chunk.

##### `agrag.chunking.RecursiveChunker.chunk_batch`

```python
chunk_batch(texts:Sequence[str], show_progress:bool = True) -> list[list[Chunk]]
```

Chunk a batch of texts.

**Parameters:**

- **texts** (<code>[Sequence](#typing.Sequence)\[[str](#str)\]</code>) – The texts to chunk.
- **show_progress** (<code>[bool](#bool)</code>) – Whether to show progress.

**Returns:**

- <code>[list](#list)\[[list](#list)\[[Chunk](#chonkie.types.Chunk)\]\]</code> – list\[list[Chunk]\]: A list of lists of Chunks.

##### `agrag.chunking.RecursiveChunker.chunk_document`

```python
chunk_document(document:Document) -> Document
```

Chunk a document.

After chunking, non-empty `document.metadata` is shallow-merged into each
chunk's :attr:`~chonkie.types.Chunk.metadata` (chunk keys override on conflict).

**Parameters:**

- **document** (<code>[Document](#chonkie.types.Document)</code>) – The document to chunk.

**Returns:**

- <code>[Document](#chonkie.types.Document)</code> – The document with chunks populated.

##### `agrag.chunking.RecursiveChunker.chunk_size`

```python
chunk_size = chunk_size
```

##### `agrag.chunking.RecursiveChunker.from_recipe`

```python
from_recipe(name:Optional[str] = 'default', lang:Optional[str] = 'en', path:str | PathLike | None = None, tokenizer:Union[str, TokenizerProtocol] = 'character', chunk_size:int = 2048, min_characters_per_chunk:int = 24) -> RecursiveChunker
```

Create a RecursiveChunker object from a recipe.

The recipes are registered in the [Chonkie Recipe Store](https://huggingface.co/datasets/chonkie-ai/recipes). If the recipe is not there, you can create your own recipe and share it with the community!

**Parameters:**

- **name** (<code>[Optional](#typing.Optional)\[[str](#str)\]</code>) – The name of the recipe.
- **lang** (<code>[Optional](#typing.Optional)\[[str](#str)\]</code>) – The language that the recursive chunker should support.
- **path** (<code>[Optional](#typing.Optional)\[[str](#str)\]</code>) – The path to the recipe.
- **tokenizer** (<code>[Union](#typing.Union)\[[str](#str), [TokenizerProtocol](#chonkie.tokenizer.TokenizerProtocol)\]</code>) – The tokenizer to use.
- **chunk_size** (<code>[int](#int)</code>) – The chunk size.
- **min_characters_per_chunk** (<code>[int](#int)</code>) – The minimum number of characters per chunk.

**Returns:**

- **RecursiveChunker** (<code>[RecursiveChunker](#chonkie.chunker.recursive.RecursiveChunker)</code>) – The RecursiveChunker object.

**Raises:**

- <code>[ValueError](#ValueError)</code> – If the recipe is not found.

##### `agrag.chunking.RecursiveChunker.min_characters_per_chunk`

```python
min_characters_per_chunk = min_characters_per_chunk
```

##### `agrag.chunking.RecursiveChunker.rules`

```python
rules = rules
```

##### `agrag.chunking.RecursiveChunker.sep`

```python
sep = '✄'
```

##### `agrag.chunking.RecursiveChunker.tokenizer`

```python
tokenizer: AutoTokenizer
```

Get the tokenizer instance.

#### `agrag.chunking.default_chunker`

```python
default_chunker(chunk_size:int = 1024) -> RecursiveChunker
```

Build the default text chunker.

**Parameters:**

- **chunk_size** (<code>[int](#int)</code>) – The maximum number of characters per chunk.

**Returns:**

- <code>[RecursiveChunker](#chonkie.RecursiveChunker)</code> – A character-based recursive chunker.

#### `agrag.chunking.text`

Splits a text Document into Chunks with the chonkie chunker.

**Functions:**

- [**chunk_document**](#agrag.chunking.text.chunk_document) – Split a document's text into chunks.
- [**iter_chunk_documents**](#agrag.chunking.text.iter_chunk_documents) – Chunk a stream of documents into a flat stream of chunks.

##### `agrag.chunking.text.chunk_document`

```python
chunk_document(document:Document, chunker:RecursiveChunker) -> list[Chunk]
```

Split a document's text into chunks.

This function computes `line_start` and `line_end` from each chunk's character
span,
because the chunker does not report line numbers. It also sets `heading_path` from
the
document's heading outline.

**Parameters:**

- **document** (<code>[Document](#agrag.common.data_models.document.Document)</code>) – The document to split. This function reads only its `text` and
  `heading_outline` fields.
- **chunker** (<code>[RecursiveChunker](#chonkie.RecursiveChunker)</code>) – The chunker to run.

**Returns:**

- <code>[list](#list)\[[Chunk](#agrag.common.data_models.chunk.Chunk)\]</code> – The chunks, in document order.

##### `agrag.chunking.text.iter_chunk_documents`

```python
iter_chunk_documents(documents:Iterator[Document], chunker:RecursiveChunker) -> Iterator[Chunk]
```

Chunk a stream of documents into a flat stream of chunks.

**Parameters:**

- **documents** (<code>[Iterator](#collections.abc.Iterator)\[[Document](#agrag.common.data_models.document.Document)\]</code>) – The documents to chunk, in order.
- **chunker** (<code>[RecursiveChunker](#chonkie.RecursiveChunker)</code>) – The chunker to run on each document.

**Yields:**

- <code>[Chunk](#agrag.common.data_models.chunk.Chunk)</code> – Each chunk, in document then chunk order.

### `agrag.common`

Common utilities and data models shared across agrag.

**Modules:**

- [**data_models**](#agrag.common.data_models) – Shared data models used by agrag components.
- [**text**](#agrag.common.text) – Shared text normalization used across resolution and merge-key computation.
- [**validation**](#agrag.common.validation) – Validation helpers shared across storage backends.

#### `agrag.common.data_models`

Shared data models used by agrag components.

**Modules:**

- [**chunk**](#agrag.common.data_models.chunk) – The Chunk model: one retrieval-sized piece of a Document.
- [**community**](#agrag.common.data_models.community) – The Community model: a Leiden-detected entity cluster with an LLM report.
- [**data_point**](#agrag.common.data_models.data_point) – The base class for a graph node.
- [**document**](#agrag.common.data_models.document) – The Document model: one unit of source text, before chunking.
- [**entity**](#agrag.common.data_models.entity) – The canonical, resolved graph entity that merge mechanics produces.
- [**extraction**](#agrag.common.data_models.extraction) – Pre-resolution entity and relation mentions produced by an Extractor.
- [**graph_record**](#agrag.common.data_models.graph_record) – Graph storage record shapes for GraphStore.
- [**graph_schema**](#agrag.common.data_models.graph_schema) – The GraphSchema contract: entity and relation types extraction validates against.
- [**provenance**](#agrag.common.data_models.provenance) – Provenance types for a chunk.
- [**relation**](#agrag.common.data_models.relation) – The canonical, deduped graph relationship that merge mechanics produces.
- [**search_result**](#agrag.common.data_models.search_result) – One retrieved item, tagged with source and relevance score.
- [**vector_record**](#agrag.common.data_models.vector_record) – Vector storage record shapes shared by VectorStore and GraphStore.

##### `agrag.common.data_models.chunk`

The Chunk model: one retrieval-sized piece of a Document.

**Classes:**

- [**Chunk**](#agrag.common.data_models.chunk.Chunk) – One retrieval-sized piece of a Document.

**Attributes:**

- [**CHUNK_LABEL**](#agrag.common.data_models.chunk.CHUNK_LABEL) –

###### `agrag.common.data_models.chunk.CHUNK_LABEL`

```python
CHUNK_LABEL = 'Chunk'
```

###### `agrag.common.data_models.chunk.Chunk`

Bases: <code>[DataPoint](#agrag.common.data_models.data_point.DataPoint)</code>

One retrieval-sized piece of a Document.

**Attributes:**

- [**document_id**](#agrag.common.data_models.chunk.Chunk.document_id) (<code>[UUID](#uuid.UUID)</code>) – The id of the parent Document. Use this id to look up fields
  such as `record_index` on the parent Document.
- [**index**](#agrag.common.data_models.chunk.Chunk.index) (<code>[int](#int)</code>) – The position of the chunk within its document, from 0.
- [**text**](#agrag.common.data_models.chunk.Chunk.text) (<code>[str](#str)</code>) – The chunk text.
- [**provenance**](#agrag.common.data_models.chunk.Chunk.provenance) (<code>[TextProvenance](#agrag.common.data_models.provenance.TextProvenance) | [PageProvenance](#agrag.common.data_models.provenance.PageProvenance)</code>) – The location of this chunk in its source. The shape of this
  value depends on which chunker made the chunk.
- [**heading_path**](#agrag.common.data_models.chunk.Chunk.heading_path) (<code>[list](#list)\[[str](#str)\]</code>) – The headings that contain this chunk, from outermost to innermost.
  Empty for a docling chunk and for a chunk with no heading above it.
- [**content_kind**](#agrag.common.data_models.chunk.Chunk.content_kind) (<code>[Literal](#typing.Literal)['text', 'table_row', 'code', 'heading']</code>) – The kind of content in this chunk. A text chunker always sets
  `"text"`. A docling chunk can also be `"table_row"`.

**Functions:**

- [**id_for**](#agrag.common.data_models.chunk.Chunk.id_for) – Compute the chunk id.
- [**to_node_record**](#agrag.common.data_models.chunk.Chunk.to_node_record) – Return this chunk as a GraphStore write record.

####### `agrag.common.data_models.chunk.Chunk.content_kind`

```python
content_kind: Literal['text', 'table_row', 'code', 'heading'] = 'text'
```

####### `agrag.common.data_models.chunk.Chunk.created_at`

```python
created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

####### `agrag.common.data_models.chunk.Chunk.document_id`

```python
document_id: UUID
```

####### `agrag.common.data_models.chunk.Chunk.embedding`

```python
embedding: list[float] | None = None
```

####### `agrag.common.data_models.chunk.Chunk.heading_path`

```python
heading_path: list[str] = Field(default_factory=list)
```

####### `agrag.common.data_models.chunk.Chunk.id`

```python
id: UUID | None = None
```

####### `agrag.common.data_models.chunk.Chunk.id_for`

```python
id_for(*, document_id:UUID, version_id:UUID | None = None, provenance:TextProvenance | PageProvenance, index:int) -> UUID
```

Compute the chunk id.

For a text chunk, the id comes from the document id and the character span. A
change in chunk size shifts the span, so it also changes the id. When supplied,
`version_id` makes the id distinct for each version of a document.

For a docling chunk, the id comes from the document id and the chunk index
instead. Docling parsing is not always the same between runs, so this id is
not stable across a re-parse of the same source.

**Parameters:**

- **document_id** (<code>[UUID](#uuid.UUID)</code>) – The id of the parent Document.
- **version_id** (<code>[UUID](#uuid.UUID) | None</code>) – Optional id for the parent document version.
- **provenance** (<code>[TextProvenance](#agrag.common.data_models.provenance.TextProvenance) | [PageProvenance](#agrag.common.data_models.provenance.PageProvenance)</code>) – The provenance of the chunk. Its type picks which id rule
  applies.
- **index** (<code>[int](#int)</code>) – The position of the chunk within its document.

**Returns:**

- <code>[UUID](#uuid.UUID)</code> – The chunk id.

####### `agrag.common.data_models.chunk.Chunk.index`

```python
index: int = 0
```

####### `agrag.common.data_models.chunk.Chunk.metadata`

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

####### `agrag.common.data_models.chunk.Chunk.provenance`

```python
provenance: TextProvenance | PageProvenance = Field(discriminator='kind')
```

####### `agrag.common.data_models.chunk.Chunk.text`

```python
text: str
```

####### `agrag.common.data_models.chunk.Chunk.to_node_record`

```python
to_node_record() -> NodeRecord
```

Return this chunk as a GraphStore write record.

Provenance is flattened to a plain JSON-safe dict via model_dump —
GraphStore's own serialize.node_params only converts UUIDs and walks
containers.

**Raises:**

- <code>[ValueError](#ValueError)</code> – id is None.

##### `agrag.common.data_models.community`

The Community model: a Leiden-detected entity cluster with an LLM report.

**Classes:**

- [**Community**](#agrag.common.data_models.community.Community) – A cluster of entities detected by hierarchical Leiden, with an LLM report.

**Attributes:**

- [**COMMUNITY_LABEL**](#agrag.common.data_models.community.COMMUNITY_LABEL) –
- [**MEMBER_OF_RELATION**](#agrag.common.data_models.community.MEMBER_OF_RELATION) –

###### `agrag.common.data_models.community.COMMUNITY_LABEL`

```python
COMMUNITY_LABEL = 'Community'
```

###### `agrag.common.data_models.community.Community`

Bases: <code>[DataPoint](#agrag.common.data_models.data_point.DataPoint)</code>

A cluster of entities detected by hierarchical Leiden, with an LLM report.

**Attributes:**

- [**title**](#agrag.common.data_models.community.Community.title) (<code>[str](#str)</code>) – A short, human-readable name for the community.
- [**summary**](#agrag.common.data_models.community.Community.summary) (<code>[str](#str)</code>) – A prose summary of what the community is about.
- [**rating**](#agrag.common.data_models.community.Community.rating) (<code>[float](#float)</code>) – An importance rating for this community, 0-10.
- [**rating_explanation**](#agrag.common.data_models.community.Community.rating_explanation) (<code>[str](#str)</code>) – One sentence explaining the rating.
- [**findings**](#agrag.common.data_models.community.Community.findings) (<code>[list](#list)\[[str](#str)\]</code>) – Distinct factual claims the report supports.
- [**member_ids**](#agrag.common.data_models.community.Community.member_ids) (<code>[list](#list)\[[UUID](#uuid.UUID)\]</code>) – Ids of every Entity in this community, ordered by
  internal weighted degree descending (see compute_communities) --
  the highest-centrality, most representative members first.
- [**internal_weight**](#agrag.common.data_models.community.Community.internal_weight) (<code>[float](#float)</code>) – Total weight of edges where both endpoints are
  members of this community. A free-to-compute (no extra query,
  no new dependency) importance signal, used in place of raw
  member count to decide which communities get a real LLM report
  -- a small but densely-attested community can matter more than
  a larger sparse one.
- [**embedding**](#agrag.common.data_models.community.Community.embedding) (<code>[list](#list)\[[float](#float)\] | None</code>) – The community's dense vector, computed from title and
  summary. None before the report/embedding stage runs.

**Functions:**

- [**to_node_record**](#agrag.common.data_models.community.Community.to_node_record) – Return this community as a GraphStore write record.

####### `agrag.common.data_models.community.Community.created_at`

```python
created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

####### `agrag.common.data_models.community.Community.embedding`

```python
embedding: list[float] | None = None
```

####### `agrag.common.data_models.community.Community.embedding_text`

```python
embedding_text: str
```

Return the text this community's embedding is computed from.

####### `agrag.common.data_models.community.Community.findings`

```python
findings: list[str] = Field(default_factory=list)
```

####### `agrag.common.data_models.community.Community.id`

```python
id: UUID
```

####### `agrag.common.data_models.community.Community.internal_weight`

```python
internal_weight: float = Field(default=0.0, ge=0.0)
```

####### `agrag.common.data_models.community.Community.member_ids`

```python
member_ids: list[UUID] = Field(default_factory=list)
```

####### `agrag.common.data_models.community.Community.metadata`

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

####### `agrag.common.data_models.community.Community.rating`

```python
rating: float = Field(ge=0.0, le=10.0)
```

####### `agrag.common.data_models.community.Community.rating_explanation`

```python
rating_explanation: str
```

####### `agrag.common.data_models.community.Community.summary`

```python
summary: str
```

####### `agrag.common.data_models.community.Community.title`

```python
title: str
```

####### `agrag.common.data_models.community.Community.to_node_record`

```python
to_node_record() -> NodeRecord
```

Return this community as a GraphStore write record.

###### `agrag.common.data_models.community.MEMBER_OF_RELATION`

```python
MEMBER_OF_RELATION = 'MEMBER_OF'
```

##### `agrag.common.data_models.data_point`

The base class for a graph node.

**Classes:**

- [**DataPoint**](#agrag.common.data_models.data_point.DataPoint) – A graph node with a fixed id and free metadata.

###### `agrag.common.data_models.data_point.DataPoint`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

A graph node with a fixed id and free metadata.

**Attributes:**

- [**id**](#agrag.common.data_models.data_point.DataPoint.id) (<code>[UUID](#uuid.UUID)</code>) – The node id. Each subclass defines its own rule to compute this id.
- [**created_at**](#agrag.common.data_models.data_point.DataPoint.created_at) (<code>[datetime](#datetime.datetime)</code>) – The time the system created this node. Defaults to the current time.
- [**metadata**](#agrag.common.data_models.data_point.DataPoint.metadata) (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\]</code>) – Extra data about the node. Add an `index_fields` key to list
  which fields the store must index for filters.

####### `agrag.common.data_models.data_point.DataPoint.created_at`

```python
created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

####### `agrag.common.data_models.data_point.DataPoint.id`

```python
id: UUID
```

####### `agrag.common.data_models.data_point.DataPoint.metadata`

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

##### `agrag.common.data_models.document`

The Document model: one unit of source text, before chunking.

**Classes:**

- [**Document**](#agrag.common.data_models.document.Document) – One unit of source text, before chunking.
- [**DocumentFamily**](#agrag.common.data_models.document.DocumentFamily) – The shape of a document's source.
- [**HeadingRef**](#agrag.common.data_models.document.HeadingRef) – One heading in a document outline.
- [**SourceFormat**](#agrag.common.data_models.document.SourceFormat) – A source format that a loader can read.

**Attributes:**

- [**DOCUMENT_LABEL**](#agrag.common.data_models.document.DOCUMENT_LABEL) –

###### `agrag.common.data_models.document.DOCUMENT_LABEL`

```python
DOCUMENT_LABEL = 'Document'
```

###### `agrag.common.data_models.document.Document`

Bases: <code>[DataPoint](#agrag.common.data_models.data_point.DataPoint)</code>

One unit of source text, before chunking.

A prose source, such as a Markdown file, makes one Document. A record source,
such as a CSV file, makes one Document per row.

The way the system computes `content_hash` depends on the loader. A text
loader hashes the decoded text. A docling loader hashes the raw source bytes
instead of the parsed output, because docling's parsed output can change
between docling versions and between runs on different hardware.

The system computes `id` from `content_hash` and `record_id` unless the caller
passes `id` directly. A record-family document without `record_id` also mixes
in `record_index` plus `source_hash`, or `uri` when `source_hash` is not
set. Pass `id` only when rebuilding a document from stored data.

**Attributes:**

- [**text**](#agrag.common.data_models.document.Document.text) (<code>[str](#str)</code>) – The document text. For a docling source, this holds docling's Markdown
  export. The chunker never reads this field for a docling source; see the
  `Chunk` model for docling chunk content instead.
- [**title**](#agrag.common.data_models.document.Document.title) (<code>[str](#str)</code>) – The document title.
- [**uri**](#agrag.common.data_models.document.Document.uri) (<code>[str](#str)</code>) – The location of the source. This value is not part of the document id.
- [**source_format**](#agrag.common.data_models.document.Document.source_format) (<code>[SourceFormat](#agrag.common.data_models.document.SourceFormat)</code>) – The format the loader used to read this document.
- [**family**](#agrag.common.data_models.document.Document.family) (<code>[DocumentFamily](#agrag.common.data_models.document.DocumentFamily)</code>) – The shape of the source: one document per file, or one document per
  record.
- [**content_hash**](#agrag.common.data_models.document.Document.content_hash) (<code>[str](#str)</code>) – The hash that forms the document id.
- [**loader_name**](#agrag.common.data_models.document.Document.loader_name) (<code>[str](#str)</code>) – The name of the loader that produced this document, for example
  `"text"` or `"docling"`.
- [**loader_version**](#agrag.common.data_models.document.Document.loader_version) (<code>[str](#str) | None</code>) – The version of the loader package. Does not affect the
  document id.
- [**encoding**](#agrag.common.data_models.document.Document.encoding) (<code>[str](#str) | None</code>) – The text encoding. Text loaders set this field; other loaders
  leave it empty.
- [**source_hash**](#agrag.common.data_models.document.Document.source_hash) (<code>[str](#str) | None</code>) – The hash of the whole source file. Record-family documents set
  this field.
- [**char_count**](#agrag.common.data_models.document.Document.char_count) (<code>[int](#int)</code>) – The number of characters in `text`.
- [**line_count**](#agrag.common.data_models.document.Document.line_count) (<code>[int](#int) | None</code>) – The number of lines in `text`. Some loaders do not set this field.
- [**record_index**](#agrag.common.data_models.document.Document.record_index) (<code>[int](#int) | None</code>) – The 0-based row number in the source. Record-family documents
  set this field.
- [**record_id**](#agrag.common.data_models.document.Document.record_id) (<code>[str](#str) | None</code>) – The value from the configured id column. Record-family documents
  set this field only when the caller configures an id column.
- [**raw_record**](#agrag.common.data_models.document.Document.raw_record) (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – The original record data. A loader sets this field only when the
  caller asks for it.
- [**heading_outline**](#agrag.common.data_models.document.Document.heading_outline) (<code>[list](#list)\[[HeadingRef](#agrag.common.data_models.document.HeadingRef)\]</code>) – The headings in the document, with their offsets. A text
  loader sets this field for a prose document.
- [**document_key**](#agrag.common.data_models.document.Document.document_key) (<code>[str](#str) | None</code>) – The stable identifier for this document's persisted graph node.
  Independent of `id`, which changes with every content edit. Defaults to
  `uri` when not supplied.

**Functions:**

- [**id_for**](#agrag.common.data_models.document.Document.id_for) – Compute the document id.
- [**node_id_for**](#agrag.common.data_models.document.Document.node_id_for) – Compute the persisted Document graph node's id.
- [**to_node_record**](#agrag.common.data_models.document.Document.to_node_record) – Return this document as a GraphStore write record for its graph node.

####### `agrag.common.data_models.document.Document.char_count`

```python
char_count: int
```

####### `agrag.common.data_models.document.Document.content_hash`

```python
content_hash: str
```

####### `agrag.common.data_models.document.Document.created_at`

```python
created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

####### `agrag.common.data_models.document.Document.document_key`

```python
document_key: str | None = None
```

####### `agrag.common.data_models.document.Document.encoding`

```python
encoding: str | None = None
```

####### `agrag.common.data_models.document.Document.family`

```python
family: DocumentFamily
```

####### `agrag.common.data_models.document.Document.heading_outline`

```python
heading_outline: list[HeadingRef] = Field(default_factory=list)
```

####### `agrag.common.data_models.document.Document.id`

```python
id: UUID | None = None
```

####### `agrag.common.data_models.document.Document.id_for`

```python
id_for(*, content_hash:str, record_id:str | None = None, record_index:int | None = None, source_hash:str | None = None, uri:str | None = None) -> UUID
```

Compute the document id.

A record id, when given, wins over the content hash. Without a record id,
a record-family document (`record_index` is not `None`) mixes in its
source hash and row index, so two rows with identical text but no
configured id column still get distinct ids. When the source hash is not
available, this falls back to `uri` so that two different sources still
do not collide.

**Parameters:**

- **content_hash** (<code>[str](#str)</code>) – The document's content hash.
- **record_id** (<code>[str](#str) | None</code>) – The value from the configured id column, when the source has one.
- **record_index** (<code>[int](#int) | None</code>) – The 0-based row number, for a record-family document.
- **source_hash** (<code>[str](#str) | None</code>) – The hash of the whole source file, for a record-family
  document.
- **uri** (<code>[str](#str) | None</code>) – The document's source location, used in place of `source_hash`
  when the caller does not supply one.

**Returns:**

- <code>[UUID](#uuid.UUID)</code> – The document id.

####### `agrag.common.data_models.document.Document.line_count`

```python
line_count: int | None = None
```

####### `agrag.common.data_models.document.Document.loader_name`

```python
loader_name: str
```

####### `agrag.common.data_models.document.Document.loader_version`

```python
loader_version: str | None = None
```

####### `agrag.common.data_models.document.Document.metadata`

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

####### `agrag.common.data_models.document.Document.node_id_for`

```python
node_id_for(*, document_key:str) -> UUID
```

Compute the persisted Document graph node's id.

Distinct from `id_for()`: this id is keyed on `document_key`, not the
content hash, so it stays the same across content changes to the same
logical document. Conflating the two ids would give every content version
of a document its own graph node instead of one node with a changing
content hash.

**Parameters:**

- **document_key** (<code>[str](#str)</code>) – The document's stable key.

**Returns:**

- <code>[UUID](#uuid.UUID)</code> – The Document graph node id.

####### `agrag.common.data_models.document.Document.raw_record`

```python
raw_record: dict[str, Any] | None = None
```

####### `agrag.common.data_models.document.Document.record_id`

```python
record_id: str | None = None
```

####### `agrag.common.data_models.document.Document.record_index`

```python
record_index: int | None = None
```

####### `agrag.common.data_models.document.Document.resolved_document_key`

```python
resolved_document_key: str
```

The document key, guaranteed non-`None` once construction succeeds.

`document_key` is typed as optional because callers may omit it and let
`_resolve_document_key` default it to `uri`, but every constructed
`Document` has a non-`None` document key by the time callers see it. Use
this property instead of `document_key` where a non-optional value is
required, such as computing the persisted Document node's id.

**Raises:**

- <code>[RuntimeError](#RuntimeError)</code> – `document_key` is still `None`, which means a validator
  was bypassed, for example via `model_construct`.

####### `agrag.common.data_models.document.Document.resolved_id`

```python
resolved_id: UUID
```

The document id, guaranteed non-`None` once construction succeeds.

`id` is typed as optional because callers may omit it and let
`_resolve_id` derive it, but every constructed `Document` has a
non-`None` id by the time callers see it. Use this property instead of
`id` where a non-optional value is required, such as building a `Chunk`.

**Raises:**

- <code>[RuntimeError](#RuntimeError)</code> – `id` is still `None`, which means a validator was
  bypassed, for example via `model_construct`.

####### `agrag.common.data_models.document.Document.source_format`

```python
source_format: SourceFormat
```

####### `agrag.common.data_models.document.Document.source_hash`

```python
source_hash: str | None = None
```

####### `agrag.common.data_models.document.Document.text`

```python
text: str
```

####### `agrag.common.data_models.document.Document.title`

```python
title: str
```

####### `agrag.common.data_models.document.Document.to_node_record`

```python
to_node_record() -> NodeRecord
```

Return this document as a GraphStore write record for its graph node.

The record excludes `text`: the persisted node exists for traversal and
the update no-op check, not to duplicate the document body already held
per-chunk.

####### `agrag.common.data_models.document.Document.uri`

```python
uri: str
```

###### `agrag.common.data_models.document.DocumentFamily`

Bases: <code>[StrEnum](#enum.StrEnum)</code>

The shape of a document's source.

**Attributes:**

- [**PROSE**](#agrag.common.data_models.document.DocumentFamily.PROSE) – One source file makes one document.
- [**RECORD**](#agrag.common.data_models.document.DocumentFamily.RECORD) – One source file makes many documents, one per record.

####### `agrag.common.data_models.document.DocumentFamily.PROSE`

```python
PROSE = 'prose'
```

####### `agrag.common.data_models.document.DocumentFamily.RECORD`

```python
RECORD = 'record'
```

###### `agrag.common.data_models.document.HeadingRef`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

One heading in a document outline.

**Attributes:**

- [**text**](#agrag.common.data_models.document.HeadingRef.text) (<code>[str](#str)</code>) – The heading text.
- [**level**](#agrag.common.data_models.document.HeadingRef.level) (<code>[int](#int)</code>) – The heading depth. A top-level heading has level 1.
- [**char_start**](#agrag.common.data_models.document.HeadingRef.char_start) (<code>[int](#int)</code>) – The start character offset of the heading in the document text. The
  chunker uses this offset to find which heading contains each chunk, since
  the
  base chunker does not detect headings on its own.

####### `agrag.common.data_models.document.HeadingRef.char_start`

```python
char_start: int
```

####### `agrag.common.data_models.document.HeadingRef.level`

```python
level: int
```

####### `agrag.common.data_models.document.HeadingRef.text`

```python
text: str
```

###### `agrag.common.data_models.document.SourceFormat`

Bases: <code>[StrEnum](#enum.StrEnum)</code>

A source format that a loader can read.

The field that holds this value is named `source_format`, not `format`.
`format`
is a Python builtin, and this project's lint rules reject builtin names for fields.

**Attributes:**

- [**ASCIIDOC**](#agrag.common.data_models.document.SourceFormat.ASCIIDOC) –
- [**CSV**](#agrag.common.data_models.document.SourceFormat.CSV) –
- [**DOCX**](#agrag.common.data_models.document.SourceFormat.DOCX) –
- [**HTML**](#agrag.common.data_models.document.SourceFormat.HTML) –
- [**IMAGE**](#agrag.common.data_models.document.SourceFormat.IMAGE) –
- [**JSON**](#agrag.common.data_models.document.SourceFormat.JSON) –
- [**JSONL**](#agrag.common.data_models.document.SourceFormat.JSONL) –
- [**LOG**](#agrag.common.data_models.document.SourceFormat.LOG) –
- [**MARKDOWN**](#agrag.common.data_models.document.SourceFormat.MARKDOWN) –
- [**PDF**](#agrag.common.data_models.document.SourceFormat.PDF) –
- [**PPTX**](#agrag.common.data_models.document.SourceFormat.PPTX) –
- [**TSV**](#agrag.common.data_models.document.SourceFormat.TSV) –
- [**TXT**](#agrag.common.data_models.document.SourceFormat.TXT) –
- [**XML**](#agrag.common.data_models.document.SourceFormat.XML) –

####### `agrag.common.data_models.document.SourceFormat.ASCIIDOC`

```python
ASCIIDOC = 'asciidoc'
```

####### `agrag.common.data_models.document.SourceFormat.CSV`

```python
CSV = 'csv'
```

####### `agrag.common.data_models.document.SourceFormat.DOCX`

```python
DOCX = 'docx'
```

####### `agrag.common.data_models.document.SourceFormat.HTML`

```python
HTML = 'html'
```

####### `agrag.common.data_models.document.SourceFormat.IMAGE`

```python
IMAGE = 'image'
```

####### `agrag.common.data_models.document.SourceFormat.JSON`

```python
JSON = 'json'
```

####### `agrag.common.data_models.document.SourceFormat.JSONL`

```python
JSONL = 'jsonl'
```

####### `agrag.common.data_models.document.SourceFormat.LOG`

```python
LOG = 'log'
```

####### `agrag.common.data_models.document.SourceFormat.MARKDOWN`

```python
MARKDOWN = 'markdown'
```

####### `agrag.common.data_models.document.SourceFormat.PDF`

```python
PDF = 'pdf'
```

####### `agrag.common.data_models.document.SourceFormat.PPTX`

```python
PPTX = 'pptx'
```

####### `agrag.common.data_models.document.SourceFormat.TSV`

```python
TSV = 'tsv'
```

####### `agrag.common.data_models.document.SourceFormat.TXT`

```python
TXT = 'txt'
```

####### `agrag.common.data_models.document.SourceFormat.XML`

```python
XML = 'xml'
```

##### `agrag.common.data_models.entity`

The canonical, resolved graph entity that merge mechanics produces.

**Classes:**

- [**Entity**](#agrag.common.data_models.entity.Entity) – A resolved entity, assembled from one or more ExtractedEntity mentions.

###### `agrag.common.data_models.entity.Entity`

Bases: <code>[DataPoint](#agrag.common.data_models.data_point.DataPoint)</code>

A resolved entity, assembled from one or more ExtractedEntity mentions.

**Attributes:**

- [**label**](#agrag.common.data_models.entity.Entity.label) (<code>[str](#str)</code>) – The EntityType label this entity was resolved as.
- [**name**](#agrag.common.data_models.entity.Entity.name) (<code>[str](#str)</code>) – The canonical resolved surface form — field-resolved the same
  way any property is, but kept as its own field rather than
  inside properties, since every entity has one regardless of
  EntityType.properties' schema, and it is what gets embedded
  (embedding_text).
- [**properties**](#agrag.common.data_models.entity.Entity.properties) (<code>[dict](#dict)\[[str](#str), [object](#object)\]</code>) – Field-resolved property values, keyed by the schema's
  declared property names (e.g. "dosage", "description" — whatever
  EntityType.properties for this label declares). Never holds name.
- [**embedding**](#agrag.common.data_models.entity.Entity.embedding) (<code>[list](#list)\[[float](#float)\] | None</code>) – The entity's dense vector, once populated by the storage
  stage. None before that point.
- [**merged_from**](#agrag.common.data_models.entity.Entity.merged_from) (<code>[list](#list)\[[UUID](#uuid.UUID)\]</code>) – Ids of entities absorbed into this one by a tombstone
  merge. Empty for an entity that has never absorbed another.
- [**merge_count**](#agrag.common.data_models.entity.Entity.merge_count) (<code>[int](#int)</code>) – The total number of source mentions and absorbed
  entities this entity's data was assembled from. Starts at 1.
- [**source_chunk_ids**](#agrag.common.data_models.entity.Entity.source_chunk_ids) (<code>[list](#list)\[[UUID](#uuid.UUID)\]</code>) – Ids of every Chunk a mention contributing to this
  entity's data came from. Each also backs one MENTIONED_IN edge
  from that Chunk to this Entity.

**Functions:**

- [**to_node_record**](#agrag.common.data_models.entity.Entity.to_node_record) – Return this entity as a GraphStore write record.

####### `agrag.common.data_models.entity.Entity.created_at`

```python
created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

####### `agrag.common.data_models.entity.Entity.embedding`

```python
embedding: list[float] | None = None
```

####### `agrag.common.data_models.entity.Entity.embedding_text`

```python
embedding_text: str
```

Return the text this entity's embedding is computed from.

Name alone, or name plus a "description" property when the schema
declares one — decided once, here, so every embedding call site
(resolution's future embedding tier, storage-stage population,
Graph.consolidate()) embeds the same text for the same entity.

####### `agrag.common.data_models.entity.Entity.id`

```python
id: UUID
```

####### `agrag.common.data_models.entity.Entity.label`

```python
label: str
```

####### `agrag.common.data_models.entity.Entity.merge_count`

```python
merge_count: int = 1
```

####### `agrag.common.data_models.entity.Entity.merge_key`

```python
merge_key: str
```

Return this entity's global exact-match lookup key.

(label, normalized name) — the same identity ExactMatch already uses
in-batch, applied to a persisted store lookup. A derived value, not
stored redundantly anywhere else on this model; to_node_record()
computes it fresh from label/name every write, so it can never drift
from what the fields it's derived from actually say.

####### `agrag.common.data_models.entity.Entity.merged_from`

```python
merged_from: list[UUID] = Field(default_factory=list)
```

####### `agrag.common.data_models.entity.Entity.metadata`

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

####### `agrag.common.data_models.entity.Entity.name`

```python
name: str
```

####### `agrag.common.data_models.entity.Entity.properties`

```python
properties: dict[str, object] = Field(default_factory=dict)
```

####### `agrag.common.data_models.entity.Entity.source_chunk_ids`

```python
source_chunk_ids: list[UUID] = Field(default_factory=list)
```

####### `agrag.common.data_models.entity.Entity.to_node_record`

```python
to_node_record() -> NodeRecord
```

Return this entity as a GraphStore write record.

Name, merge_key, merged_from, merge_count, and source_chunk_ids are
flattened into properties as plain JSON-safe values; GraphStore has
no reason to know these fields are special.

##### `agrag.common.data_models.extraction`

Pre-resolution entity and relation mentions produced by an Extractor.

**Classes:**

- [**ExtractedEntity**](#agrag.common.data_models.extraction.ExtractedEntity) – One entity mention found in a single Chunk.
- [**ExtractedRelation**](#agrag.common.data_models.extraction.ExtractedRelation) – One relation mention between two ExtractedEntity mentions in one Chunk.
- [**ExtractionResult**](#agrag.common.data_models.extraction.ExtractionResult) – The entities and relations one Extractor call found in one Chunk.

###### `agrag.common.data_models.extraction.ExtractedEntity`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

One entity mention found in a single Chunk.

Not a graph node: this has no id and no canonical identity. Resolution decides
which ExtractedEntity mentions refer to the same real-world thing.

**Attributes:**

- [**chunk_id**](#agrag.common.data_models.extraction.ExtractedEntity.chunk_id) (<code>[UUID](#uuid.UUID)</code>) – The id of the Chunk this mention came from.
- [**label**](#agrag.common.data_models.extraction.ExtractedEntity.label) (<code>[str](#str)</code>) – The EntityType label this mention was extracted as.
- [**text**](#agrag.common.data_models.extraction.ExtractedEntity.text) (<code>[str](#str)</code>) – The mention's surface text.
- [**char_start**](#agrag.common.data_models.extraction.ExtractedEntity.char_start) (<code>[int](#int)</code>) – The start character offset within the chunk's text.
- [**char_end**](#agrag.common.data_models.extraction.ExtractedEntity.char_end) (<code>[int](#int)</code>) – The end character offset within the chunk's text.
- [**confidence**](#agrag.common.data_models.extraction.ExtractedEntity.confidence) (<code>[float](#float) | None</code>) – The extractor's confidence in this mention, when available.
- [**properties**](#agrag.common.data_models.extraction.ExtractedEntity.properties) (<code>[dict](#dict)\[[str](#str), [object](#object)\]</code>) – Schema-declared property values this mention carries,
  keyed by property name. Empty for an extractor that only reports
  spans -- normalize_extraction_result drops any key the schema
  does not declare for this mention's label.

####### `agrag.common.data_models.extraction.ExtractedEntity.char_end`

```python
char_end: int
```

####### `agrag.common.data_models.extraction.ExtractedEntity.char_start`

```python
char_start: int
```

####### `agrag.common.data_models.extraction.ExtractedEntity.chunk_id`

```python
chunk_id: UUID
```

####### `agrag.common.data_models.extraction.ExtractedEntity.confidence`

```python
confidence: float | None = None
```

####### `agrag.common.data_models.extraction.ExtractedEntity.label`

```python
label: str
```

####### `agrag.common.data_models.extraction.ExtractedEntity.properties`

```python
properties: dict[str, object] = Field(default_factory=dict)
```

####### `agrag.common.data_models.extraction.ExtractedEntity.text`

```python
text: str
```

###### `agrag.common.data_models.extraction.ExtractedRelation`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

One relation mention between two ExtractedEntity mentions in one Chunk.

**Attributes:**

- [**chunk_id**](#agrag.common.data_models.extraction.ExtractedRelation.chunk_id) (<code>[UUID](#uuid.UUID)</code>) – The id of the Chunk this mention came from.
- [**label**](#agrag.common.data_models.extraction.ExtractedRelation.label) (<code>[str](#str)</code>) – The RelationType label this mention was extracted as.
- [**source_index**](#agrag.common.data_models.extraction.ExtractedRelation.source_index) (<code>[int](#int)</code>) – Index of the source entity in the same ExtractionResult.entities.
- [**target_index**](#agrag.common.data_models.extraction.ExtractedRelation.target_index) (<code>[int](#int)</code>) – Index of the target entity in the same ExtractionResult.entities.
- [**confidence**](#agrag.common.data_models.extraction.ExtractedRelation.confidence) (<code>[float](#float) | None</code>) – The extractor's confidence in this mention, when available.

####### `agrag.common.data_models.extraction.ExtractedRelation.chunk_id`

```python
chunk_id: UUID
```

####### `agrag.common.data_models.extraction.ExtractedRelation.confidence`

```python
confidence: float | None = None
```

####### `agrag.common.data_models.extraction.ExtractedRelation.label`

```python
label: str
```

####### `agrag.common.data_models.extraction.ExtractedRelation.source_index`

```python
source_index: int
```

####### `agrag.common.data_models.extraction.ExtractedRelation.target_index`

```python
target_index: int
```

###### `agrag.common.data_models.extraction.ExtractionResult`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

The entities and relations one Extractor call found in one Chunk.

**Attributes:**

- [**entities**](#agrag.common.data_models.extraction.ExtractionResult.entities) (<code>[list](#list)\[[ExtractedEntity](#agrag.common.data_models.extraction.ExtractedEntity)\]</code>) – The mentions found, in extraction order.
- [**relations**](#agrag.common.data_models.extraction.ExtractionResult.relations) (<code>[list](#list)\[[ExtractedRelation](#agrag.common.data_models.extraction.ExtractedRelation)\]</code>) – The relation mentions found, referencing entities by index.
- [**extractor_name**](#agrag.common.data_models.extraction.ExtractionResult.extractor_name) (<code>[str](#str)</code>) – Which Extractor produced this result. Set by the Extractor
  itself; useful for provenance when a EscalatingExtractor escalated.

####### `agrag.common.data_models.extraction.ExtractionResult.entities`

```python
entities: list[ExtractedEntity]
```

####### `agrag.common.data_models.extraction.ExtractionResult.extractor_name`

```python
extractor_name: str
```

####### `agrag.common.data_models.extraction.ExtractionResult.relations`

```python
relations: list[ExtractedRelation]
```

##### `agrag.common.data_models.graph_record`

Graph storage record shapes for GraphStore.

These are a temporary, minimal stopgap, not the canonical Entity/Relation
domain model resolution will eventually produce. See the future
storage/merge-mechanics work this decouples from.

**Classes:**

- [**NodeRecord**](#agrag.common.data_models.graph_record.NodeRecord) – One graph node, ready to write.
- [**RelationRecord**](#agrag.common.data_models.graph_record.RelationRecord) – One graph relationship, ready to write.
- [**UpsertFailure**](#agrag.common.data_models.graph_record.UpsertFailure) – One record that failed to write within a bulk upsert call.
- [**UpsertResult**](#agrag.common.data_models.graph_record.UpsertResult) – Outcome of a bulk `upsert_nodes`/`upsert_relations` call.

###### `agrag.common.data_models.graph_record.NodeRecord`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

One graph node, ready to write.

**Attributes:**

- [**id**](#agrag.common.data_models.graph_record.NodeRecord.id) (<code>[UUID](#uuid.UUID)</code>) – The node id.
- [**labels**](#agrag.common.data_models.graph_record.NodeRecord.labels) (<code>[list](#list)\[[str](#str)\]</code>) – The node's labels. A node carries every label listed here;
  `GraphStore.upsert_nodes` groups records by their full label set
  within a batch, since Cypher requires labels to be literal in the
  query rather than a runtime parameter.
- [**properties**](#agrag.common.data_models.graph_record.NodeRecord.properties) (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\]</code>) – The node's properties, including an embedding vector under
  whatever key `GraphStore.ensure_vector_index` was configured
  with, if native vector search is in use.

####### `agrag.common.data_models.graph_record.NodeRecord.id`

```python
id: UUID
```

####### `agrag.common.data_models.graph_record.NodeRecord.labels`

```python
labels: list[str] = Field(min_length=1)
```

####### `agrag.common.data_models.graph_record.NodeRecord.properties`

```python
properties: dict[str, Any]
```

###### `agrag.common.data_models.graph_record.RelationRecord`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

One graph relationship, ready to write.

**Attributes:**

- [**id**](#agrag.common.data_models.graph_record.RelationRecord.id) (<code>[UUID](#uuid.UUID)</code>) – The relationship id.
- [**type**](#agrag.common.data_models.graph_record.RelationRecord.type) (<code>[str](#str)</code>) – The relationship type.
- [**start_id**](#agrag.common.data_models.graph_record.RelationRecord.start_id) (<code>[UUID](#uuid.UUID)</code>) – The id of the start node.
- [**end_id**](#agrag.common.data_models.graph_record.RelationRecord.end_id) (<code>[UUID](#uuid.UUID)</code>) – The id of the end node.
- [**properties**](#agrag.common.data_models.graph_record.RelationRecord.properties) (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\]</code>) – The relationship's properties.

####### `agrag.common.data_models.graph_record.RelationRecord.end_id`

```python
end_id: UUID
```

####### `agrag.common.data_models.graph_record.RelationRecord.id`

```python
id: UUID
```

####### `agrag.common.data_models.graph_record.RelationRecord.properties`

```python
properties: dict[str, Any]
```

####### `agrag.common.data_models.graph_record.RelationRecord.start_id`

```python
start_id: UUID
```

####### `agrag.common.data_models.graph_record.RelationRecord.type`

```python
type: str
```

###### `agrag.common.data_models.graph_record.UpsertFailure`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

One record that failed to write within a bulk upsert call.

**Attributes:**

- [**id**](#agrag.common.data_models.graph_record.UpsertFailure.id) (<code>[str](#str)</code>) – The failed record's own id, as a string (matches the id already
  sent to the backend, not necessarily parseable back to UUID for
  every future backend).
- [**error_type**](#agrag.common.data_models.graph_record.UpsertFailure.error_type) (<code>[str](#str)</code>) – The backend exception class name or GraphStore failure label.
- [**error_message**](#agrag.common.data_models.graph_record.UpsertFailure.error_message) (<code>[str](#str)</code>) – The backend exception message or failure description.

####### `agrag.common.data_models.graph_record.UpsertFailure.error_message`

```python
error_message: str
```

####### `agrag.common.data_models.graph_record.UpsertFailure.error_type`

```python
error_type: str
```

####### `agrag.common.data_models.graph_record.UpsertFailure.id`

```python
id: str
```

###### `agrag.common.data_models.graph_record.UpsertResult`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

Outcome of a bulk `upsert_nodes`/`upsert_relations` call.

**Attributes:**

- [**written**](#agrag.common.data_models.graph_record.UpsertResult.written) (<code>[int](#int)</code>) – How many records were written successfully.
- [**failures**](#agrag.common.data_models.graph_record.UpsertResult.failures) (<code>[list](#list)\[[UpsertFailure](#agrag.common.data_models.graph_record.UpsertFailure)\]</code>) – Records that failed, isolated from the rest of the call.
  Empty when every record wrote successfully.

####### `agrag.common.data_models.graph_record.UpsertResult.failures`

```python
failures: list[UpsertFailure] = Field(default_factory=list)
```

####### `agrag.common.data_models.graph_record.UpsertResult.written`

```python
written: int = 0
```

##### `agrag.common.data_models.graph_schema`

The GraphSchema contract: entity and relation types extraction validates against.

**Classes:**

- [**EntityType**](#agrag.common.data_models.graph_schema.EntityType) – One kind of entity a schema recognizes.
- [**GraphSchema**](#agrag.common.data_models.graph_schema.GraphSchema) – A versioned contract of entity and relation types.
- [**RelationType**](#agrag.common.data_models.graph_schema.RelationType) – One kind of relation a schema recognizes.

**Attributes:**

- [**GENERIC**](#agrag.common.data_models.graph_schema.GENERIC) –

###### `agrag.common.data_models.graph_schema.EntityType`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

One kind of entity a schema recognizes.

**Attributes:**

- [**label**](#agrag.common.data_models.graph_schema.EntityType.label) (<code>[str](#str)</code>) – The node label used in the extraction prompt and the graph.
- [**description**](#agrag.common.data_models.graph_schema.EntityType.description) (<code>[str](#str)</code>) – Guidance fed to the extractor prompt or schema builder.
- [**properties**](#agrag.common.data_models.graph_schema.EntityType.properties) (<code>[dict](#dict)\[[str](#str), [str](#str)\]</code>) – Property names mapped to a type name, such as `"str"` or
  `"date"`. `label` and `text` are rejected, since both are
  vector payload keys retrieval filtering and keyword search use.
- [**subtypes**](#agrag.common.data_models.graph_schema.EntityType.subtypes) (<code>[list](#list)\[[str](#str)\]</code>) – Labels that narrow this type. Empty when this type has no subtypes.

####### `agrag.common.data_models.graph_schema.EntityType.description`

```python
description: str
```

####### `agrag.common.data_models.graph_schema.EntityType.label`

```python
label: str
```

####### `agrag.common.data_models.graph_schema.EntityType.properties`

```python
properties: dict[str, str] = Field(default_factory=dict)
```

####### `agrag.common.data_models.graph_schema.EntityType.subtypes`

```python
subtypes: list[str] = Field(default_factory=list)
```

###### `agrag.common.data_models.graph_schema.GENERIC`

```python
GENERIC = GraphSchema(name='generic', version='1', entities=[EntityType(label='Person', description='A named individual.'), EntityType(label='Organization', description='A company or institution.'), EntityType(label='Location', description='A place or geographic area.'), EntityType(label='Event', description='A named occurrence at a time or place.'), EntityType(label='Product', description='A named product, service, or work.')], relations=[RelationType(label='RELATED_TO', description='A generic relationship between two entities.', patterns=[(src, tgt) for src in _GENERIC_LABELS for tgt in _GENERIC_LABELS])])
```

###### `agrag.common.data_models.graph_schema.GraphSchema`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

A versioned contract of entity and relation types.

Every extraction call is validated against a GraphSchema; there is no schema-free
extraction path. Round-trip with `model_dump(mode="json")`/`model_validate()`.
A schema declaring an entity property name the vector payload reserves fails that
validation, so a payload written before the check existed must be migrated before
it loads again. See `EntityType.properties`.

**Attributes:**

- [**name**](#agrag.common.data_models.graph_schema.GraphSchema.name) (<code>[str](#str)</code>) – A short, unique name for this schema.
- [**version**](#agrag.common.data_models.graph_schema.GraphSchema.version) (<code>[str](#str)</code>) – The schema version. Bump when types or patterns change.
- [**entities**](#agrag.common.data_models.graph_schema.GraphSchema.entities) (<code>[list](#list)\[[EntityType](#agrag.common.data_models.graph_schema.EntityType)\]</code>) – The entity types this schema recognizes.
- [**relations**](#agrag.common.data_models.graph_schema.GraphSchema.relations) (<code>[list](#list)\[[RelationType](#agrag.common.data_models.graph_schema.RelationType)\]</code>) – The relation types this schema recognizes.

####### `agrag.common.data_models.graph_schema.GraphSchema.entities`

```python
entities: list[EntityType]
```

####### `agrag.common.data_models.graph_schema.GraphSchema.name`

```python
name: str
```

####### `agrag.common.data_models.graph_schema.GraphSchema.relations`

```python
relations: list[RelationType]
```

####### `agrag.common.data_models.graph_schema.GraphSchema.version`

```python
version: str
```

###### `agrag.common.data_models.graph_schema.RelationType`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

One kind of relation a schema recognizes.

**Attributes:**

- [**label**](#agrag.common.data_models.graph_schema.RelationType.label) (<code>[str](#str)</code>) – The relation label used in the extraction prompt and the graph.
- [**description**](#agrag.common.data_models.graph_schema.RelationType.description) (<code>[str](#str)</code>) – Guidance fed to the extractor prompt or schema builder.
- [**patterns**](#agrag.common.data_models.graph_schema.RelationType.patterns) (<code>[list](#list)\[[tuple](#tuple)\[[str](#str), [str](#str)\]\]</code>) – Valid (source_label, target_label) pairs for this relation. An
  extraction whose triple is not in this list is dropped at normalize time.

####### `agrag.common.data_models.graph_schema.RelationType.description`

```python
description: str
```

####### `agrag.common.data_models.graph_schema.RelationType.label`

```python
label: str
```

####### `agrag.common.data_models.graph_schema.RelationType.patterns`

```python
patterns: list[tuple[str, str]]
```

##### `agrag.common.data_models.provenance`

Provenance types for a chunk.

A chunk's provenance shows where its text came from in the source. The shape of the
provenance depends on which chunker made the chunk.

**Classes:**

- [**BoundingBox**](#agrag.common.data_models.provenance.BoundingBox) – A box on a page, in page coordinates.
- [**PageProvenance**](#agrag.common.data_models.provenance.PageProvenance) – The location of a chunk across one or more pages.
- [**PageSpan**](#agrag.common.data_models.provenance.PageSpan) – One page's part of a chunk.
- [**TextProvenance**](#agrag.common.data_models.provenance.TextProvenance) – The location of a chunk inside flattened document text.

###### `agrag.common.data_models.provenance.BoundingBox`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

A box on a page, in page coordinates.

**Attributes:**

- [**x0**](#agrag.common.data_models.provenance.BoundingBox.x0) (<code>[float](#float)</code>) – The left edge.
- [**y0**](#agrag.common.data_models.provenance.BoundingBox.y0) (<code>[float](#float)</code>) – The top edge.
- [**x1**](#agrag.common.data_models.provenance.BoundingBox.x1) (<code>[float](#float)</code>) – The right edge.
- [**y1**](#agrag.common.data_models.provenance.BoundingBox.y1) (<code>[float](#float)</code>) – The bottom edge.

####### `agrag.common.data_models.provenance.BoundingBox.x0`

```python
x0: float
```

####### `agrag.common.data_models.provenance.BoundingBox.x1`

```python
x1: float
```

####### `agrag.common.data_models.provenance.BoundingBox.y0`

```python
y0: float
```

####### `agrag.common.data_models.provenance.BoundingBox.y1`

```python
y1: float
```

###### `agrag.common.data_models.provenance.PageProvenance`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

The location of a chunk across one or more pages.

A chunk can start on one page and end on the next page. Each entry in `page_spans`
covers one page.

**Attributes:**

- [**kind**](#agrag.common.data_models.provenance.PageProvenance.kind) (<code>[Literal](#typing.Literal)['page']</code>) – The literal tag `"page"`. Marks this as page provenance.
- [**page_spans**](#agrag.common.data_models.provenance.PageProvenance.page_spans) (<code>[list](#list)\[[PageSpan](#agrag.common.data_models.provenance.PageSpan)\]</code>) – The page spans for this chunk. Has more than one entry when
  the chunk crosses a page boundary.

####### `agrag.common.data_models.provenance.PageProvenance.kind`

```python
kind: Literal['page'] = 'page'
```

####### `agrag.common.data_models.provenance.PageProvenance.page_spans`

```python
page_spans: list[PageSpan]
```

###### `agrag.common.data_models.provenance.PageSpan`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

One page's part of a chunk.

**Attributes:**

- [**page_no**](#agrag.common.data_models.provenance.PageSpan.page_no) (<code>[int](#int)</code>) – The page number.
- [**bbox**](#agrag.common.data_models.provenance.PageSpan.bbox) (<code>[BoundingBox](#agrag.common.data_models.provenance.BoundingBox)</code>) – The box on the page that holds this part of the chunk.

####### `agrag.common.data_models.provenance.PageSpan.bbox`

```python
bbox: BoundingBox
```

####### `agrag.common.data_models.provenance.PageSpan.page_no`

```python
page_no: int
```

###### `agrag.common.data_models.provenance.TextProvenance`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

The location of a chunk inside flattened document text.

**Attributes:**

- [**kind**](#agrag.common.data_models.provenance.TextProvenance.kind) (<code>[Literal](#typing.Literal)['text']</code>) – The literal tag `"text"`. Marks this as text provenance.
- [**char_start**](#agrag.common.data_models.provenance.TextProvenance.char_start) (<code>[int](#int)</code>) – The start character offset in the document text.
- [**char_end**](#agrag.common.data_models.provenance.TextProvenance.char_end) (<code>[int](#int)</code>) – The end character offset in the document text.
- [**line_start**](#agrag.common.data_models.provenance.TextProvenance.line_start) (<code>[int](#int) | None</code>) – The start line number. Empty when the loader does not track lines.
- [**line_end**](#agrag.common.data_models.provenance.TextProvenance.line_end) (<code>[int](#int) | None</code>) – The end line number. Empty when the loader does not track lines.

####### `agrag.common.data_models.provenance.TextProvenance.char_end`

```python
char_end: int
```

####### `agrag.common.data_models.provenance.TextProvenance.char_start`

```python
char_start: int
```

####### `agrag.common.data_models.provenance.TextProvenance.kind`

```python
kind: Literal['text'] = 'text'
```

####### `agrag.common.data_models.provenance.TextProvenance.line_end`

```python
line_end: int | None = None
```

####### `agrag.common.data_models.provenance.TextProvenance.line_start`

```python
line_start: int | None = None
```

##### `agrag.common.data_models.relation`

The canonical, deduped graph relationship that merge mechanics produces.

**Classes:**

- [**Relation**](#agrag.common.data_models.relation.Relation) – A resolved relationship between two Entity nodes.

###### `agrag.common.data_models.relation.Relation`

Bases: <code>[DataPoint](#agrag.common.data_models.data_point.DataPoint)</code>

A resolved relationship between two Entity nodes.

**Attributes:**

- [**type**](#agrag.common.data_models.relation.Relation.type) (<code>[str](#str)</code>) – The RelationType label this relationship was resolved as.
- [**source_id**](#agrag.common.data_models.relation.Relation.source_id) (<code>[UUID](#uuid.UUID)</code>) – The id of the source Entity.
- [**target_id**](#agrag.common.data_models.relation.Relation.target_id) (<code>[UUID](#uuid.UUID)</code>) – The id of the target Entity.
- [**properties**](#agrag.common.data_models.relation.Relation.properties) (<code>[dict](#dict)\[[str](#str), [object](#object)\]</code>) – Field-resolved property values.
- [**source_chunk_ids**](#agrag.common.data_models.relation.Relation.source_chunk_ids) (<code>[list](#list)\[[UUID](#uuid.UUID)\]</code>) – Ids of every Chunk a mention contributing to this
  relationship came from. A relationship attested by more than one
  source has more than one id here, rather than existing as
  parallel edges.

**Functions:**

- [**to_relation_record**](#agrag.common.data_models.relation.Relation.to_relation_record) – Return this relationship as a GraphStore write record.

####### `agrag.common.data_models.relation.Relation.created_at`

```python
created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

####### `agrag.common.data_models.relation.Relation.id`

```python
id: UUID
```

####### `agrag.common.data_models.relation.Relation.metadata`

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

####### `agrag.common.data_models.relation.Relation.properties`

```python
properties: dict[str, object] = Field(default_factory=dict)
```

####### `agrag.common.data_models.relation.Relation.source_chunk_ids`

```python
source_chunk_ids: list[UUID] = Field(default_factory=list)
```

####### `agrag.common.data_models.relation.Relation.source_id`

```python
source_id: UUID
```

####### `agrag.common.data_models.relation.Relation.target_id`

```python
target_id: UUID
```

####### `agrag.common.data_models.relation.Relation.to_relation_record`

```python
to_relation_record() -> RelationRecord
```

Return this relationship as a GraphStore write record.

####### `agrag.common.data_models.relation.Relation.type`

```python
type: str
```

##### `agrag.common.data_models.search_result`

One retrieved item, tagged with source and relevance score.

**Classes:**

- [**SearchResult**](#agrag.common.data_models.search_result.SearchResult) – One retrieved item, tagged with where it came from.

###### `agrag.common.data_models.search_result.SearchResult`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

One retrieved item, tagged with where it came from.

**Attributes:**

- [**item**](#agrag.common.data_models.search_result.SearchResult.item) (<code>[Union](#typing.Union)\[[Entity](#agrag.common.data_models.entity.Entity), [Relation](#agrag.common.data_models.relation.Relation), [Chunk](#agrag.common.data_models.chunk.Chunk), [Community](#agrag.common.data_models.community.Community)\]</code>) – The retrieved Entity, Relation, Chunk, or Community,
  already resolved through any merged_into chain.
- [**score**](#agrag.common.data_models.search_result.SearchResult.score) (<code>[float](#float)</code>) – The method's own relevance score. Not comparable
  across methods until Fusion normalizes it.
- [**method**](#agrag.common.data_models.search_result.SearchResult.method) (<code>[str](#str)</code>) – The name of the retrieval method that produced
  this result.

####### `agrag.common.data_models.search_result.SearchResult.identity_key`

```python
identity_key: tuple[str, UUID]
```

Return the (type, id) key Fusion deduplicates on.

**Raises:**

- <code>[ValueError](#ValueError)</code> – The item has no id, so it cannot be
  deduplicated.

####### `agrag.common.data_models.search_result.SearchResult.item`

```python
item: Union[Entity, Relation, Chunk, Community]
```

####### `agrag.common.data_models.search_result.SearchResult.method`

```python
method: str
```

####### `agrag.common.data_models.search_result.SearchResult.score`

```python
score: float
```

##### `agrag.common.data_models.vector_record`

Vector storage record shapes shared by VectorStore and GraphStore.

**Classes:**

- [**Distance**](#agrag.common.data_models.vector_record.Distance) – A distance metric a vector index compares embeddings with.
- [**VectorHit**](#agrag.common.data_models.vector_record.VectorHit) – One search result: a matched id, its score, and its stored payload.
- [**VectorRecord**](#agrag.common.data_models.vector_record.VectorRecord) – One vector and its payload, ready to write to a collection or index.

###### `agrag.common.data_models.vector_record.Distance`

Bases: <code>[StrEnum](#enum.StrEnum)</code>

A distance metric a vector index compares embeddings with.

**Attributes:**

- [**COSINE**](#agrag.common.data_models.vector_record.Distance.COSINE) – Cosine similarity. The default for most embedding models.
- [**EUCLID**](#agrag.common.data_models.vector_record.Distance.EUCLID) – Euclidean (L2) distance.
- [**DOT**](#agrag.common.data_models.vector_record.Distance.DOT) – Dot product.

####### `agrag.common.data_models.vector_record.Distance.COSINE`

```python
COSINE = 'Cosine'
```

####### `agrag.common.data_models.vector_record.Distance.DOT`

```python
DOT = 'Dot'
```

####### `agrag.common.data_models.vector_record.Distance.EUCLID`

```python
EUCLID = 'Euclid'
```

###### `agrag.common.data_models.vector_record.VectorHit`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

One search result: a matched id, its score, and its stored payload.

Returned by both `VectorStore.search`/`hybrid_search` and
`GraphStore.vector_search`, so a caller cannot tell which store produced
a given hit.

**Attributes:**

- [**id**](#agrag.common.data_models.vector_record.VectorHit.id) (<code>[UUID](#uuid.UUID)</code>) – The id of the matched record.
- [**score**](#agrag.common.data_models.vector_record.VectorHit.score) (<code>[float](#float)</code>) – The match score. Higher means a closer match, regardless of
  which distance metric the collection uses.
- [**payload**](#agrag.common.data_models.vector_record.VectorHit.payload) (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\]</code>) – The payload stored with the matched record.

####### `agrag.common.data_models.vector_record.VectorHit.id`

```python
id: UUID
```

####### `agrag.common.data_models.vector_record.VectorHit.payload`

```python
payload: dict[str, Any]
```

####### `agrag.common.data_models.vector_record.VectorHit.score`

```python
score: float
```

###### `agrag.common.data_models.vector_record.VectorRecord`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

One vector and its payload, ready to write to a collection or index.

The collection or index name is a call argument on the store, not a field
here, so one record type can target any collection.

**Attributes:**

- [**id**](#agrag.common.data_models.vector_record.VectorRecord.id) (<code>[UUID](#uuid.UUID)</code>) – The record id. Callers set this to the id of the domain object the
  vector represents.
- [**vector**](#agrag.common.data_models.vector_record.VectorRecord.vector) (<code>[list](#list)\[[float](#float)\]</code>) – The dense embedding.
- [**payload**](#agrag.common.data_models.vector_record.VectorRecord.payload) (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\]</code>) – Fields stored alongside the vector, such as the source text or
  a chunk id. Read back unchanged by `search`/`hybrid_search`.

####### `agrag.common.data_models.vector_record.VectorRecord.id`

```python
id: UUID
```

####### `agrag.common.data_models.vector_record.VectorRecord.payload`

```python
payload: dict[str, Any]
```

####### `agrag.common.data_models.vector_record.VectorRecord.vector`

```python
vector: list[float]
```

#### `agrag.common.text`

Shared text normalization used across resolution and merge-key computation.

**Functions:**

- [**normalize_text**](#agrag.common.text.normalize_text) – Return text stripped and case-folded for identity comparison.

##### `agrag.common.text.normalize_text`

```python
normalize_text(text:str) -> str
```

Return text stripped and case-folded for identity comparison.

**Parameters:**

- **text** (<code>[str](#str)</code>) – The text to normalize.

**Returns:**

- <code>[str](#str)</code> – The stripped, case-folded text.

#### `agrag.common.validation`

Validation helpers shared across storage backends.

**Functions:**

- [**require_encrypted_remote_connection**](#agrag.common.validation.require_encrypted_remote_connection) – Reject a plaintext connection to a non-local host carrying a credential.
- [**require_positive_batch_size**](#agrag.common.validation.require_positive_batch_size) – Check that a backend write's `batch_size` is usable.
- [**require_positive_max_concurrency**](#agrag.common.validation.require_positive_max_concurrency) – Check that a concurrency limit is positive.
- [**require_valid_alpha**](#agrag.common.validation.require_valid_alpha) – Check that a `hybrid_search` `alpha` is a valid dense/keyword weight.
- [**require_valid_search_limit**](#agrag.common.validation.require_valid_search_limit) – Check that a search/hybrid_search `limit` is usable across every backend.

**Attributes:**

- [**MAX_SEARCH_LIMIT**](#agrag.common.validation.MAX_SEARCH_LIMIT) –

##### `agrag.common.validation.MAX_SEARCH_LIMIT`

```python
MAX_SEARCH_LIMIT = 16384
```

##### `agrag.common.validation.require_encrypted_remote_connection`

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

- **url** (<code>[str](#str)</code>) – The connection URL or URI to check.
- **has_credential** (<code>[bool](#bool)</code>) – Whether a credential (API key, token, password) is
  configured for this connection.
- **encrypted_schemes** (<code>[Collection](#collections.abc.Collection)\[[str](#str)\]</code>) – The URL schemes considered encrypted for this
  backend, for example `{"https"}` or `{"bolt+s", "neo4j+s"}`.
- **require_encryption** (<code>[bool](#bool)</code>) – When `True`, reject plaintext to a non-local
  host even without a configured credential.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `url` uses a scheme outside `encrypted_schemes`, its
  host is not loopback, and either `has_credential` or
  `require_encryption` is `True`.

##### `agrag.common.validation.require_positive_batch_size`

```python
require_positive_batch_size(batch_size:int) -> None
```

Check that a backend write's `batch_size` is usable.

Every backend chunks writes with `range(0, len(records), batch_size)`.
A non-positive value breaks that: zero raises `ValueError` from
`range` itself, and a negative value silently produces an empty range,
skipping every record without error.

**Parameters:**

- **batch_size** (<code>[int](#int)</code>) – The batch size to check.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `batch_size` is not positive.

##### `agrag.common.validation.require_positive_max_concurrency`

```python
require_positive_max_concurrency(max_concurrency:int) -> None
```

Check that a concurrency limit is positive.

##### `agrag.common.validation.require_valid_alpha`

```python
require_valid_alpha(alpha:float) -> None
```

Check that a `hybrid_search` `alpha` is a valid dense/keyword weight.

`alpha` is only meaningful in `[0.0, 1.0]`: `1.0` is pure dense,
`0.0` is pure keyword. Outside that range, backends behave
differently: Qdrant's client-side blend still produces a
mathematically well-defined but meaningless score, while a backend's
native ranker may reject the value outright.

**Parameters:**

- **alpha** (<code>[float](#float)</code>) – The dense/keyword balance to check.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `alpha` is outside `[0.0, 1.0]`.

##### `agrag.common.validation.require_valid_search_limit`

```python
require_valid_search_limit(limit:int) -> None
```

Check that a search/hybrid_search `limit` is usable across every backend.

Backends fail differently outside this range: Milvus raises for a
non-positive `limit` or one above `MAX_SEARCH_LIMIT` (its own
query/search result-window ceiling), while Qdrant and Weaviate may
instead return an empty or silently truncated result. Enforcing the
tightest bound uniformly means a given `limit` either works, or fails
the same way, regardless of which backend is configured.

**Parameters:**

- **limit** (<code>[int](#int)</code>) – The requested maximum number of hits.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `limit` is not a positive integer, or exceeds
  `MAX_SEARCH_LIMIT`.

### `agrag.cypher`

Cypher query builders for graph stores.

Leaf modules only: nothing here imports `agrag.graphdb`, so the dependency
points one way (store -> cypher).

**Modules:**

- [**community_read**](#agrag.cypher.community_read) – Cypher for community retrieval reads.
- [**community_write**](#agrag.cypher.community_write) – Cypher for the community-detection full-replace write path.
- [**entities**](#agrag.cypher.entities) – Cypher builders for node writes and filters.
- [**merge**](#agrag.cypher.merge) – Cypher for the tombstone/transfer/dedup merge path.
- [**relations**](#agrag.cypher.relations) – Cypher builders for relationship writes and graph traversal.
- [**safety**](#agrag.cypher.safety) – Safety gate for generated Cypher queries.
- [**schema**](#agrag.cypher.schema) – Cypher builders for constraints and native vector indexes.

#### `agrag.cypher.community_read`

Cypher for community retrieval reads.

**Functions:**

- [**communities_for_entities_query**](#agrag.cypher.community_read.communities_for_entities_query) – Build Cypher finding communities overlapping given entity ids.

##### `agrag.cypher.community_read.communities_for_entities_query`

```python
communities_for_entities_query(where_clause:str = '') -> str
```

Build Cypher finding communities overlapping given entity ids.

**Parameters:**

- **where_clause** (<code>[str](#str)</code>) – Optional parameterized Cypher `WHERE` clause
  (including the `WHERE` keyword) applied to the candidate
  community node `c`, e.g. from
  `SearchFilters.to_cypher_where("c")`. Empty applies no
  additional constraint. Community nodes carry no document or
  tenant scope, so a document- or property-scoped filter that
  names a property Community nodes never have makes this
  clause match nothing, returning no communities rather than
  an unscoped one.

**Returns:**

- <code>[str](#str)</code> – Parameterized Cypher expecting $entity_ids (list of string ids)
- <code>[str](#str)</code> – and $top_k (max rows to return; must be non-negative, since
- <code>[str](#str)</code> – Neo4j rejects a negative LIMIT). Returns each overlapping
- <code>[str](#str)</code> – community node and its overlap count, highest overlap first.

#### `agrag.cypher.community_write`

Cypher for the community-detection full-replace write path.

**Functions:**

- [**delete_communities_batch_query**](#agrag.cypher.community_write.delete_communities_batch_query) – Build Cypher deleting up to $limit Community nodes and their edges.

##### `agrag.cypher.community_write.delete_communities_batch_query`

```python
delete_communities_batch_query() -> str
```

Build Cypher deleting up to $limit Community nodes and their edges.

Called repeatedly by the caller (see
agrag.ingestion.community.delete_all_communities) until no rows are
deleted, rather than a single unbatched DETACH DELETE.

**Returns:**

- <code>[str](#str)</code> – Parameterized Cypher expecting $limit. Returns the count deleted.

#### `agrag.cypher.entities`

Cypher builders for node writes and filters.

Leaf module: imports nothing from `agrag.graphdb` or other store packages, so
the dependency points one way (store -> cypher).

**Functions:**

- [**clear_chunk_embedding_query**](#agrag.cypher.entities.clear_chunk_embedding_query) – Build Cypher removing a vector property from Chunk nodes.
- [**clear_property_query**](#agrag.cypher.entities.clear_property_query) – Build Cypher removing one property from a batch of nodes, guarded by text.
- [**fetch_all_by_label_query**](#agrag.cypher.entities.fetch_all_by_label_query) – Build Cypher paginating every node with label, for consolidate().
- [**fetch_by_merge_keys_query**](#agrag.cypher.entities.fetch_by_merge_keys_query) – Build Cypher for a batched exact-match lookup by merge key.
- [**fetch_relations_between_query**](#agrag.cypher.entities.fetch_relations_between_query) – Build Cypher for batched lookup of existing relations by endpoints.
- [**filter_clause**](#agrag.cypher.entities.filter_clause) – Build a Cypher WHERE clause and parameters from a flat-dict filter.
- [**hydrate_chunks_by_id_query**](#agrag.cypher.entities.hydrate_chunks_by_id_query) – Build Cypher fetching chunks by id.
- [**hydrate_entities_by_id_query**](#agrag.cypher.entities.hydrate_entities_by_id_query) – Build Cypher fetching entities by id, excluding tombstones.
- [**is_safe_identifier**](#agrag.cypher.entities.is_safe_identifier) – Report whether a label or relationship type is a safe Cypher identifier.
- [**merge_key_index_query**](#agrag.cypher.entities.merge_key_index_query) – Build a CREATE INDEX query on the node merge_key property.
- [**resolve_merged_into_query**](#agrag.cypher.entities.resolve_merged_into_query) – Return a node and the id of the node it was merged into.
- [**set_chunk_embedding_query**](#agrag.cypher.entities.set_chunk_embedding_query) – Build Cypher setting a vector property on Chunk nodes.
- [**set_embedding_query**](#agrag.cypher.entities.set_embedding_query) – Build Cypher setting one vector property per node, guarded by its text.
- [**upsert_merge_alias_query**](#agrag.cypher.entities.upsert_merge_alias_query) – Build Cypher recording every accepted merge_key's owning entity id.
- [**upsert_node_query**](#agrag.cypher.entities.upsert_node_query) – Build the Cypher for an UNWIND-batched node upsert.
- [**upsert_survivor_query**](#agrag.cypher.entities.upsert_survivor_query) – Build Cypher upserting a merge survivor with atomic accumulation.
- [**validate_identifier**](#agrag.cypher.entities.validate_identifier) – Check that a label or relationship type is a safe Cypher identifier.

**Attributes:**

- [**MERGE_ALIAS_LABEL**](#agrag.cypher.entities.MERGE_ALIAS_LABEL) –
- [**NODE_IDENTITY_LABEL**](#agrag.cypher.entities.NODE_IDENTITY_LABEL) –

##### `agrag.cypher.entities.MERGE_ALIAS_LABEL`

```python
MERGE_ALIAS_LABEL = '_AgragMergeAlias'
```

##### `agrag.cypher.entities.NODE_IDENTITY_LABEL`

```python
NODE_IDENTITY_LABEL = '_AgragNode'
```

##### `agrag.cypher.entities.clear_chunk_embedding_query`

```python
clear_chunk_embedding_query(vector_property:str) -> str
```

Build Cypher removing a vector property from Chunk nodes.

Guards on `text` the same way `set_chunk_embedding_query` does,
so a concurrent update that changed a chunk's text between this
call's embed and its clear does not accidentally wipe a newer
vector.

**Parameters:**

- **vector_property** (<code>[str](#str)</code>) – The property to remove. Must already be
  validated.

**Returns:**

- <code>[str](#str)</code> – Parameterized Cypher expecting $records, a list of dicts with
- <code>[str](#str)</code> – the keys id and expected_text.

##### `agrag.cypher.entities.clear_property_query`

```python
clear_property_query(property_name:str) -> str
```

Build Cypher removing one property from a batch of nodes, guarded by text.

Used to drop a stale value rather than leave it readable after a write
that was supposed to replace it fails partway through, such as an
embedding vector left over from before an entity's text changed. The
same `name`/`description` guard as `set_embedding_query` applies:
a record only clears the property if the node's text still matches what
this call started with, so it cannot wipe a vector a newer, still-in-
flight call has already written for different text.

**Parameters:**

- **property_name** (<code>[str](#str)</code>) – The property to remove. Must already be validated.

**Returns:**

- <code>[str](#str)</code> – Parameterized Cypher expecting $records, a list of dicts with the keys
- <code>[str](#str)</code> – id, expected_name, and expected_description.

##### `agrag.cypher.entities.fetch_all_by_label_query`

```python
fetch_all_by_label_query(label:str) -> str
```

Build Cypher paginating every node with label, for consolidate().

**Parameters:**

- **label** (<code>[str](#str)</code>) – The node label. Must already be validated.

**Returns:**

- <code>[str](#str)</code> – Parameterized Cypher expecting $skip and $limit.

##### `agrag.cypher.entities.fetch_by_merge_keys_query`

```python
fetch_by_merge_keys_query() -> str
```

Build Cypher for a batched exact-match lookup by merge key.

Resolves through the merge-key alias table (`MERGE_ALIAS_LABEL`)
rather than matching each node's own `merge_key` property directly:
that property is cleared when a node is tombstoned (see
`clear_tombstone_merge_keys_query`), so a name it once held would
otherwise become unreachable. The alias always points at the entity id
that first held the key, which may itself now be a tombstone; the caller
follows its `merged_into` chain to the live survivor.

`merge_key` is returned alongside `n` so the caller can map a row
back to the mention(s) that queried it without re-deriving a key from
the resolved entity's current name: an accepted alias (see
`upsert_merge_alias_query`) can name an entity by something other
than its current canonical name, so re-deriving would silently fail to
map those mentions back.

**Returns:**

- <code>[str](#str)</code> – Parameterized Cypher expecting $merge_keys (list of strings).

##### `agrag.cypher.entities.fetch_relations_between_query`

```python
fetch_relations_between_query(rel_type:str) -> str
```

Build Cypher for batched lookup of existing relations by endpoints.

**Parameters:**

- **rel_type** (<code>[str](#str)</code>) – The relationship type. Must already be validated.

**Returns:**

- <code>[str](#str)</code> – Parameterized Cypher expecting $pairs (list of
- <code>[str](#str)</code> – `{source_id, target_id}`). Returns each match's id and
- <code>[str](#str)</code> – source_chunk_ids alongside the pair it matched.

##### `agrag.cypher.entities.filter_clause`

```python
filter_clause(filters:dict[str, Any], node_var:str = 'node') -> tuple[str, dict[str, Any]]
```

Build a Cypher WHERE clause and parameters from a flat-dict filter.

**Parameters:**

- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\]</code>) – A flat-dict filter: a scalar value means exact match, a list
  value means any of, and all keys are AND-ed together.
- **node_var** (<code>[str](#str)</code>) – The Cypher variable bound to the node in the surrounding query.

**Returns:**

- <code>[str](#str)</code> – The `WHERE` clause text (beginning with `WHERE` when `filters` is
- <code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\]</code> – non-empty, otherwise an empty string) and the parameter dict to pass
- <code>[tuple](#tuple)\[[str](#str), [dict](#dict)\[[str](#str), [Any](#typing.Any)\]\]</code> – with it.

##### `agrag.cypher.entities.hydrate_chunks_by_id_query`

```python
hydrate_chunks_by_id_query() -> str
```

Build Cypher fetching chunks by id.

The query follows only currently valid PART_OF edges, so superseded
document versions cannot surface in retrieval. Chunks without any
PART_OF edge are also returned for direct or legacy chunk fixtures.

**Returns:**

- <code>[str](#str)</code> – Parameterized Cypher expecting $ids (list of string ids).

##### `agrag.cypher.entities.hydrate_entities_by_id_query`

```python
hydrate_entities_by_id_query() -> str
```

Build Cypher fetching entities by id, excluding tombstones.

A tombstoned node is never deleted, so a naive
`MATCH (n) WHERE n.id IN $ids` would surface one. This query
filters on `merged_into IS NULL` to return only live nodes.

**Returns:**

- <code>[str](#str)</code> – Parameterized Cypher expecting $ids (list of string ids).

##### `agrag.cypher.entities.is_safe_identifier`

```python
is_safe_identifier(value:str) -> bool
```

Report whether a label or relationship type is a safe Cypher identifier.

A non-raising counterpart to `validate_identifier`, for filtering a
batch of names (for example ones read back from the database) rather
than validating one name a caller must supply correctly.

**Parameters:**

- **value** (<code>[str](#str)</code>) – The label or relationship type to check.

**Returns:**

- <code>[bool](#bool)</code> – `True` if `value` is a safe identifier.

##### `agrag.cypher.entities.merge_key_index_query`

```python
merge_key_index_query(label:str) -> str
```

Build a CREATE INDEX query on the node merge_key property.

Backs the global exact-match lookup.

**Parameters:**

- **label** (<code>[str](#str)</code>) – The node label. Must already be validated.

**Returns:**

- <code>[str](#str)</code> – A Cypher query creating the range index if absent.

##### `agrag.cypher.entities.resolve_merged_into_query`

```python
resolve_merged_into_query() -> str
```

Return a node and the id of the node it was merged into.

A tombstoned node is never deleted; it only gains a `merged_into`
property pointing at its survivor. The pointer is a property, not a
relationship, so a chain is followed one hop per call: `merged_into`
is null on a live node and holds the next id on a tombstone.

**Returns:**

- <code>[str](#str)</code> – A parameterized query expecting an $id parameter, returning the
- <code>[str](#str)</code> – node as `node` and its survivor id as `merged_into`.

##### `agrag.cypher.entities.set_chunk_embedding_query`

```python
set_chunk_embedding_query(vector_property:str) -> str
```

Build Cypher setting a vector property on Chunk nodes.

Similar to `set_embedding_query` but guards on `text` instead of
`name`/`description`, since chunks have no name field. The text
guard prevents a stale write from overwriting a newer vector.

**Parameters:**

- **vector_property** (<code>[str](#str)</code>) – The property to set. Must already be validated.

**Returns:**

- <code>[str](#str)</code> – Parameterized Cypher expecting $records, a list of dicts with the
- <code>[str](#str)</code> – keys id, vector, and expected_text.

##### `agrag.cypher.entities.set_embedding_query`

```python
set_embedding_query(vector_property:str) -> str
```

Build Cypher setting one vector property per node, guarded by its text.

Touches only `vector_property`, unlike a full node upsert: another
write can update an entity's provenance or properties while its new
embedding is being computed, and overwriting the whole node from a
snapshot taken before that update would discard it along with
delivering the vector. The `name`/`description` match is an
optimistic-concurrency guard: a record only applies if the node's text
still matches what its vector was computed from, so a slower write from
an older call cannot overwrite a newer one's vector with a stale one.

Also requires `merged_into IS NULL`: a concurrent merge can tombstone
the node -- clearing this same property -- after this call already read
its text and started embedding, but before this write lands. Without
this guard, the write would restore a vector on an absorbed entity
purely because its name/description happened not to change, putting it
back in native vector search. `tombstone_query` sets `merged_into`
and removes the embedding in the same write, so this guard racing that
one always sees them change together.

**Parameters:**

- **vector_property** (<code>[str](#str)</code>) – The property to set. Must already be validated.

**Returns:**

- <code>[str](#str)</code> – Parameterized Cypher expecting $records, a list of dicts with the keys
- <code>[str](#str)</code> – id, vector, expected_name, and expected_description.

##### `agrag.cypher.entities.upsert_merge_alias_query`

```python
upsert_merge_alias_query() -> str
```

Build Cypher recording every accepted merge_key's owning entity id.

Every `apply_merge` call writes one of these for each merge_key the
merge accepted -- the survivor's own current name, but also every other
name (mention text or absorbed entity's name) resolution folded into
it -- so a later mention of any of those names resolves back to this
entity instead of creating a duplicate. `ON CREATE SET` only claims a
merge_key that has no alias yet: if resolution in some other merge
already accepted this same key for a different entity, that entity
keeps it. Without this, a resolution decision in one `add()` call
could silently steal a name an unrelated entity already owns.

Once created, an alias is never rewritten to point elsewhere: if the
entity it names is later itself absorbed, `fetch_by_merge_keys_query`'s
caller follows that entity's `merged_into` chain from here instead of
this table being kept in sync with every later merge.

The returned rows are what let a caller detect the case `ON CREATE SET` alone cannot: an accepted merge_key already owned by some other
live entity, not one this same merge is writing or absorbing. Neither
entity's own node merge_key collides in that case, so nothing at the
database level rejects the write; the caller must compare each row's
entity_id against its own survivor and tombstone ids itself.

**Returns:**

- <code>[str](#str)</code> – Parameterized Cypher expecting $merge_keys (list of strings) and
- <code>[str](#str)</code> – $entity_id. Returns each merge_key alongside the entity_id that now
- <code>[str](#str)</code> – owns it -- $entity_id when this call claimed or already owned it,
- <code>[str](#str)</code> – another entity's id when a different one claimed it first.

##### `agrag.cypher.entities.upsert_node_query`

```python
upsert_node_query(labels:Sequence[str]) -> str
```

Build the Cypher for an UNWIND-batched node upsert.

MERGE identity is anchored to `NODE_IDENTITY_LABEL`, not to `labels`
itself, so a node keeps resolving to the same id regardless of what
labels it currently carries. `labels` is then applied additively with
`SET`, which is idempotent (a label the node already has is a no-op)
and never removes a label a previous upsert of the same id set but this
one omits: labels only ever accumulate. Every node in one call gets the
same additive label set, since Cypher requires labels to be literal in
the query text rather than a runtime parameter; nodes whose
`NodeRecord.labels` differ need separate calls, one per distinct label
set (see `Neo4jGraphStore.upsert_nodes` for how a mixed batch is
grouped and split before reaching this builder).

Identity is reasserted after applying properties, so a caller-supplied
`properties["id"]` cannot overwrite the `id` used to `MERGE` and
orphan the node from later upserts of the same record.

**Parameters:**

- **labels** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\]</code>) – The node's labels to add, in addition to the identity anchor.
  Must already be validated, and non-empty.

**Returns:**

- <code>[str](#str)</code> – A parameterized Cypher query expecting a `$records` list parameter.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `labels` is empty, or any label is not a safe
  identifier.

##### `agrag.cypher.entities.upsert_survivor_query`

```python
upsert_survivor_query(label:str) -> str
```

Build Cypher upserting a merge survivor with atomic accumulation.

Unlike `upsert_node_query`'s plain `SET n += record.properties`
overwrite, `source_chunk_ids` and `merged_from` are unioned against
whatever the node currently has, and `merge_count` is incremented by a
delta, all read and written inside this one query. Two concurrent
callers merging into the same entity each read the node's current
accumulator values fresh here, so neither's contribution is lost to
whichever write lands second -- unlike overwriting from a full snapshot
taken before either write landed. Every other property is still applied
as-is (last write wins); resolving a conflict there needs the candidate
values, which only a Python-side read can gather, so making that
atomic too is out of scope here.

**Parameters:**

- **label** (<code>[str](#str)</code>) – The node label. Must already be validated.

**Returns:**

- <code>[str](#str)</code> – A parameterized Cypher query expecting a `$records` list
- <code>[str](#str)</code> – parameter whose items carry `id`, `properties` (every survivor
- <code>[str](#str)</code> – field except `source_chunk_ids`, `merged_from`, and
- <code>[str](#str)</code> – `merge_count`), `new_source_chunk_ids`, `new_merged_from`, and
- <code>[str](#str)</code> – `merge_count_delta`.

##### `agrag.cypher.entities.validate_identifier`

```python
validate_identifier(value:str) -> str
```

Check that a label or relationship type is a safe Cypher identifier.

**Parameters:**

- **value** (<code>[str](#str)</code>) – The label or relationship type to check.

**Returns:**

- <code>[str](#str)</code> – `value` unchanged, once validated.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `value` is not a safe identifier.

#### `agrag.cypher.merge`

Cypher for the tombstone/transfer/dedup merge path.

**Functions:**

- [**apply_relationship_dedup_delete_query**](#agrag.cypher.merge.apply_relationship_dedup_delete_query) – Build Cypher deleting relationships a dedup pass superseded.
- [**apply_relationship_dedup_update_query**](#agrag.cypher.merge.apply_relationship_dedup_update_query) – Build Cypher applying a kept relationship's merged properties.
- [**clear_tombstone_merge_keys_query**](#agrag.cypher.merge.clear_tombstone_merge_keys_query) – Build Cypher removing merge_key from nodes about to be absorbed.
- [**delete_internal_relationships_query**](#agrag.cypher.merge.delete_internal_relationships_query) – Build Cypher deleting edges that would become meaningless self-links.
- [**fetch_node_relationships_query**](#agrag.cypher.merge.fetch_node_relationships_query) – Build Cypher fetching one direction of a node's own relationships.
- [**tombstone_query**](#agrag.cypher.merge.tombstone_query) – Build Cypher marking one or more nodes as merged, never deleting them.
- [**transfer_relationships_query**](#agrag.cypher.merge.transfer_relationships_query) – Build Cypher moving one direction of a tombstoned node's relationships.

##### `agrag.cypher.merge.apply_relationship_dedup_delete_query`

```python
apply_relationship_dedup_delete_query() -> str
```

Build Cypher deleting relationships a dedup pass superseded.

**Returns:**

- <code>[str](#str)</code> – Parameterized Cypher expecting $delete_ids (list of
- <code>[str](#str)</code> – `{id, rel_type}`).

##### `agrag.cypher.merge.apply_relationship_dedup_update_query`

```python
apply_relationship_dedup_update_query() -> str
```

Build Cypher applying a kept relationship's merged properties.

**Returns:**

- <code>[str](#str)</code> – Parameterized Cypher expecting $updates (list of
- <code>[str](#str)</code> – `{id, rel_type, properties}`), where properties is the full merged
- <code>[str](#str)</code> – property map -- not just source_chunk_ids -- so a duplicate's other
- <code>[str](#str)</code> – fields are not silently dropped when its edge is deleted.

##### `agrag.cypher.merge.clear_tombstone_merge_keys_query`

```python
clear_tombstone_merge_keys_query(label:str) -> str
```

Build Cypher removing merge_key from nodes about to be absorbed.

Must run before `upsert_survivor_query` writes the survivor, not after
`tombstone_query`: canonical selection can choose a different node as
survivor than the one a property rule (e.g. KEEP_FIRST) resolves the
name from, so the survivor's resolved merge_key can equal a still-live
tombstone's own merge_key. Writing the survivor first would then collide
with the per-label `merge_key` uniqueness constraint, since both nodes
would briefly hold the same value.

**Parameters:**

- **label** (<code>[str](#str)</code>) – The node label. Must already be validated.

**Returns:**

- <code>[str](#str)</code> – Parameterized Cypher expecting $tombstone_ids.

##### `agrag.cypher.merge.delete_internal_relationships_query`

```python
delete_internal_relationships_query() -> str
```

Build Cypher deleting edges that would become meaningless self-links.

Covers two cases, both before any transfer runs, inside the same
transaction as the merge:

- An edge between two absorbed nodes: left untransferred, it would
  become a stale `survivor->tombstone` edge after the first transfer.
- An edge directly between an absorbed node and its own survivor:
  `transfer_relationships_query` excludes these (`other.id <> $survivor_id`), since transferring one would create a
  `survivor->survivor` self-loop that no relation type's semantics
  call for. Deleting them here, in both directions, is what keeps them
  from being silently orphaned on the tombstone instead.

**Returns:**

- <code>[str](#str)</code> – Parameterized Cypher expecting $tombstone_ids (list of strings) and
- <code>[str](#str)</code> – $survivor_id.

##### `agrag.cypher.merge.fetch_node_relationships_query`

```python
fetch_node_relationships_query(*, outgoing:bool) -> str
```

Build Cypher fetching one direction of a node's own relationships.

Run against the survivor after every transfer completes, so the dedup
pass that follows sees the survivor's whole neighbourhood in that
direction -- both freshly transferred edges and ones it already had --
rather than only what one transfer call happened to move.

**Parameters:**

- **outgoing** (<code>[bool](#bool)</code>) – True fetches (node)-[r]->(other) edges. False fetches
  (other)-[r]->(node) edges.

**Returns:**

- <code>[str](#str)</code> – Parameterized Cypher expecting $node_id.

##### `agrag.cypher.merge.tombstone_query`

```python
tombstone_query(label:str, *, vector_property:str) -> str
```

Build Cypher marking one or more nodes as merged, never deleting them.

Also removes `vector_property`: a native Neo4j vector index only covers
nodes that currently carry the indexed property, so dropping it takes the
tombstone out of vector search immediately, with no query-time filter and
no dependency on a later re-embed ever running against it.

**Parameters:**

- **label** (<code>[str](#str)</code>) – The node label. Must already be validated.
- **vector_property** (<code>[str](#str)</code>) – The embedding property to remove. Must already be
  validated.

**Returns:**

- <code>[str](#str)</code> – Parameterized Cypher expecting $tombstone_ids and $survivor_id.

##### `agrag.cypher.merge.transfer_relationships_query`

```python
transfer_relationships_query(*, outgoing:bool) -> str
```

Build Cypher moving one direction of a tombstoned node's relationships.

**Parameters:**

- **outgoing** (<code>[bool](#bool)</code>) – True moves (tombstone)-[r]->(other) edges. False moves
  (other)-[r]->(tombstone) edges.

**Returns:**

- <code>[str](#str)</code> – Parameterized Cypher expecting $tombstone_id and $survivor_id.

#### `agrag.cypher.relations`

Cypher builders for relationship writes and graph traversal.

Leaf module: imports nothing from `agrag.graphdb`. See `entities.py` for the
identifier-validation contract shared by every Cypher builder.

**Functions:**

- [**bfs_expand_query**](#agrag.cypher.relations.bfs_expand_query) – Build Cypher for BFS expansion from seed entity ids.
- [**chunks_mentioning_entities_query**](#agrag.cypher.relations.chunks_mentioning_entities_query) – Build Cypher finding chunks that mention given entities.
- [**close_part_of_query**](#agrag.cypher.relations.close_part_of_query) – Build Cypher that closes currently valid document-to-chunk edges.
- [**entities_mentioned_in_chunks_query**](#agrag.cypher.relations.entities_mentioned_in_chunks_query) – Build Cypher finding entities mentioned by given chunks.
- [**fetch_all_relations_query**](#agrag.cypher.relations.fetch_all_relations_query) – Build Cypher paginating every live domain relationship.
- [**fetch_all_relations_query_cursor**](#agrag.cypher.relations.fetch_all_relations_query_cursor) – Build Cypher paginating every live domain relationship via keyset.
- [**upsert_relation_query**](#agrag.cypher.relations.upsert_relation_query) – Build the Cypher for an UNWIND-batched relationship upsert.

##### `agrag.cypher.relations.bfs_expand_query`

```python
bfs_expand_query(*, depth:int = 2, limit:int = 50, filters:dict[str, Any] | None = None, relation_types:Sequence[str] | None = None) -> tuple[str, dict[str, Any]]
```

Build Cypher for BFS expansion from seed entity ids.

Traverses outgoing relationships from a set of seed entities, bounded
by `depth` hops and `limit` total result nodes. The depth is
formatted into the query text (not a parameter) because Neo4j does
not accept a parameter for a variable-length relationship bound. It
must come from `RetrievalSettings`, never from user input.

`relation_types` restricts which relationships a traversal may
cross. Neo4j does not accept a parameter for relationship types
either, so each type is validated and formatted into the pattern.

`depth` is clamped to [1, 10] and `limit` to [1, 1000] so
misconfigured or malicious settings cannot produce unbounded
traversals. The clamp is applied here, closest to the Cypher
interpolation, so every caller benefits.

Result nodes are restricted to `_AgragNode` entities that are
**not** `Chunk` nodes: chunks are intermediate path nodes only,
never returned as BFS results.

**Parameters:**

- **depth** (<code>[int](#int)</code>) – The maximum BFS hops. Clamped to [1, 10].
- **limit** (<code>[int](#int)</code>) – The maximum number of result nodes. Clamped to [1, 1000].
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – Optional flat-dict filter applied to neighbor nodes.
  A scalar value means exact match, a list means any of.
- **relation_types** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\] | None</code>) – Optional relationship types the traversal may
  cross. None or empty crosses every type.

**Returns:**

- <code>[str](#str)</code> – A `(query, params)` tuple. The query expects `$seed_ids`
- <code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\]</code> – (list of string ids) plus any filter parameters.

**Raises:**

- <code>[ValueError](#ValueError)</code> – A relation type is not a safe Cypher identifier.

##### `agrag.cypher.relations.chunks_mentioning_entities_query`

```python
chunks_mentioning_entities_query() -> str
```

Build Cypher finding chunks that mention given entities.

Walks the MENTIONED_IN edge from Chunk to Entity. Returns chunks
that reference any of the given entity ids.

**Returns:**

- <code>[str](#str)</code> – Parameterized Cypher expecting $entity_ids (list of string ids).

##### `agrag.cypher.relations.close_part_of_query`

```python
close_part_of_query() -> str
```

Build Cypher that closes currently valid document-to-chunk edges.

##### `agrag.cypher.relations.entities_mentioned_in_chunks_query`

```python
entities_mentioned_in_chunks_query() -> str
```

Build Cypher finding entities mentioned by given chunks.

Walks the MENTIONED_IN edge from Chunk to Entity in reverse. Returns
entities referenced by any of the given chunk ids.

**Returns:**

- <code>[str](#str)</code> – Parameterized Cypher expecting $chunk_ids (list of string ids).

##### `agrag.cypher.relations.fetch_all_relations_query`

```python
fetch_all_relations_query() -> str
```

Build Cypher paginating every live domain relationship.

Used by Graph.detect_communities() to build the weighted edge list for
clustering. Excludes MENTIONED_IN and MEMBER_OF (system edges, not
entity-graph topology) and any endpoint that is a Chunk, a Community,
or a tombstone.

`ORDER BY` includes `type(r)` and `r.id` after `(a.id, b.id)`
because two distinct relationships (different types, or the same type
with different ids) can share the same endpoints -- see
`upsert_relation_query`. Without a total order, Neo4j does not
guarantee a stable row order across separate paged queries, so a page
boundary falling inside such a group can duplicate or drop rows.

**Returns:**

- <code>[str](#str)</code> – Parameterized Cypher expecting $skip and $limit. Returns each
- <code>[str](#str)</code> – relation's source_id, target_id, source_chunk_ids, and rel_type.

##### `agrag.cypher.relations.fetch_all_relations_query_cursor`

```python
fetch_all_relations_query_cursor() -> str
```

Build Cypher paginating every live domain relationship via keyset.

Keyset variant of :func:`fetch_all_relations_query` for large graphs
where `SKIP` becomes expensive. Orders by `(a.id, b.id, type(r), r.id)` and pages by the last seen tuple; the first page uses
`last_a=""`, `last_b=""`, `last_type=""` and `last_rel_id=""`.

The relationship type and id break ties on `(a.id, b.id)`: two
distinct relationships (different types, or the same type with
different ids) can share the same endpoints -- see
`upsert_relation_query`. Ordering by endpoints alone would let a
page boundary fall inside such a group, silently excluding the
remaining relationships for that pair from every later page.

**Returns:**

- <code>[str](#str)</code> – Parameterized Cypher expecting `$last_a`, `$last_b`,
- <code>[str](#str)</code> – `$last_type`, `$last_rel_id` and `$limit`.

##### `agrag.cypher.relations.upsert_relation_query`

```python
upsert_relation_query(rel_type:str) -> str
```

Build the Cypher for an UNWIND-batched relationship upsert.

Relationship identity is `record.id`, not the `(start, end, type)`
triple: two relationships of this type between the same nodes keep
separate identities when their ids differ, so parallel relationships do
not collapse into one. When a record's endpoints move, the relationship
keeps its id: the stale copy at the old endpoints is deleted before the
new one is written, backed by the per-type uniqueness constraint from
`relation_id_constraint_query`. A relationship's type is immutable once
written; retyping one requires deleting it under its old type first, since
a single upsert call only ever targets one type. Identity is reasserted
after applying properties, so a caller-supplied `properties["id"]`
cannot overwrite the `id` used to `MERGE` and orphan the relationship
from later upserts of the same record.

`source_chunk_ids` is unioned against whatever is already on the
relationship at write time, inside this same query, rather than blindly
overwritten: two concurrent callers upserting the same relationship each
compute their own union from a read taken before either write lands, so
without this, whichever caller's write commits second would silently
discard the chunk ids the other one contributed. Reading the current
value here, inside the same MERGE, keeps the union correct regardless of
which caller's read was stale.

**Parameters:**

- **rel_type** (<code>[str](#str)</code>) – The relationship type. Must already be validated.

**Returns:**

- <code>[str](#str)</code> – A parameterized Cypher query expecting a `$records` list parameter whose
- <code>[str](#str)</code> – items carry `id`, `start_id`, `end_id`, and `properties` keys.
- <code>[str](#str)</code> – `properties` may include `source_chunk_ids`; other keys are
- <code>[str](#str)</code> – applied as-is. The query returns one row with `id` for every record
- <code>[str](#str)</code> – whose endpoints matched and was processed.

#### `agrag.cypher.safety`

Safety gate for generated Cypher queries.

**Classes:**

- [**UnsafeCypherError**](#agrag.cypher.safety.UnsafeCypherError) – Raised when a generated Cypher query contains a write clause.

**Functions:**

- [**reject_write_cypher**](#agrag.cypher.safety.reject_write_cypher) – Raise fast on an obvious write clause, ahead of EXPLAIN.
- [**strip_cypher_syntax**](#agrag.cypher.safety.strip_cypher_syntax) – Blank string literals, comments, and backtick identifiers.

##### `agrag.cypher.safety.UnsafeCypherError`

Bases: <code>[Exception](#Exception)</code>

Raised when a generated Cypher query contains a write clause.

##### `agrag.cypher.safety.reject_write_cypher`

```python
reject_write_cypher(query:str) -> None
```

Raise fast on an obvious write clause, ahead of EXPLAIN.

This is a cheap pre-filter, not the safety boundary:
execute_read's read transaction is what actually prevents a
write from running, since Neo4j itself rejects one there. This
check exists so a write-shaped generated query fails immediately
instead of spending an EXPLAIN round trip first.

Keywords are matched case-insensitively, and only outside string
literals, comments, and backtick identifiers, so a lowercase
`delete` or a quote inside a comment cannot desync the scan.
The check is conservative: a write keyword used as a property
name (e.g. `RETURN n.set`) is also rejected, acceptable for a
pre-filter that guards model-generated text.

**Parameters:**

- **query** (<code>[str](#str)</code>) – The Cypher text a BAML call produced.

**Raises:**

- <code>[UnsafeCypherError](#agrag.cypher.safety.UnsafeCypherError)</code> – The query contains a write keyword outside
  a string literal, comment, or backtick identifier.

##### `agrag.cypher.safety.strip_cypher_syntax`

```python
strip_cypher_syntax(query:str) -> str
```

Blank string literals, comments, and backtick identifiers.

Replaces the contents of string literals, `//` and `/* */`
comments, and backtick-quoted identifiers with spaces, keeping every
other character intact so token boundaries survive. Scans char by
char and honors backslash and doubled-quote escapes, so an escaped
quote inside a literal cannot close the scan early and let a real
keyword after it hide inside a bogus "string".

**Parameters:**

- **query** (<code>[str](#str)</code>) – The Cypher text to scrub.

**Returns:**

- <code>[str](#str)</code> – The query with literal, comment, and identifier content blanked,
- <code>[str](#str)</code> – layout otherwise unchanged.

#### `agrag.cypher.schema`

Cypher builders for constraints and native vector indexes.

Leaf module: imports nothing from `agrag.graphdb`. See `entities.py` for the
identifier-validation contract shared by every Cypher builder.

**Functions:**

- [**merge_alias_constraint_query**](#agrag.cypher.schema.merge_alias_constraint_query) – Build a CREATE CONSTRAINT query making the merge-key alias table unique.
- [**merge_key_constraint_query**](#agrag.cypher.schema.merge_key_constraint_query) – Build a CREATE CONSTRAINT query making `merge_key` unique per label.
- [**node_id_constraint_query**](#agrag.cypher.schema.node_id_constraint_query) – Build a CREATE CONSTRAINT query making `id` unique per node.
- [**plain_index_query**](#agrag.cypher.schema.plain_index_query) – Build a CREATE INDEX query on the node `id` property.
- [**relation_id_constraint_query**](#agrag.cypher.schema.relation_id_constraint_query) – Build a CREATE CONSTRAINT query making `id` unique per relationship type.
- [**vector_index_name**](#agrag.cypher.schema.vector_index_name) – Derive the deterministic name a vector index is created under.
- [**vector_index_query**](#agrag.cypher.schema.vector_index_query) – Build a CREATE VECTOR INDEX query for native vector search.
- [**vector_search_query**](#agrag.cypher.schema.vector_search_query) – Build a native vector search query and its filter parameters.

##### `agrag.cypher.schema.merge_alias_constraint_query`

```python
merge_alias_constraint_query() -> str
```

Build a CREATE CONSTRAINT query making the merge-key alias table unique.

One global constraint, not per label: `MERGE_ALIAS_LABEL` is shared
across every entity type, and `merge_key` already embeds the label
(see `Entity.merge_key`), so a single uniqueness constraint on it is
sufficient.

**Returns:**

- <code>[str](#str)</code> – A Cypher query creating the uniqueness constraint if absent.

##### `agrag.cypher.schema.merge_key_constraint_query`

```python
merge_key_constraint_query(label:str) -> str
```

Build a CREATE CONSTRAINT query making `merge_key` unique per label.

Backs the concurrent-ingestion safety tier: two concurrent `add()` calls
for the same `(label, normalized name)` cannot both create a canonical
node; the second fails the constraint and is resolved to the canonical via
the merge path. A node absorbed by a merge has its `merge_key` cleared
before it is marked `merged_into`, so the constraint permits one live
survivor per key plus any number of tombstones.

**Parameters:**

- **label** (<code>[str](#str)</code>) – The node label. Must already be validated.

**Returns:**

- <code>[str](#str)</code> – A Cypher query creating the uniqueness constraint if absent.

##### `agrag.cypher.schema.node_id_constraint_query`

```python
node_id_constraint_query(label:str) -> str
```

Build a CREATE CONSTRAINT query making `id` unique per node.

Neo4j constraint names share one flat, global namespace regardless of
whether they apply to a node label or a relationship type, so this name
is kind-prefixed and length-prefixed the same way `vector_index_name`
is: label `"X_rel"` and relationship type `"X"` would otherwise both
produce `X_rel_id_unique`, and `IF NOT EXISTS` would then silently
leave the second one never created.

**Parameters:**

- **label** (<code>[str](#str)</code>) – The node label. Must already be validated.

**Returns:**

- <code>[str](#str)</code> – A Cypher query creating the uniqueness constraint if absent.

##### `agrag.cypher.schema.plain_index_query`

```python
plain_index_query(label:str) -> str
```

Build a CREATE INDEX query on the node `id` property.

**Parameters:**

- **label** (<code>[str](#str)</code>) – The node label. Must already be validated.

**Returns:**

- <code>[str](#str)</code> – A Cypher query creating the range index if absent.

##### `agrag.cypher.schema.relation_id_constraint_query`

```python
relation_id_constraint_query(rel_type:str) -> str
```

Build a CREATE CONSTRAINT query making `id` unique per relationship type.

This backs the stale-relationship lookup in `upsert_relation_query` with
an index and guarantees at most one relationship of `rel_type` carries a
given id. See `node_id_constraint_query` for why the name is
kind-prefixed and length-prefixed rather than a plain concatenation.

**Parameters:**

- **rel_type** (<code>[str](#str)</code>) – The relationship type. Must already be validated.

**Returns:**

- <code>[str](#str)</code> – A Cypher query creating the uniqueness constraint if absent.

##### `agrag.cypher.schema.vector_index_name`

```python
vector_index_name(label:str, vector_property:str) -> str
```

Derive the deterministic name a vector index is created under.

Each component is length-prefixed so the encoding is unambiguous: a plain
join like `f"{label}_{vector_property}_vector"` would let a label and
property containing underscores collide, for example `("A_B", "C")` and
`("A", "B_C")` both joining to `"A_B_C_vector"`. A collision would
make `ensure_vector_index` reuse one index for two different label and
property pairs, and `vector_search` would then search the wrong nodes.
`ensure_vector_index` and `vector_search` both call this function, so
they always agree on the name.

**Parameters:**

- **label** (<code>[str](#str)</code>) – The node label. Must already be validated.
- **vector_property** (<code>[str](#str)</code>) – The vector property name. Must already be validated.

**Returns:**

- <code>[str](#str)</code> – The index name `ensure_vector_index` and `vector_search` share.

##### `agrag.cypher.schema.vector_index_query`

```python
vector_index_query(label:str, vector_property:str, dimensions:int, distance:Distance) -> str
```

Build a CREATE VECTOR INDEX query for native vector search.

**Parameters:**

- **label** (<code>[str](#str)</code>) – The node label. Must already be validated.
- **vector_property** (<code>[str](#str)</code>) – The vector property name. Must already be validated.
- **dimensions** (<code>[int](#int)</code>) – The embedding dimension.
- **distance** (<code>[Distance](#agrag.common.data_models.vector_record.Distance)</code>) – The distance metric, mapped to Neo4j's similarity function.

**Returns:**

- <code>[str](#str)</code> – A Cypher query creating the vector index if absent.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `distance` is not a metric Neo4j vector indexes support.

##### `agrag.cypher.schema.vector_search_query`

```python
vector_search_query(index_name:str, filters:dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]
```

Build a native vector search query and its filter parameters.

**Parameters:**

- **index_name** (<code>[str](#str)</code>) – The vector index name from `vector_index_name`.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – An optional flat-dict filter applied with `WHERE`.

**Returns:**

- <code>[str](#str)</code> – The Cypher query yielding `node` and `score`, and a parameter dict
- <code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\]</code> – holding only the filter parameters (the caller adds `index`, `k`,
- <code>[tuple](#tuple)\[[str](#str), [dict](#dict)\[[str](#str), [Any](#typing.Any)\]\]</code> – and `vector`).

### `agrag.embedding`

Text embedding: turn strings into dense vectors.

**Modules:**

- [**base**](#agrag.embedding.base) – The Embedder and EmbeddingCache protocols.
- [**errors**](#agrag.embedding.errors) – Errors that the embedding layer raises.
- [**fastembed_bm25**](#agrag.embedding.fastembed_bm25) – BM25 sparse embedder backed by FastEmbed.
- [**sentence_transformers**](#agrag.embedding.sentence_transformers) – Sentence-transformers embedder implementation.
- [**settings**](#agrag.embedding.settings) – Settings for the sentence-transformers embedder.
- [**sparse_base**](#agrag.embedding.sparse_base) – Sparse lexical vectors and the sparse embedder protocol.

**Classes:**

- [**Embedder**](#agrag.embedding.Embedder) – A component that turns text into dense embedding vectors.
- [**EmbeddingSettings**](#agrag.embedding.EmbeddingSettings) – Sentence-transformers embedder configuration.
- [**FastEmbedBM25Embedder**](#agrag.embedding.FastEmbedBM25Embedder) – A sparse BM25 embedder built on FastEmbed.
- [**SentenceTransformerEmbedder**](#agrag.embedding.SentenceTransformerEmbedder) – An embedder backed by sentence-transformers.
- [**SparseEmbedder**](#agrag.embedding.SparseEmbedder) – A component that turns text into sparse lexical vectors, for hybrid search.
- [**SparseVector**](#agrag.embedding.SparseVector) – A sparse vector: nonzero indices and their values.

**Functions:**

- [**build_embedder**](#agrag.embedding.build_embedder) – Build an embedder from a model name, or return an embedder unchanged.

#### `agrag.embedding.Embedder`

Bases: <code>[ABC](#abc.ABC)</code>

A component that turns text into dense embedding vectors.

**Functions:**

- [**dimensions**](#agrag.embedding.Embedder.dimensions) – Return the dimension of the vectors this embedder produces.
- [**embed**](#agrag.embedding.Embedder.embed) – Embed a batch of texts.
- [**embed_one**](#agrag.embedding.Embedder.embed_one) – Embed a single text.

**Attributes:**

- [**distance**](#agrag.embedding.Embedder.distance) (<code>[Distance](#agrag.common.data_models.vector_record.Distance)</code>) – Return the distance metric for vector indexes created for this embedder.
- [**model**](#agrag.embedding.Embedder.model) (<code>[str](#str)</code>) –

##### `agrag.embedding.Embedder.dimensions`

```python
dimensions() -> int
```

Return the dimension of the vectors this embedder produces.

Async because a lazily-loaded embedder may need to load its model to
answer, and that load must go through the same worker-thread/lock
path `embed` uses rather than blocking the event loop.

##### `agrag.embedding.Embedder.distance`

```python
distance: Distance
```

Return the distance metric for vector indexes created for this embedder.

Defaults to cosine, which matches normalized sentence-transformer models.
Concrete embedders may override when their vectors use a different
metric.

##### `agrag.embedding.Embedder.embed`

```python
embed(texts:Sequence[str]) -> list[list[float]]
```

Embed a batch of texts.

**Parameters:**

- **texts** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\]</code>) – The texts to embed, in order.

**Returns:**

- <code>[list](#list)\[[list](#list)\[[float](#float)\]\]</code> – One vector per input text, in the same order.

##### `agrag.embedding.Embedder.embed_one`

```python
embed_one(text:str) -> list[float]
```

Embed a single text.

**Parameters:**

- **text** (<code>[str](#str)</code>) – The text to embed.

**Returns:**

- <code>[list](#list)\[[float](#float)\]</code> – The text's embedding vector.

##### `agrag.embedding.Embedder.model`

```python
model: str
```

#### `agrag.embedding.EmbeddingSettings`

Bases: <code>[BaseSettings](#pydantic_settings.BaseSettings)</code>

Sentence-transformers embedder configuration.

All fields are overridable via environment variables with the
`EMBEDDING_` prefix.

**Attributes:**

- [**model**](#agrag.embedding.EmbeddingSettings.model) (<code>[str](#str)</code>) – The sentence-transformers model name or path. Env: `EMBEDDING_MODEL`.
- [**device**](#agrag.embedding.EmbeddingSettings.device) (<code>[str](#str) | None</code>) – The device to load the model on, such as `"cpu"` or `"cuda"`.
  `None` uses sentence-transformers' own default detection. Env:
  `EMBEDDING_DEVICE`.
- [**normalize**](#agrag.embedding.EmbeddingSettings.normalize) (<code>[bool](#bool)</code>) – Whether to L2-normalize output vectors. Env: `EMBEDDING_NORMALIZE`.
- [**batch_size**](#agrag.embedding.EmbeddingSettings.batch_size) (<code>[int](#int)</code>) – The number of texts encoded per `model.encode` call. Env:
  `EMBEDDING_BATCH_SIZE`.
- [**cache_folder**](#agrag.embedding.EmbeddingSettings.cache_folder) (<code>[str](#str) | None</code>) – Where sentence-transformers caches downloaded models.
  `None` uses the library default. Env: `EMBEDDING_CACHE_FOLDER`.

##### `agrag.embedding.EmbeddingSettings.batch_size`

```python
batch_size: int = 32
```

##### `agrag.embedding.EmbeddingSettings.cache_folder`

```python
cache_folder: str | None = None
```

##### `agrag.embedding.EmbeddingSettings.device`

```python
device: str | None = None
```

##### `agrag.embedding.EmbeddingSettings.model`

```python
model: str = 'ibm-granite/granite-embedding-small-english-r2'
```

##### `agrag.embedding.EmbeddingSettings.model_config`

```python
model_config = SettingsConfigDict(env_prefix='EMBEDDING_', env_file='.env', extra='ignore')
```

##### `agrag.embedding.EmbeddingSettings.normalize`

```python
normalize: bool = True
```

#### `agrag.embedding.FastEmbedBM25Embedder`

```python
FastEmbedBM25Embedder(*, model:str | None = None) -> None
```

Bases: <code>[SparseEmbedder](#agrag.embedding.sparse_base.SparseEmbedder)</code>

A sparse BM25 embedder built on FastEmbed.

The model loads lazily on first `embed`, so constructing the embedder
does not download weights. Each blocking call into FastEmbed runs in a
worker thread, keeping the event loop free. FastEmbed ships with the
`qdrant` extra, so a clean install without that extra raises
`EmbeddingMissingExtraError` rather than `ImportError`.

**Functions:**

- [**embed**](#agrag.embedding.FastEmbedBM25Embedder.embed) – Embed a batch of documents into BM25 sparse vectors.
- [**query_embed**](#agrag.embedding.FastEmbedBM25Embedder.query_embed) – Embed a batch of search queries into BM25 sparse vectors.

**Attributes:**

- [**model**](#agrag.embedding.FastEmbedBM25Embedder.model) (<code>[str](#str)</code>) – The configured model name, or the FastEmbed default when unset.

**Parameters:**

- **model** (<code>[str](#str) | None</code>) – The FastEmbed BM25 model name. Defaults to FastEmbed's
  built-in BM25 model.

##### `agrag.embedding.FastEmbedBM25Embedder.embed`

```python
embed(texts:Sequence[str]) -> list[SparseVector]
```

Embed a batch of documents into BM25 sparse vectors.

Applies FastEmbed's document-side term-frequency and length
normalization weighting. Use `query_embed` for search queries.

**Parameters:**

- **texts** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\]</code>) – The document texts to embed, in order.

**Returns:**

- <code>[list](#list)\[[SparseVector](#agrag.embedding.sparse_base.SparseVector)\]</code> – One sparse vector per input text, in the same order.

##### `agrag.embedding.FastEmbedBM25Embedder.model`

```python
model: str
```

The configured model name, or the FastEmbed default when unset.

##### `agrag.embedding.FastEmbedBM25Embedder.query_embed`

```python
query_embed(texts:Sequence[str]) -> list[SparseVector]
```

Embed a batch of search queries into BM25 sparse vectors.

Uses FastEmbed's `query_embed`, which assigns each unique query
term a uniform weight of `1.0` rather than the document-side
term-frequency and length-normalization weighting `embed` applies;
IDF weighting is applied separately by the sparse index's
`Modifier.IDF` at query time.

**Parameters:**

- **texts** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\]</code>) – The query texts to embed, in order.

**Returns:**

- <code>[list](#list)\[[SparseVector](#agrag.embedding.sparse_base.SparseVector)\]</code> – One sparse vector per input text, in the same order.

#### `agrag.embedding.SentenceTransformerEmbedder`

```python
SentenceTransformerEmbedder(*, settings:EmbeddingSettings | None = None, cache:EmbeddingCache | None = None, model:object | None = None) -> None
```

Bases: <code>[Embedder](#agrag.embedding.base.Embedder)</code>

An embedder backed by sentence-transformers.

The model loads lazily on first `embed`, so constructing the embedder
does not touch the GPU or download weights. Every blocking call into the
model runs in a worker thread (`asyncio.to_thread`), so the event loop
stays free for other work while a large batch encodes.

**Functions:**

- [**dimensions**](#agrag.embedding.SentenceTransformerEmbedder.dimensions) – Return the dimension the loaded model produces.
- [**embed**](#agrag.embedding.SentenceTransformerEmbedder.embed) – Embed a batch of texts, using the cache where possible.
- [**embed_one**](#agrag.embedding.SentenceTransformerEmbedder.embed_one) – Embed a single text.

**Attributes:**

- [**distance**](#agrag.embedding.SentenceTransformerEmbedder.distance) (<code>[Distance](#agrag.common.data_models.vector_record.Distance)</code>) – Return the distance metric for vector indexes created for this embedder.
- [**model**](#agrag.embedding.SentenceTransformerEmbedder.model) (<code>[str](#str)</code>) – The configured model name.

**Parameters:**

- **settings** (<code>[EmbeddingSettings](#agrag.embedding.settings.EmbeddingSettings) | None</code>) – Embedder configuration. Defaults to `EmbeddingSettings()`.
- **cache** (<code>[EmbeddingCache](#agrag.embedding.base.EmbeddingCache) | None</code>) – An optional content-addressed cache. Defaults to a no-op cache.
- **model** (<code>[object](#object) | None</code>) – A pre-built sentence-transformers model, for tests. When set,
  `__init__` imports nothing and `embed` calls this object
  directly instead of building one.

##### `agrag.embedding.SentenceTransformerEmbedder.dimensions`

```python
dimensions() -> int
```

Return the dimension the loaded model produces.

Calling this loads the model the first time, the same
lock-protected, worker-thread path `embed` uses, so it is safe to
call concurrently with `embed` without stalling the event loop or
loading a second copy of the model.

**Raises:**

- <code>[EmbeddingMissingExtraError](#agrag.embedding.errors.EmbeddingMissingExtraError)</code> – sentence-transformers is not installed.

##### `agrag.embedding.SentenceTransformerEmbedder.distance`

```python
distance: Distance
```

Return the distance metric for vector indexes created for this embedder.

Defaults to cosine, which matches normalized sentence-transformer models.
Concrete embedders may override when their vectors use a different
metric.

##### `agrag.embedding.SentenceTransformerEmbedder.embed`

```python
embed(texts:Sequence[str]) -> list[list[float]]
```

Embed a batch of texts, using the cache where possible.

**Parameters:**

- **texts** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\]</code>) – The texts to embed, in order.

**Returns:**

- <code>[list](#list)\[[list](#list)\[[float](#float)\]\]</code> – One vector per input text, in the same order.

##### `agrag.embedding.SentenceTransformerEmbedder.embed_one`

```python
embed_one(text:str) -> list[float]
```

Embed a single text.

**Parameters:**

- **text** (<code>[str](#str)</code>) – The text to embed.

**Returns:**

- <code>[list](#list)\[[float](#float)\]</code> – The text's embedding vector.

##### `agrag.embedding.SentenceTransformerEmbedder.model`

```python
model: str
```

The configured model name.

#### `agrag.embedding.SparseEmbedder`

Bases: <code>[ABC](#abc.ABC)</code>

A component that turns text into sparse lexical vectors, for hybrid search.

**Functions:**

- [**embed**](#agrag.embedding.SparseEmbedder.embed) – Embed a batch of documents into sparse vectors.
- [**query_embed**](#agrag.embedding.SparseEmbedder.query_embed) – Embed a batch of search queries into sparse vectors.

**Attributes:**

- [**model**](#agrag.embedding.SparseEmbedder.model) (<code>[str](#str)</code>) –

##### `agrag.embedding.SparseEmbedder.embed`

```python
embed(texts:Sequence[str]) -> list[SparseVector]
```

Embed a batch of documents into sparse vectors.

**Parameters:**

- **texts** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\]</code>) – The document texts to embed, in order.

**Returns:**

- <code>[list](#list)\[[SparseVector](#agrag.embedding.sparse_base.SparseVector)\]</code> – One sparse vector per input text, in the same order.

##### `agrag.embedding.SparseEmbedder.model`

```python
model: str
```

##### `agrag.embedding.SparseEmbedder.query_embed`

```python
query_embed(texts:Sequence[str]) -> list[SparseVector]
```

Embed a batch of search queries into sparse vectors.

Query-side sparse embedding is not always the same computation as
document-side embedding: BM25, for example, applies term-frequency
and document-length normalization on the document side but only a
uniform per-term weight on the query side, since IDF weighting is
applied by the sparse index at query time instead. Implementations
with no such asymmetry may implement this identically to `embed`.

**Parameters:**

- **texts** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\]</code>) – The query texts to embed, in order.

**Returns:**

- <code>[list](#list)\[[SparseVector](#agrag.embedding.sparse_base.SparseVector)\]</code> – One sparse vector per input text, in the same order.

#### `agrag.embedding.SparseVector`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

A sparse vector: nonzero indices and their values.

**Attributes:**

- [**indices**](#agrag.embedding.SparseVector.indices) (<code>[list](#list)\[[int](#int)\]</code>) – The positions of nonzero entries.
- [**values**](#agrag.embedding.SparseVector.values) (<code>[list](#list)\[[float](#float)\]</code>) – The weight at each index, aligned with `indices`.

##### `agrag.embedding.SparseVector.indices`

```python
indices: list[int]
```

##### `agrag.embedding.SparseVector.values`

```python
values: list[float]
```

#### `agrag.embedding.base`

The Embedder and EmbeddingCache protocols.

**Classes:**

- [**Embedder**](#agrag.embedding.base.Embedder) – A component that turns text into dense embedding vectors.
- [**EmbeddingCache**](#agrag.embedding.base.EmbeddingCache) – A content-addressed cache for embedding vectors.
- [**NullEmbeddingCache**](#agrag.embedding.base.NullEmbeddingCache) – A cache that never stores anything. The default when none is injected.

##### `agrag.embedding.base.Embedder`

Bases: <code>[ABC](#abc.ABC)</code>

A component that turns text into dense embedding vectors.

**Functions:**

- [**dimensions**](#agrag.embedding.base.Embedder.dimensions) – Return the dimension of the vectors this embedder produces.
- [**embed**](#agrag.embedding.base.Embedder.embed) – Embed a batch of texts.
- [**embed_one**](#agrag.embedding.base.Embedder.embed_one) – Embed a single text.

**Attributes:**

- [**distance**](#agrag.embedding.base.Embedder.distance) (<code>[Distance](#agrag.common.data_models.vector_record.Distance)</code>) – Return the distance metric for vector indexes created for this embedder.
- [**model**](#agrag.embedding.base.Embedder.model) (<code>[str](#str)</code>) –

###### `agrag.embedding.base.Embedder.dimensions`

```python
dimensions() -> int
```

Return the dimension of the vectors this embedder produces.

Async because a lazily-loaded embedder may need to load its model to
answer, and that load must go through the same worker-thread/lock
path `embed` uses rather than blocking the event loop.

###### `agrag.embedding.base.Embedder.distance`

```python
distance: Distance
```

Return the distance metric for vector indexes created for this embedder.

Defaults to cosine, which matches normalized sentence-transformer models.
Concrete embedders may override when their vectors use a different
metric.

###### `agrag.embedding.base.Embedder.embed`

```python
embed(texts:Sequence[str]) -> list[list[float]]
```

Embed a batch of texts.

**Parameters:**

- **texts** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\]</code>) – The texts to embed, in order.

**Returns:**

- <code>[list](#list)\[[list](#list)\[[float](#float)\]\]</code> – One vector per input text, in the same order.

###### `agrag.embedding.base.Embedder.embed_one`

```python
embed_one(text:str) -> list[float]
```

Embed a single text.

**Parameters:**

- **text** (<code>[str](#str)</code>) – The text to embed.

**Returns:**

- <code>[list](#list)\[[float](#float)\]</code> – The text's embedding vector.

###### `agrag.embedding.base.Embedder.model`

```python
model: str
```

##### `agrag.embedding.base.EmbeddingCache`

Bases: <code>[ABC](#abc.ABC)</code>

A content-addressed cache for embedding vectors.

`normalize` is part of the cache key alongside `text` and `model`
because it changes the vector an embedder produces for the same text and
model: without it, embedders sharing one cache but configured with
opposite `EmbeddingSettings.normalize` values would read back the wrong
output mode. Any future embedder setting that changes output values must
join this key the same way.

**Functions:**

- [**get**](#agrag.embedding.base.EmbeddingCache.get) – Return the cached vector for `(text, model, normalize)`.
- [**set**](#agrag.embedding.base.EmbeddingCache.set) – Store `vector` under `(text, model, normalize)`.

###### `agrag.embedding.base.EmbeddingCache.get`

```python
get(*, text:str, model:str, normalize:bool) -> list[float] | None
```

Return the cached vector for `(text, model, normalize)`.

**Returns:**

- <code>[list](#list)\[[float](#float)\] | None</code> – The cached vector, or `None` on a miss.

###### `agrag.embedding.base.EmbeddingCache.set`

```python
set(*, text:str, model:str, normalize:bool, vector:list[float]) -> None
```

Store `vector` under `(text, model, normalize)`.

##### `agrag.embedding.base.NullEmbeddingCache`

Bases: <code>[EmbeddingCache](#agrag.embedding.base.EmbeddingCache)</code>

A cache that never stores anything. The default when none is injected.

**Functions:**

- [**get**](#agrag.embedding.base.NullEmbeddingCache.get) – Always miss.
- [**set**](#agrag.embedding.base.NullEmbeddingCache.set) – Do nothing.

###### `agrag.embedding.base.NullEmbeddingCache.get`

```python
get(*, text:str, model:str, normalize:bool) -> list[float] | None
```

Always miss.

###### `agrag.embedding.base.NullEmbeddingCache.set`

```python
set(*, text:str, model:str, normalize:bool, vector:list[float]) -> None
```

Do nothing.

#### `agrag.embedding.build_embedder`

```python
build_embedder(value:str | Embedder) -> Embedder
```

Build an embedder from a model name, or return an embedder unchanged.

**Parameters:**

- **value** (<code>[str](#str) | [Embedder](#agrag.embedding.base.Embedder)</code>) – A sentence-transformers model name, such as
  `"ibm-granite/granite-embedding-small-english-r2"` (the default
  model), or an already-constructed `Embedder` for full control
  over device, batching, or caching.

**Returns:**

- <code>[Embedder](#agrag.embedding.base.Embedder)</code> – A ready-to-use embedder.

#### `agrag.embedding.errors`

Errors that the embedding layer raises.

**Classes:**

- [**EmbeddingDimensionMismatchError**](#agrag.embedding.errors.EmbeddingDimensionMismatchError) – A stored collection or index expects a different embedding dimension.
- [**EmbeddingError**](#agrag.embedding.errors.EmbeddingError) – The base class for every embedding error.
- [**EmbeddingMissingExtraError**](#agrag.embedding.errors.EmbeddingMissingExtraError) – An embedder exists, but its package extra is not installed.

##### `agrag.embedding.errors.EmbeddingDimensionMismatchError`

```python
EmbeddingDimensionMismatchError(*, expected:int, actual:int) -> None
```

Bases: <code>[EmbeddingError](#agrag.embedding.errors.EmbeddingError)</code>

A stored collection or index expects a different embedding dimension.

**Attributes:**

- [**expected**](#agrag.embedding.errors.EmbeddingDimensionMismatchError.expected) – The dimension the collection or index was created with.
- [**actual**](#agrag.embedding.errors.EmbeddingDimensionMismatchError.actual) – The dimension the embedder actually produces.

###### `agrag.embedding.errors.EmbeddingDimensionMismatchError.actual`

```python
actual = actual
```

###### `agrag.embedding.errors.EmbeddingDimensionMismatchError.expected`

```python
expected = expected
```

##### `agrag.embedding.errors.EmbeddingError`

Bases: <code>[Exception](#Exception)</code>

The base class for every embedding error.

##### `agrag.embedding.errors.EmbeddingMissingExtraError`

```python
EmbeddingMissingExtraError(extra:str) -> None
```

Bases: <code>[EmbeddingError](#agrag.embedding.errors.EmbeddingError)</code>

An embedder exists, but its package extra is not installed.

**Attributes:**

- [**extra**](#agrag.embedding.errors.EmbeddingMissingExtraError.extra) – The name of the package extra to install.

###### `agrag.embedding.errors.EmbeddingMissingExtraError.extra`

```python
extra = extra
```

#### `agrag.embedding.fastembed_bm25`

BM25 sparse embedder backed by FastEmbed.

**Classes:**

- [**FastEmbedBM25Embedder**](#agrag.embedding.fastembed_bm25.FastEmbedBM25Embedder) – A sparse BM25 embedder built on FastEmbed.

**Attributes:**

- [**DEFAULT_BM25_MODEL**](#agrag.embedding.fastembed_bm25.DEFAULT_BM25_MODEL) –

##### `agrag.embedding.fastembed_bm25.DEFAULT_BM25_MODEL`

```python
DEFAULT_BM25_MODEL = 'Qdrant/bm25'
```

##### `agrag.embedding.fastembed_bm25.FastEmbedBM25Embedder`

```python
FastEmbedBM25Embedder(*, model:str | None = None) -> None
```

Bases: <code>[SparseEmbedder](#agrag.embedding.sparse_base.SparseEmbedder)</code>

A sparse BM25 embedder built on FastEmbed.

The model loads lazily on first `embed`, so constructing the embedder
does not download weights. Each blocking call into FastEmbed runs in a
worker thread, keeping the event loop free. FastEmbed ships with the
`qdrant` extra, so a clean install without that extra raises
`EmbeddingMissingExtraError` rather than `ImportError`.

**Functions:**

- [**embed**](#agrag.embedding.fastembed_bm25.FastEmbedBM25Embedder.embed) – Embed a batch of documents into BM25 sparse vectors.
- [**query_embed**](#agrag.embedding.fastembed_bm25.FastEmbedBM25Embedder.query_embed) – Embed a batch of search queries into BM25 sparse vectors.

**Attributes:**

- [**model**](#agrag.embedding.fastembed_bm25.FastEmbedBM25Embedder.model) (<code>[str](#str)</code>) – The configured model name, or the FastEmbed default when unset.

**Parameters:**

- **model** (<code>[str](#str) | None</code>) – The FastEmbed BM25 model name. Defaults to FastEmbed's
  built-in BM25 model.

###### `agrag.embedding.fastembed_bm25.FastEmbedBM25Embedder.embed`

```python
embed(texts:Sequence[str]) -> list[SparseVector]
```

Embed a batch of documents into BM25 sparse vectors.

Applies FastEmbed's document-side term-frequency and length
normalization weighting. Use `query_embed` for search queries.

**Parameters:**

- **texts** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\]</code>) – The document texts to embed, in order.

**Returns:**

- <code>[list](#list)\[[SparseVector](#agrag.embedding.sparse_base.SparseVector)\]</code> – One sparse vector per input text, in the same order.

###### `agrag.embedding.fastembed_bm25.FastEmbedBM25Embedder.model`

```python
model: str
```

The configured model name, or the FastEmbed default when unset.

###### `agrag.embedding.fastembed_bm25.FastEmbedBM25Embedder.query_embed`

```python
query_embed(texts:Sequence[str]) -> list[SparseVector]
```

Embed a batch of search queries into BM25 sparse vectors.

Uses FastEmbed's `query_embed`, which assigns each unique query
term a uniform weight of `1.0` rather than the document-side
term-frequency and length-normalization weighting `embed` applies;
IDF weighting is applied separately by the sparse index's
`Modifier.IDF` at query time.

**Parameters:**

- **texts** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\]</code>) – The query texts to embed, in order.

**Returns:**

- <code>[list](#list)\[[SparseVector](#agrag.embedding.sparse_base.SparseVector)\]</code> – One sparse vector per input text, in the same order.

#### `agrag.embedding.sentence_transformers`

Sentence-transformers embedder implementation.

**Classes:**

- [**SentenceTransformerEmbedder**](#agrag.embedding.sentence_transformers.SentenceTransformerEmbedder) – An embedder backed by sentence-transformers.

##### `agrag.embedding.sentence_transformers.SentenceTransformerEmbedder`

```python
SentenceTransformerEmbedder(*, settings:EmbeddingSettings | None = None, cache:EmbeddingCache | None = None, model:object | None = None) -> None
```

Bases: <code>[Embedder](#agrag.embedding.base.Embedder)</code>

An embedder backed by sentence-transformers.

The model loads lazily on first `embed`, so constructing the embedder
does not touch the GPU or download weights. Every blocking call into the
model runs in a worker thread (`asyncio.to_thread`), so the event loop
stays free for other work while a large batch encodes.

**Functions:**

- [**dimensions**](#agrag.embedding.sentence_transformers.SentenceTransformerEmbedder.dimensions) – Return the dimension the loaded model produces.
- [**embed**](#agrag.embedding.sentence_transformers.SentenceTransformerEmbedder.embed) – Embed a batch of texts, using the cache where possible.
- [**embed_one**](#agrag.embedding.sentence_transformers.SentenceTransformerEmbedder.embed_one) – Embed a single text.

**Attributes:**

- [**distance**](#agrag.embedding.sentence_transformers.SentenceTransformerEmbedder.distance) (<code>[Distance](#agrag.common.data_models.vector_record.Distance)</code>) – Return the distance metric for vector indexes created for this embedder.
- [**model**](#agrag.embedding.sentence_transformers.SentenceTransformerEmbedder.model) (<code>[str](#str)</code>) – The configured model name.

**Parameters:**

- **settings** (<code>[EmbeddingSettings](#agrag.embedding.settings.EmbeddingSettings) | None</code>) – Embedder configuration. Defaults to `EmbeddingSettings()`.
- **cache** (<code>[EmbeddingCache](#agrag.embedding.base.EmbeddingCache) | None</code>) – An optional content-addressed cache. Defaults to a no-op cache.
- **model** (<code>[object](#object) | None</code>) – A pre-built sentence-transformers model, for tests. When set,
  `__init__` imports nothing and `embed` calls this object
  directly instead of building one.

###### `agrag.embedding.sentence_transformers.SentenceTransformerEmbedder.dimensions`

```python
dimensions() -> int
```

Return the dimension the loaded model produces.

Calling this loads the model the first time, the same
lock-protected, worker-thread path `embed` uses, so it is safe to
call concurrently with `embed` without stalling the event loop or
loading a second copy of the model.

**Raises:**

- <code>[EmbeddingMissingExtraError](#agrag.embedding.errors.EmbeddingMissingExtraError)</code> – sentence-transformers is not installed.

###### `agrag.embedding.sentence_transformers.SentenceTransformerEmbedder.distance`

```python
distance: Distance
```

Return the distance metric for vector indexes created for this embedder.

Defaults to cosine, which matches normalized sentence-transformer models.
Concrete embedders may override when their vectors use a different
metric.

###### `agrag.embedding.sentence_transformers.SentenceTransformerEmbedder.embed`

```python
embed(texts:Sequence[str]) -> list[list[float]]
```

Embed a batch of texts, using the cache where possible.

**Parameters:**

- **texts** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\]</code>) – The texts to embed, in order.

**Returns:**

- <code>[list](#list)\[[list](#list)\[[float](#float)\]\]</code> – One vector per input text, in the same order.

###### `agrag.embedding.sentence_transformers.SentenceTransformerEmbedder.embed_one`

```python
embed_one(text:str) -> list[float]
```

Embed a single text.

**Parameters:**

- **text** (<code>[str](#str)</code>) – The text to embed.

**Returns:**

- <code>[list](#list)\[[float](#float)\]</code> – The text's embedding vector.

###### `agrag.embedding.sentence_transformers.SentenceTransformerEmbedder.model`

```python
model: str
```

The configured model name.

#### `agrag.embedding.settings`

Settings for the sentence-transformers embedder.

**Classes:**

- [**EmbeddingSettings**](#agrag.embedding.settings.EmbeddingSettings) – Sentence-transformers embedder configuration.

##### `agrag.embedding.settings.EmbeddingSettings`

Bases: <code>[BaseSettings](#pydantic_settings.BaseSettings)</code>

Sentence-transformers embedder configuration.

All fields are overridable via environment variables with the
`EMBEDDING_` prefix.

**Attributes:**

- [**model**](#agrag.embedding.settings.EmbeddingSettings.model) (<code>[str](#str)</code>) – The sentence-transformers model name or path. Env: `EMBEDDING_MODEL`.
- [**device**](#agrag.embedding.settings.EmbeddingSettings.device) (<code>[str](#str) | None</code>) – The device to load the model on, such as `"cpu"` or `"cuda"`.
  `None` uses sentence-transformers' own default detection. Env:
  `EMBEDDING_DEVICE`.
- [**normalize**](#agrag.embedding.settings.EmbeddingSettings.normalize) (<code>[bool](#bool)</code>) – Whether to L2-normalize output vectors. Env: `EMBEDDING_NORMALIZE`.
- [**batch_size**](#agrag.embedding.settings.EmbeddingSettings.batch_size) (<code>[int](#int)</code>) – The number of texts encoded per `model.encode` call. Env:
  `EMBEDDING_BATCH_SIZE`.
- [**cache_folder**](#agrag.embedding.settings.EmbeddingSettings.cache_folder) (<code>[str](#str) | None</code>) – Where sentence-transformers caches downloaded models.
  `None` uses the library default. Env: `EMBEDDING_CACHE_FOLDER`.

###### `agrag.embedding.settings.EmbeddingSettings.batch_size`

```python
batch_size: int = 32
```

###### `agrag.embedding.settings.EmbeddingSettings.cache_folder`

```python
cache_folder: str | None = None
```

###### `agrag.embedding.settings.EmbeddingSettings.device`

```python
device: str | None = None
```

###### `agrag.embedding.settings.EmbeddingSettings.model`

```python
model: str = 'ibm-granite/granite-embedding-small-english-r2'
```

###### `agrag.embedding.settings.EmbeddingSettings.model_config`

```python
model_config = SettingsConfigDict(env_prefix='EMBEDDING_', env_file='.env', extra='ignore')
```

###### `agrag.embedding.settings.EmbeddingSettings.normalize`

```python
normalize: bool = True
```

#### `agrag.embedding.sparse_base`

Sparse lexical vectors and the sparse embedder protocol.

**Classes:**

- [**SparseEmbedder**](#agrag.embedding.sparse_base.SparseEmbedder) – A component that turns text into sparse lexical vectors, for hybrid search.
- [**SparseVector**](#agrag.embedding.sparse_base.SparseVector) – A sparse vector: nonzero indices and their values.

##### `agrag.embedding.sparse_base.SparseEmbedder`

Bases: <code>[ABC](#abc.ABC)</code>

A component that turns text into sparse lexical vectors, for hybrid search.

**Functions:**

- [**embed**](#agrag.embedding.sparse_base.SparseEmbedder.embed) – Embed a batch of documents into sparse vectors.
- [**query_embed**](#agrag.embedding.sparse_base.SparseEmbedder.query_embed) – Embed a batch of search queries into sparse vectors.

**Attributes:**

- [**model**](#agrag.embedding.sparse_base.SparseEmbedder.model) (<code>[str](#str)</code>) –

###### `agrag.embedding.sparse_base.SparseEmbedder.embed`

```python
embed(texts:Sequence[str]) -> list[SparseVector]
```

Embed a batch of documents into sparse vectors.

**Parameters:**

- **texts** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\]</code>) – The document texts to embed, in order.

**Returns:**

- <code>[list](#list)\[[SparseVector](#agrag.embedding.sparse_base.SparseVector)\]</code> – One sparse vector per input text, in the same order.

###### `agrag.embedding.sparse_base.SparseEmbedder.model`

```python
model: str
```

###### `agrag.embedding.sparse_base.SparseEmbedder.query_embed`

```python
query_embed(texts:Sequence[str]) -> list[SparseVector]
```

Embed a batch of search queries into sparse vectors.

Query-side sparse embedding is not always the same computation as
document-side embedding: BM25, for example, applies term-frequency
and document-length normalization on the document side but only a
uniform per-term weight on the query side, since IDF weighting is
applied by the sparse index at query time instead. Implementations
with no such asymmetry may implement this identically to `embed`.

**Parameters:**

- **texts** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\]</code>) – The query texts to embed, in order.

**Returns:**

- <code>[list](#list)\[[SparseVector](#agrag.embedding.sparse_base.SparseVector)\]</code> – One sparse vector per input text, in the same order.

##### `agrag.embedding.sparse_base.SparseVector`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

A sparse vector: nonzero indices and their values.

**Attributes:**

- [**indices**](#agrag.embedding.sparse_base.SparseVector.indices) (<code>[list](#list)\[[int](#int)\]</code>) – The positions of nonzero entries.
- [**values**](#agrag.embedding.sparse_base.SparseVector.values) (<code>[list](#list)\[[float](#float)\]</code>) – The weight at each index, aligned with `indices`.

###### `agrag.embedding.sparse_base.SparseVector.indices`

```python
indices: list[int]
```

###### `agrag.embedding.sparse_base.SparseVector.values`

```python
values: list[float]
```

### `agrag.graphdb`

Graph storage backends and the build shortcut.

**Modules:**

- [**base**](#agrag.graphdb.base) – The GraphStore abstraction and its build shortcut helpers.
- [**errors**](#agrag.graphdb.errors) – Errors that the graph-store layer raises.
- [**neo4j**](#agrag.graphdb.neo4j) – Neo4j graph-store backend.
- [**serialize**](#agrag.graphdb.serialize) – Convert graph records into Neo4j-driver-friendly parameters.
- [**settings**](#agrag.graphdb.settings) – Settings for the Neo4j graph-store backend.

**Classes:**

- [**GraphStore**](#agrag.graphdb.GraphStore) – A graph database backend: schema, writes, and native vector search.
- [**GraphStoreError**](#agrag.graphdb.GraphStoreError) – The base class for every graph-store error.
- [**GraphStoreMissingExtraError**](#agrag.graphdb.GraphStoreMissingExtraError) – A graph store exists, but its package extra is not installed.
- [**Neo4jGraphStore**](#agrag.graphdb.Neo4jGraphStore) – A `GraphStore` backed by Neo4j, using native vector indexes.
- [**Neo4jSettings**](#agrag.graphdb.Neo4jSettings) – Neo4j connection configuration.

**Functions:**

- [**build_graph_store**](#agrag.graphdb.build_graph_store) – Build a graph store from a backend name, or return one unchanged.

**Attributes:**

- [**GraphStoreName**](#agrag.graphdb.GraphStoreName) –

#### `agrag.graphdb.GraphStore`

Bases: <code>[ABC](#abc.ABC)</code>

A graph database backend: schema, writes, and native vector search.

**Functions:**

- [**close**](#agrag.graphdb.GraphStore.close) – Release the backend connection.
- [**connect**](#agrag.graphdb.GraphStore.connect) – Open the backend connection and verify connectivity.
- [**ensure_vector_index**](#agrag.graphdb.GraphStore.ensure_vector_index) – Create a native vector index if it does not exist.
- [**execute_read**](#agrag.graphdb.GraphStore.execute_read) – Run a read transaction.
- [**execute_write**](#agrag.graphdb.GraphStore.execute_write) – Run a write transaction.
- [**register_labels**](#agrag.graphdb.GraphStore.register_labels) – Mark labels as known, without writing anything.
- [**register_relation_types**](#agrag.graphdb.GraphStore.register_relation_types) – Mark relationship types as known, without writing anything.
- [**session**](#agrag.graphdb.GraphStore.session) – Open a session as an async context manager.
- [**setup_constraints**](#agrag.graphdb.GraphStore.setup_constraints) – Create per-label and per-relation-type uniqueness constraints.
- [**setup_indexes**](#agrag.graphdb.GraphStore.setup_indexes) – Create per-label property indexes.
- [**transaction**](#agrag.graphdb.GraphStore.transaction) – Start an explicit transaction spanning multiple writes.
- [**upsert_nodes**](#agrag.graphdb.GraphStore.upsert_nodes) – Write or merge nodes, honoring each record's full label set.
- [**upsert_relations**](#agrag.graphdb.GraphStore.upsert_relations) – Write or merge relationships between existing nodes.
- [**vector_search**](#agrag.graphdb.GraphStore.vector_search) – Search nodes by dense vector.

##### `agrag.graphdb.GraphStore.close`

```python
close() -> None
```

Release the backend connection.

##### `agrag.graphdb.GraphStore.connect`

```python
connect() -> None
```

Open the backend connection and verify connectivity.

##### `agrag.graphdb.GraphStore.ensure_vector_index`

```python
ensure_vector_index(*, label:str, vector_property:str, dimensions:int, distance:Distance) -> None
```

Create a native vector index if it does not exist.

**Parameters:**

- **label** (<code>[str](#str)</code>) – The node label to index.
- **vector_property** (<code>[str](#str)</code>) – The embedding property name.
- **dimensions** (<code>[int](#int)</code>) – The embedding dimension.
- **distance** (<code>[Distance](#agrag.common.data_models.vector_record.Distance)</code>) – The distance metric.

##### `agrag.graphdb.GraphStore.execute_read`

```python
execute_read(query:str, parameters:Mapping[str, Any] | None = None, *, timeout:float | None = None) -> list[dict[str, Any]]
```

Run a read transaction.

**Parameters:**

- **query** (<code>[str](#str)</code>) – The Cypher query to run.
- **parameters** (<code>[Mapping](#collections.abc.Mapping)\[[str](#str), [Any](#typing.Any)\] | None</code>) – The query parameters.
- **timeout** (<code>[float](#float) | None</code>) – Server-side transaction timeout in seconds. The
  database terminates the transaction when it runs
  longer. None uses the server's default timeout.
  Backends that cannot enforce a timeout ignore it.

**Returns:**

- <code>[list](#list)\[[dict](#dict)\[[str](#str), [Any](#typing.Any)\]\]</code> – The result rows as dicts.

##### `agrag.graphdb.GraphStore.execute_write`

```python
execute_write(query:str, parameters:Mapping[str, Any] | None = None) -> list[dict[str, Any]]
```

Run a write transaction.

**Parameters:**

- **query** (<code>[str](#str)</code>) – The Cypher query to run.
- **parameters** (<code>[Mapping](#collections.abc.Mapping)\[[str](#str), [Any](#typing.Any)\] | None</code>) – The query parameters.

**Returns:**

- <code>[list](#list)\[[dict](#dict)\[[str](#str), [Any](#typing.Any)\]\]</code> – The result rows as dicts.

##### `agrag.graphdb.GraphStore.register_labels`

```python
register_labels(labels:Sequence[str]) -> None
```

Mark labels as known, without writing anything.

setup_constraints()/setup_indexes() only cover labels this instance
has already written (or that already exist live in the database) —
both empty on a brand-new database. register_labels lets a caller
holding a GraphSchema (Graph.open()) provision a fresh database
fully before its first write.

**Parameters:**

- **labels** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\]</code>) – The labels to register. Each must be a safe Cypher
  identifier.

**Raises:**

- <code>[ValueError](#ValueError)</code> – Any label is not a safe identifier.

##### `agrag.graphdb.GraphStore.register_relation_types`

```python
register_relation_types(types:Sequence[str]) -> None
```

Mark relationship types as known, without writing anything.

The relationship-type counterpart to register_labels — see its
docstring for why this exists.

**Parameters:**

- **types** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\]</code>) – The relationship types to register. Each must be a safe
  Cypher identifier.

**Raises:**

- <code>[ValueError](#ValueError)</code> – Any type is not a safe identifier.

##### `agrag.graphdb.GraphStore.session`

```python
session() -> AbstractAsyncContextManager[Any]
```

Open a session as an async context manager.

**Returns:**

- <code>[AbstractAsyncContextManager](#contextlib.AbstractAsyncContextManager)\[[Any](#typing.Any)\]</code> – A context manager yielding a backend session.

##### `agrag.graphdb.GraphStore.setup_constraints`

```python
setup_constraints() -> None
```

Create per-label and per-relation-type uniqueness constraints.

Constraints cover every node label and relationship type written
through this instance or already present in the database, so a fresh
instance can set up an existing database without first rewriting
every record.

##### `agrag.graphdb.GraphStore.setup_indexes`

```python
setup_indexes() -> None
```

Create per-label property indexes.

Covers every node label written through this instance or already
present in the database, so a fresh instance can set up an existing
database without first rewriting every record.

##### `agrag.graphdb.GraphStore.transaction`

```python
transaction() -> AsyncIterator[GraphStoreTransaction]
```

Start an explicit transaction spanning multiple writes.

Every call through the yielded handle should join one backend
transaction, committing as a whole on clean exit from the
`async with` block and rolling back as a whole if the block raises.
The default here simply yields `self` and gives no atomicity beyond
what each individual call already provides; a backend that can offer
real atomicity, such as `Neo4jGraphStore`, overrides this with a
driver transaction.

Use this when a caller must guarantee several writes either all apply
or none do, such as `apply_merge`'s tombstone, relationship
transfer, and dedup steps.

**Returns:**

- <code>[AsyncIterator](#collections.abc.AsyncIterator)\[[GraphStoreTransaction](#agrag.graphdb.base.GraphStoreTransaction)\]</code> – An async context manager yielding the transactional handle.

##### `agrag.graphdb.GraphStore.upsert_nodes`

```python
upsert_nodes(label:str, nodes:Sequence[NodeRecord], *, batch_size:int = 256) -> UpsertResult
```

Write or merge nodes, honoring each record's full label set.

**Parameters:**

- **label** (<code>[str](#str)</code>) – The label this batch is tracked under for constraint and
  index bookkeeping.
- **nodes** (<code>[Sequence](#collections.abc.Sequence)\[[NodeRecord](#agrag.common.data_models.graph_record.NodeRecord)\]</code>) – The node records to upsert. Each node's `NodeRecord.labels`
  names the full label set actually written to it, which may
  include labels beyond `label`.
- **batch_size** (<code>[int](#int)</code>) – Records per backend write call, applied within each
  distinct label set when `nodes` mixes more than one. Must
  be positive.

**Returns:**

- <code>[UpsertResult](#agrag.common.data_models.graph_record.UpsertResult)</code> – The number written and one failure entry for each isolated record.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `batch_size` is not positive.

##### `agrag.graphdb.GraphStore.upsert_relations`

```python
upsert_relations(relations:Sequence[RelationRecord], *, batch_size:int = 256) -> UpsertResult
```

Write or merge relationships between existing nodes.

**Parameters:**

- **relations** (<code>[Sequence](#collections.abc.Sequence)\[[RelationRecord](#agrag.common.data_models.graph_record.RelationRecord)\]</code>) – The relation records to upsert.
- **batch_size** (<code>[int](#int)</code>) – Records per backend write call. Must be positive.

**Returns:**

- <code>[UpsertResult](#agrag.common.data_models.graph_record.UpsertResult)</code> – The number written and one failure entry for each isolated record.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `batch_size` is not positive.

##### `agrag.graphdb.GraphStore.vector_search`

```python
vector_search(*, label:str, vector_property:str, query_vector:Sequence[float], limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search nodes by dense vector.

**Parameters:**

- **label** (<code>[str](#str)</code>) – The node label to search.
- **vector_property** (<code>[str](#str)</code>) – The embedding property name.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **limit** (<code>[int](#int)</code>) – Maximum number of hits.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – An optional flat-dict filter on node properties.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The matched hits, highest score first.

#### `agrag.graphdb.GraphStoreError`

Bases: <code>[Exception](#Exception)</code>

The base class for every graph-store error.

#### `agrag.graphdb.GraphStoreMissingExtraError`

```python
GraphStoreMissingExtraError(extra:str) -> None
```

Bases: <code>[GraphStoreError](#agrag.graphdb.errors.GraphStoreError)</code>

A graph store exists, but its package extra is not installed.

**Attributes:**

- [**extra**](#agrag.graphdb.GraphStoreMissingExtraError.extra) – The name of the package extra to install.

##### `agrag.graphdb.GraphStoreMissingExtraError.extra`

```python
extra = extra
```

#### `agrag.graphdb.GraphStoreName`

```python
GraphStoreName = Literal['neo4j']
```

#### `agrag.graphdb.Neo4jGraphStore`

```python
Neo4jGraphStore(*, settings:Neo4jSettings | None = None, driver:AsyncDriver | None = None) -> None
```

Bases: <code>[GraphStore](#agrag.graphdb.base.GraphStore)</code>

A `GraphStore` backed by Neo4j, using native vector indexes.

The driver connects lazily on first use, so constructing the store does not
open a network connection. `execute_read`/`execute_write` wrap the
driver's managed transactions with no added retry loop.

**Functions:**

- [**close**](#agrag.graphdb.Neo4jGraphStore.close) – Close the driver, releasing its connection pool.
- [**connect**](#agrag.graphdb.Neo4jGraphStore.connect) – Open the driver and verify connectivity.
- [**ensure_relation_constraint**](#agrag.graphdb.Neo4jGraphStore.ensure_relation_constraint) – Create a relationship type's `id` uniqueness constraint once.
- [**ensure_vector_index**](#agrag.graphdb.Neo4jGraphStore.ensure_vector_index) – Create a native vector index if it does not exist.
- [**execute_read**](#agrag.graphdb.Neo4jGraphStore.execute_read) – Run a read transaction and return its rows.
- [**execute_write**](#agrag.graphdb.Neo4jGraphStore.execute_write) – Run a write transaction and return its rows.
- [**register_labels**](#agrag.graphdb.Neo4jGraphStore.register_labels) – Add labels to this instance's known-label set.
- [**register_relation_types**](#agrag.graphdb.Neo4jGraphStore.register_relation_types) – Add types to this instance's known-relation-type set.
- [**session**](#agrag.graphdb.Neo4jGraphStore.session) – Open a session to the configured database.
- [**setup_constraints**](#agrag.graphdb.Neo4jGraphStore.setup_constraints) – Create a uniqueness constraint on `id` for every known label.
- [**setup_indexes**](#agrag.graphdb.Neo4jGraphStore.setup_indexes) – Create a range index on `id` for every known label.
- [**transaction**](#agrag.graphdb.Neo4jGraphStore.transaction) – Open one Neo4j explicit transaction spanning multiple writes.
- [**upsert_nodes**](#agrag.graphdb.Neo4jGraphStore.upsert_nodes) – Write or merge nodes, honoring each record's full label set.
- [**upsert_relations**](#agrag.graphdb.Neo4jGraphStore.upsert_relations) – Write or merge relationships between existing nodes.
- [**vector_search**](#agrag.graphdb.Neo4jGraphStore.vector_search) – Search nodes by dense vector using the native vector index.

**Parameters:**

- **settings** (<code>[Neo4jSettings](#agrag.graphdb.settings.Neo4jSettings) | None</code>) – Neo4j connection settings. Defaults to `Neo4jSettings()`.
- **driver** (<code>[AsyncDriver](#neo4j.AsyncDriver) | None</code>) – A pre-built `AsyncDriver`, for tests. When set,
  `__init__` imports nothing and the store calls this object
  directly instead of building one.

##### `agrag.graphdb.Neo4jGraphStore.close`

```python
close() -> None
```

Close the driver, releasing its connection pool.

##### `agrag.graphdb.Neo4jGraphStore.connect`

```python
connect() -> None
```

Open the driver and verify connectivity.

##### `agrag.graphdb.Neo4jGraphStore.ensure_relation_constraint`

```python
ensure_relation_constraint(rel_type:str) -> None
```

Create a relationship type's `id` uniqueness constraint once.

Public entry point onto `_ensure_relation_constraint` for
`_Neo4jTransaction.upsert_relations`, which must give the same
constraint-before-first-write guarantee inside an explicit
transaction that the non-transactional `upsert_relations` gives.

**Parameters:**

- **rel_type** (<code>[str](#str)</code>) – The relationship type to ensure a constraint for. Must
  already be validated.

##### `agrag.graphdb.Neo4jGraphStore.ensure_vector_index`

```python
ensure_vector_index(*, label:str, vector_property:str, dimensions:int, distance:Distance) -> None
```

Create a native vector index if it does not exist.

##### `agrag.graphdb.Neo4jGraphStore.execute_read`

```python
execute_read(query:str, parameters:Mapping[str, Any] | None = None, *, timeout:float | None = None) -> list[dict[str, Any]]
```

Run a read transaction and return its rows.

**Parameters:**

- **query** (<code>[str](#str)</code>) – The Cypher query to run.
- **parameters** (<code>[Mapping](#collections.abc.Mapping)\[[str](#str), [Any](#typing.Any)\] | None</code>) – The query parameters.
- **timeout** (<code>[float](#float) | None</code>) – Server-side transaction timeout in seconds,
  applied through the driver's `unit_of_work` so the
  database terminates the transaction when it runs
  longer. None uses the server's default timeout.

**Returns:**

- <code>[list](#list)\[[dict](#dict)\[[str](#str), [Any](#typing.Any)\]\]</code> – The result rows as dicts.

##### `agrag.graphdb.Neo4jGraphStore.execute_write`

```python
execute_write(query:str, parameters:Mapping[str, Any] | None = None) -> list[dict[str, Any]]
```

Run a write transaction and return its rows.

**Raises:**

- <code>[GraphStoreConstraintViolationError](#agrag.graphdb.errors.GraphStoreConstraintViolationError)</code> – The write violated a uniqueness
  constraint, translated from the driver's own exception so
  callers do not need a hard dependency on it.

##### `agrag.graphdb.Neo4jGraphStore.register_labels`

```python
register_labels(labels:Sequence[str]) -> None
```

Add labels to this instance's known-label set.

**Parameters:**

- **labels** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\]</code>) – The labels to register. Each must be a safe Cypher
  identifier.

**Raises:**

- <code>[ValueError](#ValueError)</code> – Any label is not a safe identifier.

##### `agrag.graphdb.Neo4jGraphStore.register_relation_types`

```python
register_relation_types(types:Sequence[str]) -> None
```

Add types to this instance's known-relation-type set.

**Parameters:**

- **types** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\]</code>) – The relationship types to register. Each must be a safe
  Cypher identifier.

**Raises:**

- <code>[ValueError](#ValueError)</code> – Any type is not a safe identifier.

##### `agrag.graphdb.Neo4jGraphStore.session`

```python
session() -> AbstractAsyncContextManager[Any]
```

Open a session to the configured database.

##### `agrag.graphdb.Neo4jGraphStore.setup_constraints`

```python
setup_constraints() -> None
```

Create a uniqueness constraint on `id` for every known label.

"Known" means written by this instance or already present in the
database, so a fresh store can set up constraints for an existing
database without first rewriting every record. Also creates the
global uniqueness constraint on `NODE_IDENTITY_LABEL` that
`upsert_node_query`'s `MERGE` relies on to resolve a node by id
regardless of its other, mutable labels, and a per-type uniqueness
constraint on `id` for every known relationship type, which backs
the stale-relationship cleanup `upsert_relation_query` performs on
endpoint changes.

##### `agrag.graphdb.Neo4jGraphStore.setup_indexes`

```python
setup_indexes() -> None
```

Create a range index on `id` for every known label.

"Known" means written by this instance or already present in the
database, so a fresh store can set up indexes for an existing
database without first rewriting every record.

##### `agrag.graphdb.Neo4jGraphStore.transaction`

```python
transaction() -> AsyncIterator[GraphStoreTransaction]
```

Open one Neo4j explicit transaction spanning multiple writes.

Commits when the `async with` block exits cleanly; rolls back and
re-raises when it raises. The identity constraint is ensured before
opening the transaction, the same way `upsert_nodes` ensures it
before writing, since `_Neo4jTransaction.upsert_nodes` skips that
check to avoid a nested write racing the transaction it belongs to.

**Raises:**

- <code>[GraphStoreConstraintViolationError](#agrag.graphdb.errors.GraphStoreConstraintViolationError)</code> – A write inside the block, or the
  commit itself, violated a uniqueness constraint -- Neo4j
  validates some constraints only at commit time for an
  explicit transaction, so this can surface here even when
  every individual write appeared to succeed.

##### `agrag.graphdb.Neo4jGraphStore.upsert_nodes`

```python
upsert_nodes(label:str, nodes:Sequence[NodeRecord], *, batch_size:int = 256) -> UpsertResult
```

Write or merge nodes, honoring each record's full label set.

`label` names the batch for constraint/index bookkeeping, matching
every other tracked label; the labels actually written to a node come
from `NodeRecord.labels`, which may name more than one label (for
example a node that is both `Chunk` and `Entity`). Records with
different label sets are grouped and written with separate `MERGE`
queries, since Cypher requires labels to be literal in the query text
rather than a runtime parameter, so `batch_size` chunks apply within
each group rather than across the whole call.

**Returns:**

- <code>[UpsertResult](#agrag.common.data_models.graph_record.UpsertResult)</code> – The number written and one failure entry for each isolated record.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `batch_size` is not positive.

##### `agrag.graphdb.Neo4jGraphStore.upsert_relations`

```python
upsert_relations(relations:Sequence[RelationRecord], *, batch_size:int = 256) -> UpsertResult
```

Write or merge relationships between existing nodes.

Relationship identity is each record's `id`, not its endpoints: see
`upsert_relation_query` for how endpoint changes and same-id
parallel relationships are handled.

**Returns:**

- <code>[UpsertResult](#agrag.common.data_models.graph_record.UpsertResult)</code> – The number written and one failure entry for each isolated record.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `batch_size` is not positive.

##### `agrag.graphdb.Neo4jGraphStore.vector_search`

```python
vector_search(*, label:str, vector_property:str, query_vector:Sequence[float], limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search nodes by dense vector using the native vector index.

A label with no provisioned vector index has nothing to search,
so an absent index returns an empty result list rather than a
driver error.

When `filters` is set, Neo4j's vector procedure applies the filter
only after selecting its top `k` candidates, so a plain `k=limit`
call can return fewer matches than actually exist. This escalates
`k` and retries until `limit` filtered hits come back or the
escalation reaches `_VECTOR_SEARCH_MAX_K`.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `limit` is not positive. A non-positive value is
  not a meaningful request and would send that same
  non-positive `k` to Neo4j's native vector procedure, which
  requires a positive top-k.

#### `agrag.graphdb.Neo4jSettings`

Bases: <code>[BaseSettings](#pydantic_settings.BaseSettings)</code>

Neo4j connection configuration.

**Attributes:**

- [**uri**](#agrag.graphdb.Neo4jSettings.uri) (<code>[str](#str)</code>) – The Bolt connection URI, including scheme (`neo4j+s://` for
  Aura). Env: `NEO4J_URI`.
- [**username**](#agrag.graphdb.Neo4jSettings.username) (<code>[str](#str)</code>) – The database username. Env: `NEO4J_USERNAME`.
- [**password**](#agrag.graphdb.Neo4jSettings.password) (<code>[SecretStr](#pydantic.SecretStr)</code>) – The database password. Env: `NEO4J_PASSWORD`.
- [**database**](#agrag.graphdb.Neo4jSettings.database) (<code>[str](#str)</code>) – The target database name. Env: `NEO4J_DATABASE`.
- [**max_connection_lifetime**](#agrag.graphdb.Neo4jSettings.max_connection_lifetime) (<code>[int](#int)</code>) – The maximum seconds a pooled connection
  lives, kept well below Aura's roughly five-minute idle timeout.
  Env: `NEO4J_MAX_CONNECTION_LIFETIME`.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `uri` is plaintext (`bolt://` or `neo4j://`) and
  points at a non-local host. Neo4j always authenticates with a
  password, so a plaintext scheme always sends it in the clear; use
  `neo4j+s://` (or `bolt+s://`) for a remote instance.

##### `agrag.graphdb.Neo4jSettings.database`

```python
database: str = 'neo4j'
```

##### `agrag.graphdb.Neo4jSettings.max_connection_lifetime`

```python
max_connection_lifetime: int = 240
```

##### `agrag.graphdb.Neo4jSettings.model_config`

```python
model_config = SettingsConfigDict(env_prefix='NEO4J_', env_file='.env', extra='ignore')
```

##### `agrag.graphdb.Neo4jSettings.password`

```python
password: SecretStr = SecretStr('neo4j')
```

##### `agrag.graphdb.Neo4jSettings.uri`

```python
uri: str = 'bolt://localhost:7687'
```

##### `agrag.graphdb.Neo4jSettings.username`

```python
username: str = 'neo4j'
```

#### `agrag.graphdb.base`

The GraphStore abstraction and its build shortcut helpers.

**Classes:**

- [**GraphStore**](#agrag.graphdb.base.GraphStore) – A graph database backend: schema, writes, and native vector search.
- [**GraphStoreTransaction**](#agrag.graphdb.base.GraphStoreTransaction) – The read/write/upsert surface available inside a `transaction()` block.

##### `agrag.graphdb.base.GraphStore`

Bases: <code>[ABC](#abc.ABC)</code>

A graph database backend: schema, writes, and native vector search.

**Functions:**

- [**close**](#agrag.graphdb.base.GraphStore.close) – Release the backend connection.
- [**connect**](#agrag.graphdb.base.GraphStore.connect) – Open the backend connection and verify connectivity.
- [**ensure_vector_index**](#agrag.graphdb.base.GraphStore.ensure_vector_index) – Create a native vector index if it does not exist.
- [**execute_read**](#agrag.graphdb.base.GraphStore.execute_read) – Run a read transaction.
- [**execute_write**](#agrag.graphdb.base.GraphStore.execute_write) – Run a write transaction.
- [**register_labels**](#agrag.graphdb.base.GraphStore.register_labels) – Mark labels as known, without writing anything.
- [**register_relation_types**](#agrag.graphdb.base.GraphStore.register_relation_types) – Mark relationship types as known, without writing anything.
- [**session**](#agrag.graphdb.base.GraphStore.session) – Open a session as an async context manager.
- [**setup_constraints**](#agrag.graphdb.base.GraphStore.setup_constraints) – Create per-label and per-relation-type uniqueness constraints.
- [**setup_indexes**](#agrag.graphdb.base.GraphStore.setup_indexes) – Create per-label property indexes.
- [**transaction**](#agrag.graphdb.base.GraphStore.transaction) – Start an explicit transaction spanning multiple writes.
- [**upsert_nodes**](#agrag.graphdb.base.GraphStore.upsert_nodes) – Write or merge nodes, honoring each record's full label set.
- [**upsert_relations**](#agrag.graphdb.base.GraphStore.upsert_relations) – Write or merge relationships between existing nodes.
- [**vector_search**](#agrag.graphdb.base.GraphStore.vector_search) – Search nodes by dense vector.

###### `agrag.graphdb.base.GraphStore.close`

```python
close() -> None
```

Release the backend connection.

###### `agrag.graphdb.base.GraphStore.connect`

```python
connect() -> None
```

Open the backend connection and verify connectivity.

###### `agrag.graphdb.base.GraphStore.ensure_vector_index`

```python
ensure_vector_index(*, label:str, vector_property:str, dimensions:int, distance:Distance) -> None
```

Create a native vector index if it does not exist.

**Parameters:**

- **label** (<code>[str](#str)</code>) – The node label to index.
- **vector_property** (<code>[str](#str)</code>) – The embedding property name.
- **dimensions** (<code>[int](#int)</code>) – The embedding dimension.
- **distance** (<code>[Distance](#agrag.common.data_models.vector_record.Distance)</code>) – The distance metric.

###### `agrag.graphdb.base.GraphStore.execute_read`

```python
execute_read(query:str, parameters:Mapping[str, Any] | None = None, *, timeout:float | None = None) -> list[dict[str, Any]]
```

Run a read transaction.

**Parameters:**

- **query** (<code>[str](#str)</code>) – The Cypher query to run.
- **parameters** (<code>[Mapping](#collections.abc.Mapping)\[[str](#str), [Any](#typing.Any)\] | None</code>) – The query parameters.
- **timeout** (<code>[float](#float) | None</code>) – Server-side transaction timeout in seconds. The
  database terminates the transaction when it runs
  longer. None uses the server's default timeout.
  Backends that cannot enforce a timeout ignore it.

**Returns:**

- <code>[list](#list)\[[dict](#dict)\[[str](#str), [Any](#typing.Any)\]\]</code> – The result rows as dicts.

###### `agrag.graphdb.base.GraphStore.execute_write`

```python
execute_write(query:str, parameters:Mapping[str, Any] | None = None) -> list[dict[str, Any]]
```

Run a write transaction.

**Parameters:**

- **query** (<code>[str](#str)</code>) – The Cypher query to run.
- **parameters** (<code>[Mapping](#collections.abc.Mapping)\[[str](#str), [Any](#typing.Any)\] | None</code>) – The query parameters.

**Returns:**

- <code>[list](#list)\[[dict](#dict)\[[str](#str), [Any](#typing.Any)\]\]</code> – The result rows as dicts.

###### `agrag.graphdb.base.GraphStore.register_labels`

```python
register_labels(labels:Sequence[str]) -> None
```

Mark labels as known, without writing anything.

setup_constraints()/setup_indexes() only cover labels this instance
has already written (or that already exist live in the database) —
both empty on a brand-new database. register_labels lets a caller
holding a GraphSchema (Graph.open()) provision a fresh database
fully before its first write.

**Parameters:**

- **labels** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\]</code>) – The labels to register. Each must be a safe Cypher
  identifier.

**Raises:**

- <code>[ValueError](#ValueError)</code> – Any label is not a safe identifier.

###### `agrag.graphdb.base.GraphStore.register_relation_types`

```python
register_relation_types(types:Sequence[str]) -> None
```

Mark relationship types as known, without writing anything.

The relationship-type counterpart to register_labels — see its
docstring for why this exists.

**Parameters:**

- **types** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\]</code>) – The relationship types to register. Each must be a safe
  Cypher identifier.

**Raises:**

- <code>[ValueError](#ValueError)</code> – Any type is not a safe identifier.

###### `agrag.graphdb.base.GraphStore.session`

```python
session() -> AbstractAsyncContextManager[Any]
```

Open a session as an async context manager.

**Returns:**

- <code>[AbstractAsyncContextManager](#contextlib.AbstractAsyncContextManager)\[[Any](#typing.Any)\]</code> – A context manager yielding a backend session.

###### `agrag.graphdb.base.GraphStore.setup_constraints`

```python
setup_constraints() -> None
```

Create per-label and per-relation-type uniqueness constraints.

Constraints cover every node label and relationship type written
through this instance or already present in the database, so a fresh
instance can set up an existing database without first rewriting
every record.

###### `agrag.graphdb.base.GraphStore.setup_indexes`

```python
setup_indexes() -> None
```

Create per-label property indexes.

Covers every node label written through this instance or already
present in the database, so a fresh instance can set up an existing
database without first rewriting every record.

###### `agrag.graphdb.base.GraphStore.transaction`

```python
transaction() -> AsyncIterator[GraphStoreTransaction]
```

Start an explicit transaction spanning multiple writes.

Every call through the yielded handle should join one backend
transaction, committing as a whole on clean exit from the
`async with` block and rolling back as a whole if the block raises.
The default here simply yields `self` and gives no atomicity beyond
what each individual call already provides; a backend that can offer
real atomicity, such as `Neo4jGraphStore`, overrides this with a
driver transaction.

Use this when a caller must guarantee several writes either all apply
or none do, such as `apply_merge`'s tombstone, relationship
transfer, and dedup steps.

**Returns:**

- <code>[AsyncIterator](#collections.abc.AsyncIterator)\[[GraphStoreTransaction](#agrag.graphdb.base.GraphStoreTransaction)\]</code> – An async context manager yielding the transactional handle.

###### `agrag.graphdb.base.GraphStore.upsert_nodes`

```python
upsert_nodes(label:str, nodes:Sequence[NodeRecord], *, batch_size:int = 256) -> UpsertResult
```

Write or merge nodes, honoring each record's full label set.

**Parameters:**

- **label** (<code>[str](#str)</code>) – The label this batch is tracked under for constraint and
  index bookkeeping.
- **nodes** (<code>[Sequence](#collections.abc.Sequence)\[[NodeRecord](#agrag.common.data_models.graph_record.NodeRecord)\]</code>) – The node records to upsert. Each node's `NodeRecord.labels`
  names the full label set actually written to it, which may
  include labels beyond `label`.
- **batch_size** (<code>[int](#int)</code>) – Records per backend write call, applied within each
  distinct label set when `nodes` mixes more than one. Must
  be positive.

**Returns:**

- <code>[UpsertResult](#agrag.common.data_models.graph_record.UpsertResult)</code> – The number written and one failure entry for each isolated record.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `batch_size` is not positive.

###### `agrag.graphdb.base.GraphStore.upsert_relations`

```python
upsert_relations(relations:Sequence[RelationRecord], *, batch_size:int = 256) -> UpsertResult
```

Write or merge relationships between existing nodes.

**Parameters:**

- **relations** (<code>[Sequence](#collections.abc.Sequence)\[[RelationRecord](#agrag.common.data_models.graph_record.RelationRecord)\]</code>) – The relation records to upsert.
- **batch_size** (<code>[int](#int)</code>) – Records per backend write call. Must be positive.

**Returns:**

- <code>[UpsertResult](#agrag.common.data_models.graph_record.UpsertResult)</code> – The number written and one failure entry for each isolated record.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `batch_size` is not positive.

###### `agrag.graphdb.base.GraphStore.vector_search`

```python
vector_search(*, label:str, vector_property:str, query_vector:Sequence[float], limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search nodes by dense vector.

**Parameters:**

- **label** (<code>[str](#str)</code>) – The node label to search.
- **vector_property** (<code>[str](#str)</code>) – The embedding property name.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **limit** (<code>[int](#int)</code>) – Maximum number of hits.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – An optional flat-dict filter on node properties.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The matched hits, highest score first.

##### `agrag.graphdb.base.GraphStoreTransaction`

Bases: <code>[Protocol](#typing.Protocol)</code>

The read/write/upsert surface available inside a `transaction()` block.

A structural type, not a base class: `GraphStore` itself satisfies it
(the default `transaction()` yields `self`), and a backend's own
transaction handle, such as Neo4j's, satisfies it without inheriting from
anything here.

**Functions:**

- [**execute_read**](#agrag.graphdb.base.GraphStoreTransaction.execute_read) – Run a read inside the surrounding transaction.
- [**execute_write**](#agrag.graphdb.base.GraphStoreTransaction.execute_write) – Run a write inside the surrounding transaction.
- [**upsert_nodes**](#agrag.graphdb.base.GraphStoreTransaction.upsert_nodes) – Write or merge nodes inside the surrounding transaction.
- [**upsert_relations**](#agrag.graphdb.base.GraphStoreTransaction.upsert_relations) – Write or merge relationships inside the surrounding transaction.

###### `agrag.graphdb.base.GraphStoreTransaction.execute_read`

```python
execute_read(query:str, parameters:Mapping[str, Any] | None = None) -> list[dict[str, Any]]
```

Run a read inside the surrounding transaction.

###### `agrag.graphdb.base.GraphStoreTransaction.execute_write`

```python
execute_write(query:str, parameters:Mapping[str, Any] | None = None) -> list[dict[str, Any]]
```

Run a write inside the surrounding transaction.

###### `agrag.graphdb.base.GraphStoreTransaction.upsert_nodes`

```python
upsert_nodes(label:str, nodes:Sequence[NodeRecord], *, batch_size:int = 256) -> UpsertResult | None
```

Write or merge nodes inside the surrounding transaction.

###### `agrag.graphdb.base.GraphStoreTransaction.upsert_relations`

```python
upsert_relations(relations:Sequence[RelationRecord], *, batch_size:int = 256) -> UpsertResult | None
```

Write or merge relationships inside the surrounding transaction.

#### `agrag.graphdb.build_graph_store`

```python
build_graph_store(value:GraphStoreName | GraphStore) -> GraphStore
```

Build a graph store from a backend name, or return one unchanged.

**Parameters:**

- **value** (<code>[GraphStoreName](#agrag.graphdb.GraphStoreName) | [GraphStore](#agrag.graphdb.base.GraphStore)</code>) – `"neo4j"`, or an already-constructed `GraphStore`.

**Returns:**

- <code>[GraphStore](#agrag.graphdb.base.GraphStore)</code> – A ready-to-use graph store.

#### `agrag.graphdb.errors`

Errors that the graph-store layer raises.

**Classes:**

- [**GraphStoreAliasConflictError**](#agrag.graphdb.errors.GraphStoreAliasConflictError) – A merge-key alias a merge tried to claim already names another entity.
- [**GraphStoreConstraintViolationError**](#agrag.graphdb.errors.GraphStoreConstraintViolationError) – A write violated a uniqueness constraint the backend enforces.
- [**GraphStoreDataIntegrityError**](#agrag.graphdb.errors.GraphStoreDataIntegrityError) – A read found the graph store in a state its own invariants forbid.
- [**GraphStoreError**](#agrag.graphdb.errors.GraphStoreError) – The base class for every graph-store error.
- [**GraphStoreMissingExtraError**](#agrag.graphdb.errors.GraphStoreMissingExtraError) – A graph store exists, but its package extra is not installed.

##### `agrag.graphdb.errors.GraphStoreAliasConflictError`

```python
GraphStoreAliasConflictError(conflicts:dict[str, str]) -> None
```

Bases: <code>[GraphStoreConstraintViolationError](#agrag.graphdb.errors.GraphStoreConstraintViolationError)</code>

A merge-key alias a merge tried to claim already names another entity.

Unlike the base class, this is not surfaced by the backend's own
uniqueness constraint -- claiming an already-owned alias is a silent
no-op at the database level (see `upsert_merge_alias_query`) -- so
`apply_merge` detects it itself from the claim's own return rows and
raises this instead. For example, one writer creates a canonical entity
named "Bob" while a concurrent writer separately resolves "Bob" as an
accepted alias of a different canonical entity named "Robert": neither
writer's own node merge_key collides, so recovery must come from here,
not from a constraint violation.

**Attributes:**

- [**conflicts**](#agrag.graphdb.errors.GraphStoreAliasConflictError.conflicts) – Every accepted merge_key this claim found already owned,
  mapped to the entity id that owns it.

###### `agrag.graphdb.errors.GraphStoreAliasConflictError.conflicts`

```python
conflicts = conflicts
```

##### `agrag.graphdb.errors.GraphStoreConstraintViolationError`

Bases: <code>[GraphStoreError](#agrag.graphdb.errors.GraphStoreError)</code>

A write violated a uniqueness constraint the backend enforces.

Raised instead of letting the backend's own driver exception propagate,
so callers can recognize this specific case -- for example, two
concurrent writers both missing an exact-match lookup and racing to
create the same `merge_key` -- and recover by re-resolving to
whichever write landed first, rather than treating it as a fatal error.

##### `agrag.graphdb.errors.GraphStoreDataIntegrityError`

Bases: <code>[GraphStoreError](#agrag.graphdb.errors.GraphStoreError)</code>

A read found the graph store in a state its own invariants forbid.

Raised when persisted data cannot be trusted at face value -- for
example a `merged_into` tombstone chain that cycles, points at a
missing node, or runs past its expected bound without reaching a live
node. Returning the last-seen data in these cases would let a caller
silently act on a tombstone instead of the entity it was absorbed into.

##### `agrag.graphdb.errors.GraphStoreError`

Bases: <code>[Exception](#Exception)</code>

The base class for every graph-store error.

##### `agrag.graphdb.errors.GraphStoreMissingExtraError`

```python
GraphStoreMissingExtraError(extra:str) -> None
```

Bases: <code>[GraphStoreError](#agrag.graphdb.errors.GraphStoreError)</code>

A graph store exists, but its package extra is not installed.

**Attributes:**

- [**extra**](#agrag.graphdb.errors.GraphStoreMissingExtraError.extra) – The name of the package extra to install.

###### `agrag.graphdb.errors.GraphStoreMissingExtraError.extra`

```python
extra = extra
```

#### `agrag.graphdb.neo4j`

Neo4j graph-store backend.

**Classes:**

- [**Neo4jGraphStore**](#agrag.graphdb.neo4j.Neo4jGraphStore) – A `GraphStore` backed by Neo4j, using native vector indexes.

##### `agrag.graphdb.neo4j.Neo4jGraphStore`

```python
Neo4jGraphStore(*, settings:Neo4jSettings | None = None, driver:AsyncDriver | None = None) -> None
```

Bases: <code>[GraphStore](#agrag.graphdb.base.GraphStore)</code>

A `GraphStore` backed by Neo4j, using native vector indexes.

The driver connects lazily on first use, so constructing the store does not
open a network connection. `execute_read`/`execute_write` wrap the
driver's managed transactions with no added retry loop.

**Functions:**

- [**close**](#agrag.graphdb.neo4j.Neo4jGraphStore.close) – Close the driver, releasing its connection pool.
- [**connect**](#agrag.graphdb.neo4j.Neo4jGraphStore.connect) – Open the driver and verify connectivity.
- [**ensure_relation_constraint**](#agrag.graphdb.neo4j.Neo4jGraphStore.ensure_relation_constraint) – Create a relationship type's `id` uniqueness constraint once.
- [**ensure_vector_index**](#agrag.graphdb.neo4j.Neo4jGraphStore.ensure_vector_index) – Create a native vector index if it does not exist.
- [**execute_read**](#agrag.graphdb.neo4j.Neo4jGraphStore.execute_read) – Run a read transaction and return its rows.
- [**execute_write**](#agrag.graphdb.neo4j.Neo4jGraphStore.execute_write) – Run a write transaction and return its rows.
- [**register_labels**](#agrag.graphdb.neo4j.Neo4jGraphStore.register_labels) – Add labels to this instance's known-label set.
- [**register_relation_types**](#agrag.graphdb.neo4j.Neo4jGraphStore.register_relation_types) – Add types to this instance's known-relation-type set.
- [**session**](#agrag.graphdb.neo4j.Neo4jGraphStore.session) – Open a session to the configured database.
- [**setup_constraints**](#agrag.graphdb.neo4j.Neo4jGraphStore.setup_constraints) – Create a uniqueness constraint on `id` for every known label.
- [**setup_indexes**](#agrag.graphdb.neo4j.Neo4jGraphStore.setup_indexes) – Create a range index on `id` for every known label.
- [**transaction**](#agrag.graphdb.neo4j.Neo4jGraphStore.transaction) – Open one Neo4j explicit transaction spanning multiple writes.
- [**upsert_nodes**](#agrag.graphdb.neo4j.Neo4jGraphStore.upsert_nodes) – Write or merge nodes, honoring each record's full label set.
- [**upsert_relations**](#agrag.graphdb.neo4j.Neo4jGraphStore.upsert_relations) – Write or merge relationships between existing nodes.
- [**vector_search**](#agrag.graphdb.neo4j.Neo4jGraphStore.vector_search) – Search nodes by dense vector using the native vector index.

**Parameters:**

- **settings** (<code>[Neo4jSettings](#agrag.graphdb.settings.Neo4jSettings) | None</code>) – Neo4j connection settings. Defaults to `Neo4jSettings()`.
- **driver** (<code>[AsyncDriver](#neo4j.AsyncDriver) | None</code>) – A pre-built `AsyncDriver`, for tests. When set,
  `__init__` imports nothing and the store calls this object
  directly instead of building one.

###### `agrag.graphdb.neo4j.Neo4jGraphStore.close`

```python
close() -> None
```

Close the driver, releasing its connection pool.

###### `agrag.graphdb.neo4j.Neo4jGraphStore.connect`

```python
connect() -> None
```

Open the driver and verify connectivity.

###### `agrag.graphdb.neo4j.Neo4jGraphStore.ensure_relation_constraint`

```python
ensure_relation_constraint(rel_type:str) -> None
```

Create a relationship type's `id` uniqueness constraint once.

Public entry point onto `_ensure_relation_constraint` for
`_Neo4jTransaction.upsert_relations`, which must give the same
constraint-before-first-write guarantee inside an explicit
transaction that the non-transactional `upsert_relations` gives.

**Parameters:**

- **rel_type** (<code>[str](#str)</code>) – The relationship type to ensure a constraint for. Must
  already be validated.

###### `agrag.graphdb.neo4j.Neo4jGraphStore.ensure_vector_index`

```python
ensure_vector_index(*, label:str, vector_property:str, dimensions:int, distance:Distance) -> None
```

Create a native vector index if it does not exist.

###### `agrag.graphdb.neo4j.Neo4jGraphStore.execute_read`

```python
execute_read(query:str, parameters:Mapping[str, Any] | None = None, *, timeout:float | None = None) -> list[dict[str, Any]]
```

Run a read transaction and return its rows.

**Parameters:**

- **query** (<code>[str](#str)</code>) – The Cypher query to run.
- **parameters** (<code>[Mapping](#collections.abc.Mapping)\[[str](#str), [Any](#typing.Any)\] | None</code>) – The query parameters.
- **timeout** (<code>[float](#float) | None</code>) – Server-side transaction timeout in seconds,
  applied through the driver's `unit_of_work` so the
  database terminates the transaction when it runs
  longer. None uses the server's default timeout.

**Returns:**

- <code>[list](#list)\[[dict](#dict)\[[str](#str), [Any](#typing.Any)\]\]</code> – The result rows as dicts.

###### `agrag.graphdb.neo4j.Neo4jGraphStore.execute_write`

```python
execute_write(query:str, parameters:Mapping[str, Any] | None = None) -> list[dict[str, Any]]
```

Run a write transaction and return its rows.

**Raises:**

- <code>[GraphStoreConstraintViolationError](#agrag.graphdb.errors.GraphStoreConstraintViolationError)</code> – The write violated a uniqueness
  constraint, translated from the driver's own exception so
  callers do not need a hard dependency on it.

###### `agrag.graphdb.neo4j.Neo4jGraphStore.register_labels`

```python
register_labels(labels:Sequence[str]) -> None
```

Add labels to this instance's known-label set.

**Parameters:**

- **labels** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\]</code>) – The labels to register. Each must be a safe Cypher
  identifier.

**Raises:**

- <code>[ValueError](#ValueError)</code> – Any label is not a safe identifier.

###### `agrag.graphdb.neo4j.Neo4jGraphStore.register_relation_types`

```python
register_relation_types(types:Sequence[str]) -> None
```

Add types to this instance's known-relation-type set.

**Parameters:**

- **types** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\]</code>) – The relationship types to register. Each must be a safe
  Cypher identifier.

**Raises:**

- <code>[ValueError](#ValueError)</code> – Any type is not a safe identifier.

###### `agrag.graphdb.neo4j.Neo4jGraphStore.session`

```python
session() -> AbstractAsyncContextManager[Any]
```

Open a session to the configured database.

###### `agrag.graphdb.neo4j.Neo4jGraphStore.setup_constraints`

```python
setup_constraints() -> None
```

Create a uniqueness constraint on `id` for every known label.

"Known" means written by this instance or already present in the
database, so a fresh store can set up constraints for an existing
database without first rewriting every record. Also creates the
global uniqueness constraint on `NODE_IDENTITY_LABEL` that
`upsert_node_query`'s `MERGE` relies on to resolve a node by id
regardless of its other, mutable labels, and a per-type uniqueness
constraint on `id` for every known relationship type, which backs
the stale-relationship cleanup `upsert_relation_query` performs on
endpoint changes.

###### `agrag.graphdb.neo4j.Neo4jGraphStore.setup_indexes`

```python
setup_indexes() -> None
```

Create a range index on `id` for every known label.

"Known" means written by this instance or already present in the
database, so a fresh store can set up indexes for an existing
database without first rewriting every record.

###### `agrag.graphdb.neo4j.Neo4jGraphStore.transaction`

```python
transaction() -> AsyncIterator[GraphStoreTransaction]
```

Open one Neo4j explicit transaction spanning multiple writes.

Commits when the `async with` block exits cleanly; rolls back and
re-raises when it raises. The identity constraint is ensured before
opening the transaction, the same way `upsert_nodes` ensures it
before writing, since `_Neo4jTransaction.upsert_nodes` skips that
check to avoid a nested write racing the transaction it belongs to.

**Raises:**

- <code>[GraphStoreConstraintViolationError](#agrag.graphdb.errors.GraphStoreConstraintViolationError)</code> – A write inside the block, or the
  commit itself, violated a uniqueness constraint -- Neo4j
  validates some constraints only at commit time for an
  explicit transaction, so this can surface here even when
  every individual write appeared to succeed.

###### `agrag.graphdb.neo4j.Neo4jGraphStore.upsert_nodes`

```python
upsert_nodes(label:str, nodes:Sequence[NodeRecord], *, batch_size:int = 256) -> UpsertResult
```

Write or merge nodes, honoring each record's full label set.

`label` names the batch for constraint/index bookkeeping, matching
every other tracked label; the labels actually written to a node come
from `NodeRecord.labels`, which may name more than one label (for
example a node that is both `Chunk` and `Entity`). Records with
different label sets are grouped and written with separate `MERGE`
queries, since Cypher requires labels to be literal in the query text
rather than a runtime parameter, so `batch_size` chunks apply within
each group rather than across the whole call.

**Returns:**

- <code>[UpsertResult](#agrag.common.data_models.graph_record.UpsertResult)</code> – The number written and one failure entry for each isolated record.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `batch_size` is not positive.

###### `agrag.graphdb.neo4j.Neo4jGraphStore.upsert_relations`

```python
upsert_relations(relations:Sequence[RelationRecord], *, batch_size:int = 256) -> UpsertResult
```

Write or merge relationships between existing nodes.

Relationship identity is each record's `id`, not its endpoints: see
`upsert_relation_query` for how endpoint changes and same-id
parallel relationships are handled.

**Returns:**

- <code>[UpsertResult](#agrag.common.data_models.graph_record.UpsertResult)</code> – The number written and one failure entry for each isolated record.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `batch_size` is not positive.

###### `agrag.graphdb.neo4j.Neo4jGraphStore.vector_search`

```python
vector_search(*, label:str, vector_property:str, query_vector:Sequence[float], limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search nodes by dense vector using the native vector index.

A label with no provisioned vector index has nothing to search,
so an absent index returns an empty result list rather than a
driver error.

When `filters` is set, Neo4j's vector procedure applies the filter
only after selecting its top `k` candidates, so a plain `k=limit`
call can return fewer matches than actually exist. This escalates
`k` and retries until `limit` filtered hits come back or the
escalation reaches `_VECTOR_SEARCH_MAX_K`.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `limit` is not positive. A non-positive value is
  not a meaningful request and would send that same
  non-positive `k` to Neo4j's native vector procedure, which
  requires a positive top-k.

#### `agrag.graphdb.serialize`

Convert graph records into Neo4j-driver-friendly parameters.

**Functions:**

- [**node_params**](#agrag.graphdb.serialize.node_params) – Build the `$records` entry for a node upsert.
- [**relation_params**](#agrag.graphdb.serialize.relation_params) – Build the `$records` entry for a relationship upsert.

##### `agrag.graphdb.serialize.node_params`

```python
node_params(record:NodeRecord) -> dict[str, Any]
```

Build the `$records` entry for a node upsert.

**Parameters:**

- **record** (<code>[NodeRecord](#agrag.common.data_models.graph_record.NodeRecord)</code>) – The node record to serialize.

**Returns:**

- <code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\]</code> – A dict with `id` (string) and `properties` (converted).

##### `agrag.graphdb.serialize.relation_params`

```python
relation_params(record:RelationRecord) -> dict[str, Any]
```

Build the `$records` entry for a relationship upsert.

**Parameters:**

- **record** (<code>[RelationRecord](#agrag.common.data_models.graph_record.RelationRecord)</code>) – The relation record to serialize.

**Returns:**

- <code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\]</code> – A dict with `id`, `start_id`, `end_id`, and `properties`.

#### `agrag.graphdb.settings`

Settings for the Neo4j graph-store backend.

**Classes:**

- [**Neo4jSettings**](#agrag.graphdb.settings.Neo4jSettings) – Neo4j connection configuration.

##### `agrag.graphdb.settings.Neo4jSettings`

Bases: <code>[BaseSettings](#pydantic_settings.BaseSettings)</code>

Neo4j connection configuration.

**Attributes:**

- [**uri**](#agrag.graphdb.settings.Neo4jSettings.uri) (<code>[str](#str)</code>) – The Bolt connection URI, including scheme (`neo4j+s://` for
  Aura). Env: `NEO4J_URI`.
- [**username**](#agrag.graphdb.settings.Neo4jSettings.username) (<code>[str](#str)</code>) – The database username. Env: `NEO4J_USERNAME`.
- [**password**](#agrag.graphdb.settings.Neo4jSettings.password) (<code>[SecretStr](#pydantic.SecretStr)</code>) – The database password. Env: `NEO4J_PASSWORD`.
- [**database**](#agrag.graphdb.settings.Neo4jSettings.database) (<code>[str](#str)</code>) – The target database name. Env: `NEO4J_DATABASE`.
- [**max_connection_lifetime**](#agrag.graphdb.settings.Neo4jSettings.max_connection_lifetime) (<code>[int](#int)</code>) – The maximum seconds a pooled connection
  lives, kept well below Aura's roughly five-minute idle timeout.
  Env: `NEO4J_MAX_CONNECTION_LIFETIME`.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `uri` is plaintext (`bolt://` or `neo4j://`) and
  points at a non-local host. Neo4j always authenticates with a
  password, so a plaintext scheme always sends it in the clear; use
  `neo4j+s://` (or `bolt+s://`) for a remote instance.

###### `agrag.graphdb.settings.Neo4jSettings.database`

```python
database: str = 'neo4j'
```

###### `agrag.graphdb.settings.Neo4jSettings.max_connection_lifetime`

```python
max_connection_lifetime: int = 240
```

###### `agrag.graphdb.settings.Neo4jSettings.model_config`

```python
model_config = SettingsConfigDict(env_prefix='NEO4J_', env_file='.env', extra='ignore')
```

###### `agrag.graphdb.settings.Neo4jSettings.password`

```python
password: SecretStr = SecretStr('neo4j')
```

###### `agrag.graphdb.settings.Neo4jSettings.uri`

```python
uri: str = 'bolt://localhost:7687'
```

###### `agrag.graphdb.settings.Neo4jSettings.username`

```python
username: str = 'neo4j'
```

### `agrag.ingestion`

The ingestion package.

**Modules:**

- [**community**](#agrag.ingestion.community) – Community detection: hierarchical Leiden over the entity graph.
- [**extract**](#agrag.ingestion.extract) – The Extractor interface: reads one Chunk and produces an ExtractionResult.
- [**graph**](#agrag.ingestion.graph) – The public Graph API for ingestion.
- [**merge**](#agrag.ingestion.merge) – Merge mechanics: computing how a resolved group of mentions and entities combine.
- [**reports**](#agrag.ingestion.reports) – Reports returned by Graph pipeline operations.
- [**resolve**](#agrag.ingestion.resolve) – Entity resolution: deciding which ExtractedEntity mentions are the same thing.
- [**stats**](#agrag.ingestion.stats) – Per-stage observability types for the ingestion pipeline.

**Classes:**

- [**Graph**](#agrag.ingestion.Graph) – A knowledge graph that a caller can open and add content to.

#### `agrag.ingestion.Graph`

```python
Graph(*, schema:GraphSchema, graph_store:GraphStore, embedder:Embedder, extractor:Extractor, tracer:Tracer | None = None, vector_store:VectorStore | None = None, retrieval_settings:RetrievalSettings | None = None) -> None
```

A knowledge graph that a caller can open and add content to.

When an optional VectorStore is configured, every embedding this
graph writes to graph_store is also upserted there, so SearchEngine's
VectorStore path finds the same vectors the GraphStore-native path
does. Collections follow RetrievalSettings' names and are provisioned
by `open()` when missing.

**Functions:**

- [**add**](#agrag.ingestion.Graph.add) – Add content to the graph.
- [**consolidate**](#agrag.ingestion.Graph.consolidate) – Run full tiered resolution against everything persisted.
- [**delete_document**](#agrag.ingestion.Graph.delete_document) – Soft-delete a document by closing its current PART_OF edges.
- [**detect_communities**](#agrag.ingestion.Graph.detect_communities) – Detect entity communities via hierarchical Leiden.
- [**open**](#agrag.ingestion.Graph.open) – Open a graph, connecting and fully provisioning graph_store.
- [**update**](#agrag.ingestion.Graph.update) – Replace one document version, closing its former PART_OF edges.

**Parameters:**

- **schema** (<code>[GraphSchema](#agrag.common.data_models.graph_schema.GraphSchema)</code>) – The entity/relation types this graph validates every
  extraction against.
- **graph_store** (<code>[GraphStore](#agrag.graphdb.base.GraphStore)</code>) – Where entities, relations, chunks, and MENTIONED_IN
  edges are written.
- **embedder** (<code>[Embedder](#agrag.embedding.base.Embedder)</code>) – Populates entity embeddings for native vector search.
- **extractor** (<code>[Extractor](#agrag.ingestion.extract.Extractor)</code>) – Runs against each chunk.
- **tracer** (<code>[Tracer](#opentelemetry.trace.Tracer) | None</code>) – A tracer to record spans for every step. Pass None for none.
- **vector_store** (<code>[VectorStore](#agrag.vectordb.base.VectorStore) | None</code>) – Optional second write target for embeddings. When
  set, every embedding the pipeline writes to graph_store is
  also upserted here, so SearchEngine's VectorStore path finds
  the same vectors the GraphStore-native path does. Also gets
  tombstoned entities deleted after merges and old community
  vectors removed on each detect_communities(apply=True)
  cycle.
- **retrieval_settings** (<code>[RetrievalSettings](#agrag.retrieval.settings.RetrievalSettings) | None</code>) – Collection names for the VectorStore writes.
  None uses RetrievalSettings defaults. Ignored when
  vector_store is None.

##### `agrag.ingestion.Graph.add`

```python
add(source:SourcesType | None = None, *, text:str | None = None, documents:Sequence[Document] | None = None, loader:Loader | None = None, error_policy:ErrorPolicy = ErrorPolicy.RAISE, on_progress:Callable[[AddResult], None] | None = None, return_chunks:bool = False) -> AddResult
```

Add content to the graph.

Give exactly one of `source`, `text`, and `documents`.

**Parameters:**

- **source** (<code>[SourcesType](#agrag.ingestion.graph.SourcesType) | None</code>) – A file path, a directory, a glob, or a list of these.
- **text** (<code>[str](#str) | None</code>) – Raw text to add as one document.
- **documents** (<code>[Sequence](#collections.abc.Sequence)\[[Document](#agrag.common.data_models.document.Document)\] | None</code>) – Already-built documents to add directly.
- **loader** (<code>[Loader](#agrag.loaders.corpus.base.Loader) | None</code>) – A loader to use instead of the registry default. Requires a
  single-file `source`; a directory, glob, or list of sources raises an
  error.
- **error_policy** (<code>[ErrorPolicy](#agrag.loaders.corpus.types.ErrorPolicy)</code>) – The action to take on a per-source error.
- **on_progress** (<code>[Callable](#collections.abc.Callable)\[\[[AddResult](#agrag.ingestion.reports.AddResult)\], None\] | None</code>) – A callback the call runs after each batch and once more
  at the end with the fully-populated result.
- **return_chunks** (<code>[bool](#bool)</code>) – Whether to include the produced chunks in the
  returned AddResult. False by default to avoid holding full text
  for a large corpus when not needed.

**Returns:**

- <code>[AddResult](#agrag.ingestion.reports.AddResult)</code> – A summary of what was added per pipeline stage.

**Raises:**

- <code>[ValueError](#ValueError)</code> – The call got zero, or more than one, of `source`, `text`,
  and `documents`. Also raised when `loader` is set without
  `source`, or with a source that can match more than one file.
- <code>[UnsupportedFormatError](#UnsupportedFormatError)</code> – No loader is registered for a source's format.
- <code>[MissingExtraError](#MissingExtraError)</code> – A loader is registered for a source's format, but its
  package extra is not installed. This error follows `error_policy`
  instead of always stopping the call.
- <code>[ValueError](#ValueError)</code> – The input contains multiple documents with the same
  `document_key`.

##### `agrag.ingestion.Graph.consolidate`

```python
consolidate(*, apply:bool = False) -> ConsolidationReport
```

Run full tiered resolution against everything persisted.

Dry-run by default: produces a report of what would merge before any
node is touched. Pass apply=True to write the merges.

For each EntityType label in self.\_schema, fetches every persisted
entity with that label and runs the same comparator sequence add() uses
in-batch (ExactMatch, FuzzyMatch, LLMVerify) pairwise across all of
them — O(n^2) within each label's population.
Confirmed matches become MergePlans via compute_merge.

**Parameters:**

- **apply** (<code>[bool](#bool)</code>) – Write the computed merges. False produces a report only.

**Returns:**

- <code>[ConsolidationReport](#agrag.ingestion.reports.ConsolidationReport)</code> – A report of every group consolidate() found, applied or not.

##### `agrag.ingestion.Graph.delete_document`

```python
delete_document(document_key:str) -> UpdateResult
```

Soft-delete a document by closing its current PART_OF edges.

##### `agrag.ingestion.Graph.detect_communities`

```python
detect_communities(*, apply:bool = False, max_cluster_size:int = 10, resolution:float = 1.0, seed:int | None = 3735928559) -> CommunityDetectionReport
```

Detect entity communities via hierarchical Leiden.

Dry-run by default: produces a report of the communities that would be
written before any node is touched. Pass apply=True to write them.

Fetches every live domain relation across the whole graph (not scoped
by entity label the way consolidate() is -- community structure spans
entity types), builds a weighted edge list, and runs hierarchical
Leiden off the event loop. Every prior run's Community nodes and
MEMBER_OF edges are deleted before the new ones are written when
apply=True: this is a full recompute, not an incremental update,
so there is no notion of merging this run's output with a
previous one's.

**Parameters:**

- **apply** (<code>[bool](#bool)</code>) – Write the computed communities. False produces a report only.
- **max_cluster_size** (<code>[int](#int)</code>) – Forwarded to compute_communities.
- **resolution** (<code>[float](#float)</code>) – Forwarded to compute_communities.
- **seed** (<code>[int](#int) | None</code>) – Forwarded to compute_communities.

**Returns:**

- <code>[CommunityDetectionReport](#agrag.ingestion.reports.CommunityDetectionReport)</code> – A report of every community this call found, applied or not.

**Raises:**

- <code>[CommunityDetectionMissingExtraError](#agrag.ingestion.community.CommunityDetectionMissingExtraError)</code> –
  graspologic-native is not installed.

##### `agrag.ingestion.Graph.open`

```python
open(*, schema:GraphSchema, graph_store:GraphStore, embedder:Embedder, extractor:Extractor, tracer:Tracer | None = None, vector_store:VectorStore | None = None, retrieval_settings:RetrievalSettings | None = None) -> Graph
```

Open a graph, connecting and fully provisioning graph_store.

Provisioning order: connect, then register every label/relation type
this graph will ever write (schema's own labels/types plus the fixed
system names CHUNK_LABEL/SYSTEM_RELATION_TYPES), then
setup_constraints(), then setup_indexes(), then vector indexes for
every schema entity label — so a brand-new database is fully ready,
including the merge_key index the global exact-match tier needs and
the embedding vector indexes native search needs, before this call
returns. When vector_store is set, the entity, chunk, and community
collections are provisioned there too (created when missing) so the
dual writes never hit an absent collection.

**Parameters:**

- **schema** (<code>[GraphSchema](#agrag.common.data_models.graph_schema.GraphSchema)</code>) – The entity/relation types this graph validates every
  extraction against.
- **graph_store** (<code>[GraphStore](#agrag.graphdb.base.GraphStore)</code>) – Where entities, relations, chunks, and MENTIONED_IN
  edges are written.
- **embedder** (<code>[Embedder](#agrag.embedding.base.Embedder)</code>) – Populates entity embeddings for native vector search.
- **extractor** (<code>[Extractor](#agrag.ingestion.extract.Extractor)</code>) – Runs against each chunk.
- **tracer** (<code>[Tracer](#opentelemetry.trace.Tracer) | None</code>) – A tracer to record spans for every step. Pass None for none.
- **vector_store** (<code>[VectorStore](#agrag.vectordb.base.VectorStore) | None</code>) – Optional second write target for embeddings; see
  __init__.
- **retrieval_settings** (<code>[RetrievalSettings](#agrag.retrieval.settings.RetrievalSettings) | None</code>) – Collection names for the VectorStore writes.
  None uses RetrievalSettings defaults.

**Returns:**

- <code>[Graph](#agrag.ingestion.graph.Graph)</code> – A graph connected to graph_store and ready to accept add() calls.

**Raises:**

- <code>[Exception](#Exception)</code> – Whatever connect(), registration, constraint/index
  setup, or vector-index provisioning raises. graph_store is
  closed first, so a failed open() never leaks a connection.

##### `agrag.ingestion.Graph.update`

```python
update(document_key:str, *, text:str | None = None, source:SourcesType | None = None, loader:Loader | None = None, error_policy:ErrorPolicy = ErrorPolicy.RAISE) -> UpdateResult
```

Replace one document version, closing its former PART_OF edges.

An unchanged content hash is a no-op. The update path uses the same
`add` pipeline as fresh ingestion after it closes the old edges. A
source must resolve to exactly one document.

**Raises:**

- <code>[ValueError](#ValueError)</code> – Both or neither of `text` and `source` are given, a loader
  override targets multiple sources, or a source resolves to any number
  of documents other than one.

#### `agrag.ingestion.community`

Community detection: hierarchical Leiden over the entity graph.

**Classes:**

- [**CommunityDetectionMissingExtraError**](#agrag.ingestion.community.CommunityDetectionMissingExtraError) – Raised when graspologic-native is not installed.

**Functions:**

- [**compute_communities**](#agrag.ingestion.community.compute_communities) – Run hierarchical Leiden and return level-0 communities.
- [**delete_all_communities**](#agrag.ingestion.community.delete_all_communities) – Delete every Community node and its edges, in batches.
- [**embed_communities**](#agrag.ingestion.community.embed_communities) – Compute each community's embedding from its report text, in place.
- [**fetch_relation_edges**](#agrag.ingestion.community.fetch_relation_edges) – Return every live domain relation as a weighted edge tuple.
- [**generate_community_reports**](#agrag.ingestion.community.generate_community_reports) – Generate a report for each community, in place.
- [**required_member_ids**](#agrag.ingestion.community.required_member_ids) – Return the member ids generate_community_reports will actually read.

**Attributes:**

- [**WeightedEdge**](#agrag.ingestion.community.WeightedEdge) – One domain relation as (source_id, target_id, weight, relation_type).
- [**logger**](#agrag.ingestion.community.logger) –

##### `agrag.ingestion.community.CommunityDetectionMissingExtraError`

```python
CommunityDetectionMissingExtraError(extra:str = 'community') -> None
```

Bases: <code>[Exception](#Exception)</code>

Raised when graspologic-native is not installed.

##### `agrag.ingestion.community.WeightedEdge`

```python
WeightedEdge = tuple[str, str, float, str]
```

One domain relation as (source_id, target_id, weight, relation_type).

##### `agrag.ingestion.community.compute_communities`

```python
compute_communities(edges:list[WeightedEdge], *, max_cluster_size:int = 10, resolution:float = 1.0, seed:int | None = 3735928559) -> list[Community]
```

Run hierarchical Leiden and return level-0 communities.

CPU-bound and synchronous; callers on the event loop should run this via
asyncio.to_thread (see Graph.\_chunk_documents for the same pattern with
chunking). Only level 0 is kept -- higher levels are computed for
max_cluster_size capping but never persisted.

After clustering, one extra pass over the same edge list computes a
structural-importance signal, entirely from data already in memory --
no new dependency (graspologic exposes no general centrality function;
see the follow-up research this refinement is based on), no new query:

- Each community's internal_weight (total weight of edges where both
  endpoints are its members) -- signal for which communities get a
  real LLM report instead of a heuristic one.
- Each member's local weight (weight of its own internal edges) --
  used to order member_ids highest-first, so the "most representative"
  members lead the list for both a large qualifying community's
  (token-budget-truncated) LLM prompt and a heuristic report's
  few-name summary.

**Parameters:**

- **edges** (<code>[list](#list)\[[WeightedEdge](#agrag.ingestion.community.WeightedEdge)\]</code>) – The weighted edge list from fetch_relation_edges, as
  (source_id, target_id, weight, relation_type) tuples.
- **max_cluster_size** (<code>[int](#int)</code>) – The size ceiling a cluster is split past, at every
  level.
- **resolution** (<code>[float](#float)</code>) – Leiden's resolution parameter.
- **seed** (<code>[int](#int) | None</code>) – Random seed for reproducibility. None uses the native
  default.

**Returns:**

- <code>[list](#list)\[[Community](#agrag.common.data_models.community.Community)\]</code> – One Community per level-0 cluster with two or more members, with
- <code>[list](#list)\[[Community](#agrag.common.data_models.community.Community)\]</code> – member_ids ordered by local weight descending and internal_weight
- <code>[list](#list)\[[Community](#agrag.common.data_models.community.Community)\]</code> – set. Reports (title/summary/rating/findings) are left empty; report
- <code>[list](#list)\[[Community](#agrag.common.data_models.community.Community)\]</code> – generation fills them.

**Raises:**

- <code>[CommunityDetectionMissingExtraError](#agrag.ingestion.community.CommunityDetectionMissingExtraError)</code> – graspologic-native is not
  installed.

##### `agrag.ingestion.community.delete_all_communities`

```python
delete_all_communities(graph_store:GraphStore | GraphStoreTransaction, *, batch_size:int = _DEFAULT_DELETE_BATCH_SIZE) -> None
```

Delete every Community node and its edges, in batches.

Repeats the bounded delete until a batch reports fewer than
batch_size rows deleted.

**Parameters:**

- **graph_store** (<code>[GraphStore](#agrag.graphdb.base.GraphStore) | [GraphStoreTransaction](#agrag.graphdb.base.GraphStoreTransaction)</code>) – Where the delete runs. Accepts either a
  `GraphStore` or a `GraphStoreTransaction` handle so a
  caller inside `store.transaction()` can delete and rewrite
  communities atomically.
- **batch_size** (<code>[int](#int)</code>) – Community nodes deleted per statement.

##### `agrag.ingestion.community.embed_communities`

```python
embed_communities(communities:list[Community], *, embedder:Embedder, batch_size:int = _DEFAULT_EMBED_BATCH_SIZE, max_concurrency:int = 4) -> list[StageFailure]
```

Compute each community's embedding from its report text, in place.

Called after generate_community_reports and before to_node_record(), so
the vector is already present on the very first (and only) write a
replace cycle makes.

Embedder.embed's contract makes no chunking guarantee (see
agrag/embedding/base.py), so at 1M+ entity scale, where a full recompute
can produce 100,000+ communities, this batches the embed() calls itself
rather than passing every community's text in one call.

A batch embed() failure does not block other batches: it is recorded as
one StageFailure per community in that batch, matching the
failure-tolerance shape generate_community_reports already uses. Those
communities keep embedding=None and still get written by
Community.to_node_record(), which omits the embedding property when it
is None, rather than being dropped from the graph.

**Parameters:**

- **communities** (<code>[list](#list)\[[Community](#agrag.common.data_models.community.Community)\]</code>) – The communities to embed, mutated in place.
- **embedder** (<code>[Embedder](#agrag.embedding.base.Embedder)</code>) – Computes one vector per community's embedding_text.
- **batch_size** (<code>[int](#int)</code>) – Communities embedded per embed() call.
- **max_concurrency** (<code>[int](#int)</code>) – Max concurrent embed calls.

**Returns:**

- <code>[list](#list)\[[StageFailure](#agrag.ingestion.stats.StageFailure)\]</code> – One StageFailure per community whose batch embed() call failed.

##### `agrag.ingestion.community.fetch_relation_edges`

```python
fetch_relation_edges(graph_store:GraphStore, *, page_size:int = 5000, use_cursor:bool = True) -> list[WeightedEdge]
```

Return every live domain relation as a weighted edge tuple.

Weight is len(source_chunk_ids) (attestation count). A relation with
no attested chunks contributes weight 0.0, so an unsupported edge
cannot inflate clustering or a community's report importance. Two
entities connected by more than one distinct relation type contribute
one edge tuple per type; graspologic_native sums parallel-edge
weights building its own adjacency.

Supports cursor (keyset) pagination for large graphs where `SKIP`
is expensive, and legacy `SKIP` pagination for callers that need
it.

**Parameters:**

- **graph_store** (<code>[GraphStore](#agrag.graphdb.base.GraphStore)</code>) – Where the relations are read from.
- **page_size** (<code>[int](#int)</code>) – Rows fetched per page.
- **use_cursor** (<code>[bool](#bool)</code>) – When True uses keyset pagination on `(a.id, b.id, type(r), r.id)`; when False uses `SKIP` pagination.

**Returns:**

- <code>[list](#list)\[[WeightedEdge](#agrag.ingestion.community.WeightedEdge)\]</code> – Edge tuples as (source_id_str, target_id_str, weight, rel_type).

##### `agrag.ingestion.community.generate_community_reports`

```python
generate_community_reports(communities:list[Community], entities_by_id:dict[UUID, Entity], *, edges:list[WeightedEdge] | None = None, min_importance_for_llm_report:float = _DEFAULT_MIN_IMPORTANCE_FOR_LLM_REPORT, batch_size:int = _DEFAULT_REPORT_BATCH_SIZE, max_members_per_prompt:int = _DEFAULT_MAX_MEMBERS_PER_PROMPT, max_relations_per_prompt:int = _DEFAULT_MAX_RELATIONS_PER_PROMPT, max_concurrency:int = 4, error_policy:ErrorPolicy = ErrorPolicy.SKIP) -> list[StageFailure]
```

Generate a report for each community, in place.

Communities at or above min_importance_for_llm_report (internal_weight
-- total weight of edges internal to the community, set by
compute_communities) get a real LLM-generated report, batch_size per
call, bounding total call count at scale. internal_weight, not raw
member count, decides this: a small but
densely-attested community can matter more than a larger sparse one.
Communities below the threshold -- most of a large graph's communities,
which sit near the max_cluster_size floor -- get
\_apply_heuristic_report's deterministic report instead, no LLM call at
all.

A qualifying community's member list is truncated to its top
max_members_per_prompt members (already ordered by local weight
descending) before it enters the batch prompt, protecting the batch
call's token budget from one oversized community without an arbitrary
cut -- the members dropped are the least central ones. When edges is
given, each community's prompt also carries its internal
"source REL_TYPE target" lines (most-attested first, truncated to
max_relations_per_prompt), so the report can state connections the
evidence actually attests; a relation whose endpoint Entity was not
hydrated is omitted.

When the `llm` extra (baml-py) is not installed, qualifying
communities fall back to the heuristic report too: with ErrorPolicy
SKIP a warning is logged and the pipeline completes, with RAISE the
ImportError propagates.

A batch call failure does not block other batches: it is recorded as
one StageFailure per community in that batch, each of which then falls
back to the heuristic report, matching the failure-tolerance shape
merge.py's description-summarization step already uses. A batch
response with fewer reports than communities (a malformed or truncated
response) falls back to the heuristic report for whatever is left over,
rather than discarding the reports that did come back.

**Parameters:**

- **communities** (<code>[list](#list)\[[Community](#agrag.common.data_models.community.Community)\]</code>) – The communities to summarize, mutated in place.
- **entities_by_id** (<code>[dict](#dict)\[[UUID](#uuid.UUID), [Entity](#agrag.common.data_models.entity.Entity)\]</code>) – Every entity the reports will read, keyed by id,
  for building each community's member-summary context.
- **edges** (<code>[list](#list)\[[WeightedEdge](#agrag.ingestion.community.WeightedEdge)\] | None</code>) – The weighted edge list from fetch_relation_edges, used to
  build each community's attested-relation context. None omits
  relation context from the prompts.
- **min_importance_for_llm_report** (<code>[float](#float)</code>) – The internal_weight floor a
  community must meet to get a real LLM report instead of the
  heuristic one.
- **batch_size** (<code>[int](#int)</code>) – Communities summarized per LLM call.
- **max_members_per_prompt** (<code>[int](#int)</code>) – Members per community fed into the LLM
  prompt, highest-centrality first.
- **max_relations_per_prompt** (<code>[int](#int)</code>) – Attested-relation lines per community
  fed into the LLM prompt, most-attested first.
- **max_concurrency** (<code>[int](#int)</code>) – Max concurrent SummarizeCommunities calls.
- **error_policy** (<code>[ErrorPolicy](#agrag.loaders.corpus.types.ErrorPolicy)</code>) – RAISE propagates a batch call failure or a missing
  `llm` extra; anything else records it or falls back and
  continues.

**Returns:**

- <code>[list](#list)\[[StageFailure](#agrag.ingestion.stats.StageFailure)\]</code> – One StageFailure per community whose batch call failed.

##### `agrag.ingestion.community.logger`

```python
logger = logging.getLogger(__name__)
```

##### `agrag.ingestion.community.required_member_ids`

```python
required_member_ids(communities:list[Community], *, min_importance_for_llm_report:float = _DEFAULT_MIN_IMPORTANCE_FOR_LLM_REPORT, max_members_per_prompt:int = _DEFAULT_MAX_MEMBERS_PER_PROMPT) -> set[UUID]
```

Return the member ids generate_community_reports will actually read.

An LLM-qualifying community only needs its top max_members_per_prompt
members (already ordered by local weight, highest first); a
heuristic-report community only needs its top 3. Since level-0
clusters are capped by max_cluster_size and typically much smaller
than max_members_per_prompt, this mainly saves by excluding isolated
entities and any entity type detect_communities() never touches, not
by truncating within a community.

**Parameters:**

- **communities** (<code>[list](#list)\[[Community](#agrag.common.data_models.community.Community)\]</code>) – The communities generate_community_reports will run
  over.
- **min_importance_for_llm_report** (<code>[float](#float)</code>) – Must match the value
  generate_community_reports is called with, or the two
  functions disagree about which communities are LLM-qualifying.
- **max_members_per_prompt** (<code>[int](#int)</code>) – Must match the value
  generate_community_reports is called with.

**Returns:**

- <code>[set](#set)\[[UUID](#uuid.UUID)\]</code> – The union of every community's needed member ids.

#### `agrag.ingestion.extract`

The Extractor interface: reads one Chunk and produces an ExtractionResult.

**Classes:**

- [**BAMLExtractor**](#agrag.ingestion.extract.BAMLExtractor) – Extracts with an LLM, via a BAML function and a runtime ClientRegistry.
- [**EscalatingExtractor**](#agrag.ingestion.extract.EscalatingExtractor) – Runs a cheap primary extractor first, escalating per chunk when it's weak.
- [**ExtractionLLMSettings**](#agrag.ingestion.extract.ExtractionLLMSettings) – Env-backed LLM client config for the extraction role.
- [**Extractor**](#agrag.ingestion.extract.Extractor) – Reads one Chunk and produces the entities and relations it contains.
- [**ExtractorMissingExtraError**](#agrag.ingestion.extract.ExtractorMissingExtraError) – An Extractor needs a package extra that is not installed.
- [**GlinerExtractor**](#agrag.ingestion.extract.GlinerExtractor) – Extracts locally with a GLiNER2.5 model. No network call.

##### `agrag.ingestion.extract.BAMLExtractor`

```python
BAMLExtractor(*, settings:ExtractionLLMSettings | None = None, client:object | None = None) -> None
```

Bases: <code>[Extractor](#agrag.ingestion.extract.Extractor)</code>

Extracts with an LLM, via a BAML function and a runtime ClientRegistry.

**Functions:**

- [**extract**](#agrag.ingestion.extract.BAMLExtractor.extract) – Extract with an LLM call through the configured ClientRegistry.

**Attributes:**

- [**settings**](#agrag.ingestion.extract.BAMLExtractor.settings) –

**Parameters:**

- **settings** (<code>[ExtractionLLMSettings](#agrag.ingestion.extract.ExtractionLLMSettings) | None</code>) – LLM client config. Defaults to `ExtractionLLMSettings()`,
  loaded from the environment/`.env`. Ignored when `client`
  is given: an injected client also disables `settings.retry`,
  since a caller building its own client is assumed to own its
  own retry behavior too.
- **client** (<code>[object](#object) | None</code>) – An already-built BAML client object exposing
  `ExtractEntitiesAndRelations`. Tests inject a fake here.

###### `agrag.ingestion.extract.BAMLExtractor.extract`

```python
extract(chunk:Chunk, schema:GraphSchema) -> ExtractionResult
```

Extract with an LLM call through the configured ClientRegistry.

**Raises:**

- <code>[ExtractorMissingExtraError](#agrag.ingestion.extract.ExtractorMissingExtraError)</code> – The `llm` package extra is not
  installed.
- <code>[ValueError](#ValueError)</code> – `chunk.id` is `None`.

###### `agrag.ingestion.extract.BAMLExtractor.settings`

```python
settings = settings
```

##### `agrag.ingestion.extract.EscalatingExtractor`

```python
EscalatingExtractor(primary:Extractor, escalate_to:Extractor, *, min_confidence:float = 0.5, min_chunk_words:int = 8) -> None
```

Bases: <code>[Extractor](#agrag.ingestion.extract.Extractor)</code>

Runs a cheap primary extractor first, escalating per chunk when it's weak.

**Functions:**

- [**extract**](#agrag.ingestion.extract.EscalatingExtractor.extract) – Extract with the primary extractor, escalating when it's weak.

**Attributes:**

- [**escalate_to**](#agrag.ingestion.extract.EscalatingExtractor.escalate_to) –
- [**min_chunk_words**](#agrag.ingestion.extract.EscalatingExtractor.min_chunk_words) –
- [**min_confidence**](#agrag.ingestion.extract.EscalatingExtractor.min_confidence) –
- [**primary**](#agrag.ingestion.extract.EscalatingExtractor.primary) –

**Parameters:**

- **primary** (<code>[Extractor](#agrag.ingestion.extract.Extractor)</code>) – Runs first, for every chunk.
- **escalate_to** (<code>[Extractor](#agrag.ingestion.extract.Extractor)</code>) – Runs instead of, never in addition to, the primary's
  result, when escalation triggers. Merging both extractors'
  output would mean reconciling overlapping spans between them,
  which is what entity resolution is for, not extraction.
- **min_confidence** (<code>[float](#float)</code>) – Escalate when the primary's mean entity confidence
  falls below this, among entities that report a confidence.
- **min_chunk_words** (<code>[int](#int)</code>) – Below this word count, a zero-entity result from
  the primary is treated as plausibly correct, not a miss.

###### `agrag.ingestion.extract.EscalatingExtractor.escalate_to`

```python
escalate_to = escalate_to
```

###### `agrag.ingestion.extract.EscalatingExtractor.extract`

```python
extract(chunk:Chunk, schema:GraphSchema) -> ExtractionResult
```

Extract with the primary extractor, escalating when it's weak.

Returns escalate_to's result outright when escalation triggers, never
a combination of both extractors' results.

###### `agrag.ingestion.extract.EscalatingExtractor.min_chunk_words`

```python
min_chunk_words = min_chunk_words
```

###### `agrag.ingestion.extract.EscalatingExtractor.min_confidence`

```python
min_confidence = min_confidence
```

###### `agrag.ingestion.extract.EscalatingExtractor.primary`

```python
primary = primary
```

##### `agrag.ingestion.extract.ExtractionLLMSettings`

Bases: <code>[BaseSettings](#pydantic_settings.BaseSettings)</code>

Env-backed LLM client config for the extraction role.

**Attributes:**

- [**clients**](#agrag.ingestion.extract.ExtractionLLMSettings.clients) (<code>[list](#list)\[[LLMClientConfig](#agrag.llm.client_config.LLMClientConfig)\]</code>) – The LLM client(s) to use. One element for a single provider;
  more than one composed per `strategy`.
- [**strategy**](#agrag.ingestion.extract.ExtractionLLMSettings.strategy) (<code>[Literal](#typing.Literal)['single', 'fallback', 'round_robin']</code>) – How to compose multiple clients. Ignored with one client.
- [**retry**](#agrag.ingestion.extract.ExtractionLLMSettings.retry) (<code>[RetryConfig](#agrag.llm.client_config.RetryConfig)</code>) – Retry settings applied to the extraction LLM call.

Env prefix: `EXTRACTION_LLM_`.

**Functions:**

- [**from_openai_compatible_env**](#agrag.ingestion.extract.ExtractionLLMSettings.from_openai_compatible_env) – Build settings from a generic OpenAI-compatible endpoint.

###### `agrag.ingestion.extract.ExtractionLLMSettings.clients`

```python
clients: list[LLMClientConfig]
```

###### `agrag.ingestion.extract.ExtractionLLMSettings.from_openai_compatible_env`

```python
from_openai_compatible_env() -> ExtractionLLMSettings
```

Build settings from a generic OpenAI-compatible endpoint.

Reads `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL_ID` from the
environment or `.env`, so the model name is never hardcoded. Raises
`RuntimeError` when the required variables are not all set.

**Returns:**

- <code>[ExtractionLLMSettings](#agrag.ingestion.extract.ExtractionLLMSettings)</code> – Settings pointing at one `openai-generic` client.

###### `agrag.ingestion.extract.ExtractionLLMSettings.model_config`

```python
model_config = SettingsConfigDict(env_prefix='EXTRACTION_LLM_', env_file='.env', extra='ignore')
```

###### `agrag.ingestion.extract.ExtractionLLMSettings.retry`

```python
retry: RetryConfig = Field(default_factory=RetryConfig)
```

###### `agrag.ingestion.extract.ExtractionLLMSettings.strategy`

```python
strategy: Literal['single', 'fallback', 'round_robin'] = 'single'
```

##### `agrag.ingestion.extract.Extractor`

Bases: <code>[ABC](#abc.ABC)</code>

Reads one Chunk and produces the entities and relations it contains.

**Functions:**

- [**extract**](#agrag.ingestion.extract.Extractor.extract) – Extract entities and relations from one chunk.

###### `agrag.ingestion.extract.Extractor.extract`

```python
extract(chunk:Chunk, schema:GraphSchema) -> ExtractionResult
```

Extract entities and relations from one chunk.

**Parameters:**

- **chunk** (<code>[Chunk](#agrag.common.data_models.chunk.Chunk)</code>) – The chunk to read. Only `chunk.text` and `chunk.id` are used.
- **schema** (<code>[GraphSchema](#agrag.common.data_models.graph_schema.GraphSchema)</code>) – The entity/relation types to extract. Every returned entity's
  `label` and relation's `label` must be declared in this schema.

**Returns:**

- <code>[ExtractionResult](#agrag.common.data_models.extraction.ExtractionResult)</code> – The entities and relations this call found, in extraction order.

##### `agrag.ingestion.extract.ExtractorMissingExtraError`

```python
ExtractorMissingExtraError(component:str, extra:str) -> None
```

Bases: <code>[IngestionError](#agrag.loaders.corpus.errors.IngestionError)</code>

An Extractor needs a package extra that is not installed.

**Attributes:**

- [**component**](#agrag.ingestion.extract.ExtractorMissingExtraError.component) – The class name that needs the extra.
- [**extra**](#agrag.ingestion.extract.ExtractorMissingExtraError.extra) – The package extra to install.

###### `agrag.ingestion.extract.ExtractorMissingExtraError.component`

```python
component = component
```

###### `agrag.ingestion.extract.ExtractorMissingExtraError.extra`

```python
extra = extra
```

##### `agrag.ingestion.extract.GlinerExtractor`

```python
GlinerExtractor(*, model_name:str = 'fastino/gliner2.5-small-v1', model:object | None = None) -> None
```

Bases: <code>[Extractor](#agrag.ingestion.extract.Extractor)</code>

Extracts locally with a GLiNER2.5 model. No network call.

**Functions:**

- [**extract**](#agrag.ingestion.extract.GlinerExtractor.extract) – Extract with the local GLiNER2.5 model.

**Attributes:**

- [**model_name**](#agrag.ingestion.extract.GlinerExtractor.model_name) –

**Parameters:**

- **model_name** (<code>[str](#str)</code>) – The checkpoint to load if `model` is not given.
- **model** (<code>[object](#object) | None</code>) – An already-built GLiNER2.5 model. Tests inject a fake here
  to avoid a real model download.

###### `agrag.ingestion.extract.GlinerExtractor.extract`

```python
extract(chunk:Chunk, schema:GraphSchema) -> ExtractionResult
```

Extract with the local GLiNER2.5 model.

**Raises:**

- <code>[ExtractorMissingExtraError](#agrag.ingestion.extract.ExtractorMissingExtraError)</code> – The `extract` package extra is not
  installed.
- <code>[ValueError](#ValueError)</code> – `chunk.id` is `None`.

###### `agrag.ingestion.extract.GlinerExtractor.model_name`

```python
model_name = model_name
```

#### `agrag.ingestion.graph`

The public Graph API for ingestion.

**Classes:**

- [**Graph**](#agrag.ingestion.graph.Graph) – A knowledge graph that a caller can open and add content to.

**Attributes:**

- [**SYSTEM_RELATION_TYPES**](#agrag.ingestion.graph.SYSTEM_RELATION_TYPES) –
- [**SourceType**](#agrag.ingestion.graph.SourceType) –
- [**SourcesType**](#agrag.ingestion.graph.SourcesType) –

##### `agrag.ingestion.graph.Graph`

```python
Graph(*, schema:GraphSchema, graph_store:GraphStore, embedder:Embedder, extractor:Extractor, tracer:Tracer | None = None, vector_store:VectorStore | None = None, retrieval_settings:RetrievalSettings | None = None) -> None
```

A knowledge graph that a caller can open and add content to.

When an optional VectorStore is configured, every embedding this
graph writes to graph_store is also upserted there, so SearchEngine's
VectorStore path finds the same vectors the GraphStore-native path
does. Collections follow RetrievalSettings' names and are provisioned
by `open()` when missing.

**Functions:**

- [**add**](#agrag.ingestion.graph.Graph.add) – Add content to the graph.
- [**consolidate**](#agrag.ingestion.graph.Graph.consolidate) – Run full tiered resolution against everything persisted.
- [**delete_document**](#agrag.ingestion.graph.Graph.delete_document) – Soft-delete a document by closing its current PART_OF edges.
- [**detect_communities**](#agrag.ingestion.graph.Graph.detect_communities) – Detect entity communities via hierarchical Leiden.
- [**open**](#agrag.ingestion.graph.Graph.open) – Open a graph, connecting and fully provisioning graph_store.
- [**update**](#agrag.ingestion.graph.Graph.update) – Replace one document version, closing its former PART_OF edges.

**Parameters:**

- **schema** (<code>[GraphSchema](#agrag.common.data_models.graph_schema.GraphSchema)</code>) – The entity/relation types this graph validates every
  extraction against.
- **graph_store** (<code>[GraphStore](#agrag.graphdb.base.GraphStore)</code>) – Where entities, relations, chunks, and MENTIONED_IN
  edges are written.
- **embedder** (<code>[Embedder](#agrag.embedding.base.Embedder)</code>) – Populates entity embeddings for native vector search.
- **extractor** (<code>[Extractor](#agrag.ingestion.extract.Extractor)</code>) – Runs against each chunk.
- **tracer** (<code>[Tracer](#opentelemetry.trace.Tracer) | None</code>) – A tracer to record spans for every step. Pass None for none.
- **vector_store** (<code>[VectorStore](#agrag.vectordb.base.VectorStore) | None</code>) – Optional second write target for embeddings. When
  set, every embedding the pipeline writes to graph_store is
  also upserted here, so SearchEngine's VectorStore path finds
  the same vectors the GraphStore-native path does. Also gets
  tombstoned entities deleted after merges and old community
  vectors removed on each detect_communities(apply=True)
  cycle.
- **retrieval_settings** (<code>[RetrievalSettings](#agrag.retrieval.settings.RetrievalSettings) | None</code>) – Collection names for the VectorStore writes.
  None uses RetrievalSettings defaults. Ignored when
  vector_store is None.

###### `agrag.ingestion.graph.Graph.add`

```python
add(source:SourcesType | None = None, *, text:str | None = None, documents:Sequence[Document] | None = None, loader:Loader | None = None, error_policy:ErrorPolicy = ErrorPolicy.RAISE, on_progress:Callable[[AddResult], None] | None = None, return_chunks:bool = False) -> AddResult
```

Add content to the graph.

Give exactly one of `source`, `text`, and `documents`.

**Parameters:**

- **source** (<code>[SourcesType](#agrag.ingestion.graph.SourcesType) | None</code>) – A file path, a directory, a glob, or a list of these.
- **text** (<code>[str](#str) | None</code>) – Raw text to add as one document.
- **documents** (<code>[Sequence](#collections.abc.Sequence)\[[Document](#agrag.common.data_models.document.Document)\] | None</code>) – Already-built documents to add directly.
- **loader** (<code>[Loader](#agrag.loaders.corpus.base.Loader) | None</code>) – A loader to use instead of the registry default. Requires a
  single-file `source`; a directory, glob, or list of sources raises an
  error.
- **error_policy** (<code>[ErrorPolicy](#agrag.loaders.corpus.types.ErrorPolicy)</code>) – The action to take on a per-source error.
- **on_progress** (<code>[Callable](#collections.abc.Callable)\[\[[AddResult](#agrag.ingestion.reports.AddResult)\], None\] | None</code>) – A callback the call runs after each batch and once more
  at the end with the fully-populated result.
- **return_chunks** (<code>[bool](#bool)</code>) – Whether to include the produced chunks in the
  returned AddResult. False by default to avoid holding full text
  for a large corpus when not needed.

**Returns:**

- <code>[AddResult](#agrag.ingestion.reports.AddResult)</code> – A summary of what was added per pipeline stage.

**Raises:**

- <code>[ValueError](#ValueError)</code> – The call got zero, or more than one, of `source`, `text`,
  and `documents`. Also raised when `loader` is set without
  `source`, or with a source that can match more than one file.
- <code>[UnsupportedFormatError](#UnsupportedFormatError)</code> – No loader is registered for a source's format.
- <code>[MissingExtraError](#MissingExtraError)</code> – A loader is registered for a source's format, but its
  package extra is not installed. This error follows `error_policy`
  instead of always stopping the call.
- <code>[ValueError](#ValueError)</code> – The input contains multiple documents with the same
  `document_key`.

###### `agrag.ingestion.graph.Graph.consolidate`

```python
consolidate(*, apply:bool = False) -> ConsolidationReport
```

Run full tiered resolution against everything persisted.

Dry-run by default: produces a report of what would merge before any
node is touched. Pass apply=True to write the merges.

For each EntityType label in self.\_schema, fetches every persisted
entity with that label and runs the same comparator sequence add() uses
in-batch (ExactMatch, FuzzyMatch, LLMVerify) pairwise across all of
them — O(n^2) within each label's population.
Confirmed matches become MergePlans via compute_merge.

**Parameters:**

- **apply** (<code>[bool](#bool)</code>) – Write the computed merges. False produces a report only.

**Returns:**

- <code>[ConsolidationReport](#agrag.ingestion.reports.ConsolidationReport)</code> – A report of every group consolidate() found, applied or not.

###### `agrag.ingestion.graph.Graph.delete_document`

```python
delete_document(document_key:str) -> UpdateResult
```

Soft-delete a document by closing its current PART_OF edges.

###### `agrag.ingestion.graph.Graph.detect_communities`

```python
detect_communities(*, apply:bool = False, max_cluster_size:int = 10, resolution:float = 1.0, seed:int | None = 3735928559) -> CommunityDetectionReport
```

Detect entity communities via hierarchical Leiden.

Dry-run by default: produces a report of the communities that would be
written before any node is touched. Pass apply=True to write them.

Fetches every live domain relation across the whole graph (not scoped
by entity label the way consolidate() is -- community structure spans
entity types), builds a weighted edge list, and runs hierarchical
Leiden off the event loop. Every prior run's Community nodes and
MEMBER_OF edges are deleted before the new ones are written when
apply=True: this is a full recompute, not an incremental update,
so there is no notion of merging this run's output with a
previous one's.

**Parameters:**

- **apply** (<code>[bool](#bool)</code>) – Write the computed communities. False produces a report only.
- **max_cluster_size** (<code>[int](#int)</code>) – Forwarded to compute_communities.
- **resolution** (<code>[float](#float)</code>) – Forwarded to compute_communities.
- **seed** (<code>[int](#int) | None</code>) – Forwarded to compute_communities.

**Returns:**

- <code>[CommunityDetectionReport](#agrag.ingestion.reports.CommunityDetectionReport)</code> – A report of every community this call found, applied or not.

**Raises:**

- <code>[CommunityDetectionMissingExtraError](#agrag.ingestion.community.CommunityDetectionMissingExtraError)</code> –
  graspologic-native is not installed.

###### `agrag.ingestion.graph.Graph.open`

```python
open(*, schema:GraphSchema, graph_store:GraphStore, embedder:Embedder, extractor:Extractor, tracer:Tracer | None = None, vector_store:VectorStore | None = None, retrieval_settings:RetrievalSettings | None = None) -> Graph
```

Open a graph, connecting and fully provisioning graph_store.

Provisioning order: connect, then register every label/relation type
this graph will ever write (schema's own labels/types plus the fixed
system names CHUNK_LABEL/SYSTEM_RELATION_TYPES), then
setup_constraints(), then setup_indexes(), then vector indexes for
every schema entity label — so a brand-new database is fully ready,
including the merge_key index the global exact-match tier needs and
the embedding vector indexes native search needs, before this call
returns. When vector_store is set, the entity, chunk, and community
collections are provisioned there too (created when missing) so the
dual writes never hit an absent collection.

**Parameters:**

- **schema** (<code>[GraphSchema](#agrag.common.data_models.graph_schema.GraphSchema)</code>) – The entity/relation types this graph validates every
  extraction against.
- **graph_store** (<code>[GraphStore](#agrag.graphdb.base.GraphStore)</code>) – Where entities, relations, chunks, and MENTIONED_IN
  edges are written.
- **embedder** (<code>[Embedder](#agrag.embedding.base.Embedder)</code>) – Populates entity embeddings for native vector search.
- **extractor** (<code>[Extractor](#agrag.ingestion.extract.Extractor)</code>) – Runs against each chunk.
- **tracer** (<code>[Tracer](#opentelemetry.trace.Tracer) | None</code>) – A tracer to record spans for every step. Pass None for none.
- **vector_store** (<code>[VectorStore](#agrag.vectordb.base.VectorStore) | None</code>) – Optional second write target for embeddings; see
  __init__.
- **retrieval_settings** (<code>[RetrievalSettings](#agrag.retrieval.settings.RetrievalSettings) | None</code>) – Collection names for the VectorStore writes.
  None uses RetrievalSettings defaults.

**Returns:**

- <code>[Graph](#agrag.ingestion.graph.Graph)</code> – A graph connected to graph_store and ready to accept add() calls.

**Raises:**

- <code>[Exception](#Exception)</code> – Whatever connect(), registration, constraint/index
  setup, or vector-index provisioning raises. graph_store is
  closed first, so a failed open() never leaks a connection.

###### `agrag.ingestion.graph.Graph.update`

```python
update(document_key:str, *, text:str | None = None, source:SourcesType | None = None, loader:Loader | None = None, error_policy:ErrorPolicy = ErrorPolicy.RAISE) -> UpdateResult
```

Replace one document version, closing its former PART_OF edges.

An unchanged content hash is a no-op. The update path uses the same
`add` pipeline as fresh ingestion after it closes the old edges. A
source must resolve to exactly one document.

**Raises:**

- <code>[ValueError](#ValueError)</code> – Both or neither of `text` and `source` are given, a loader
  override targets multiple sources, or a source resolves to any number
  of documents other than one.

##### `agrag.ingestion.graph.SYSTEM_RELATION_TYPES`

```python
SYSTEM_RELATION_TYPES = ['MENTIONED_IN', MEMBER_OF_RELATION, 'PART_OF', 'NEXT_CHUNK']
```

##### `agrag.ingestion.graph.SourceType`

```python
SourceType = Union[str, Path]
```

##### `agrag.ingestion.graph.SourcesType`

```python
SourcesType = Union[SourceType, Sequence[SourceType]]
```

#### `agrag.ingestion.merge`

Merge mechanics: computing how a resolved group of mentions and entities combine.

This module is storage-agnostic: it decides what a merge should look like,
but never touches GraphStore itself. Applying a computed MergePlan is a
separate step.

**Classes:**

- [**ConflictRecord**](#agrag.ingestion.merge.ConflictRecord) – One property that had more than one candidate value.
- [**MergePlan**](#agrag.ingestion.merge.MergePlan) – Computed result of merging zero or more entities and mentions.
- [**PropertyRules**](#agrag.ingestion.merge.PropertyRules) – Per-property conflict resolution, with a default for unlisted properties.
- [**PropertyStrategy**](#agrag.ingestion.merge.PropertyStrategy) – Fallback rule for a property with no entry in PropertyRules.

**Functions:**

- [**apply_merge**](#agrag.ingestion.merge.apply_merge) – Write a computed MergePlan to storage.
- [**compute_merge**](#agrag.ingestion.merge.compute_merge) – Compute how existing_entities and mentions combine into one Entity.
- [**mentioned_in_id**](#agrag.ingestion.merge.mentioned_in_id) – Return the deterministic id for a new Chunk -[:MENTIONED_IN]-> Entity edge.
- [**next_chunk_id**](#agrag.ingestion.merge.next_chunk_id) – Return the deterministic id for a Chunk -[:NEXT_CHUNK]-> Chunk edge.
- [**part_of_id**](#agrag.ingestion.merge.part_of_id) – Return the id for one versioned Document -[:PART_OF]-> Chunk edge.
- [**relation_id**](#agrag.ingestion.merge.relation_id) – Return the deterministic id for a domain relationship triple.

**Attributes:**

- [**PropertyRule**](#agrag.ingestion.merge.PropertyRule) – Per-property conflict resolver.

##### `agrag.ingestion.merge.ConflictRecord`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

One property that had more than one candidate value.

**Attributes:**

- [**field**](#agrag.ingestion.merge.ConflictRecord.field) (<code>[str](#str)</code>) – The property name.
- [**candidates**](#agrag.ingestion.merge.ConflictRecord.candidates) (<code>[list](#list)\[[object](#object)\]</code>) – Every distinct candidate value seen, in encounter order.
- [**resolved**](#agrag.ingestion.merge.ConflictRecord.resolved) (<code>[object](#object)</code>) – The value compute_merge chose.

###### `agrag.ingestion.merge.ConflictRecord.candidates`

```python
candidates: list[object]
```

###### `agrag.ingestion.merge.ConflictRecord.field`

```python
field: str
```

###### `agrag.ingestion.merge.ConflictRecord.resolved`

```python
resolved: object
```

##### `agrag.ingestion.merge.MergePlan`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

Computed result of merging zero or more entities and mentions.

**Attributes:**

- [**survivor**](#agrag.ingestion.merge.MergePlan.survivor) (<code>[Entity](#agrag.common.data_models.entity.Entity)</code>) – The resulting Entity. Its merge_count, source_chunk_ids,
  and merged_from are this call's best local computation, for
  reporting; apply_merge writes new_source_chunk_ids and
  merge_count_delta atomically instead, so a concurrent writer's
  own contribution to the same node is never overwritten.
- [**tombstone_ids**](#agrag.ingestion.merge.MergePlan.tombstone_ids) (<code>[list](#list)\[[UUID](#uuid.UUID)\]</code>) – Ids of entities absorbed into survivor. Also this
  call's new contribution to the survivor's merged_from, applied
  atomically.
- [**conflicts**](#agrag.ingestion.merge.MergePlan.conflicts) (<code>[list](#list)\[[ConflictRecord](#agrag.ingestion.merge.ConflictRecord)\]</code>) – Every field that had more than one candidate value.
- [**accepted_merge_keys**](#agrag.ingestion.merge.MergePlan.accepted_merge_keys) (<code>[list](#list)\[[str](#str)\]</code>) – Every normalized merge_key this merge
  accepted -- from existing_entities and mentions alike, not only
  the survivor's own chosen name -- so a later mention of any
  accepted name resolves back to this entity instead of creating
  a duplicate.
- [**new_source_chunk_ids**](#agrag.ingestion.merge.MergePlan.new_source_chunk_ids) (<code>[list](#list)\[[UUID](#uuid.UUID)\]</code>) – The chunk ids this call's mentions and
  absorbed entities contribute, applied as an atomic union
  against whatever the survivor's node currently has.
- [**merge_count_delta**](#agrag.ingestion.merge.MergePlan.merge_count_delta) (<code>[int](#int)</code>) – The amount to atomically add to whatever
  merge_count the survivor's node currently has.

###### `agrag.ingestion.merge.MergePlan.accepted_merge_keys`

```python
accepted_merge_keys: list[str] = []
```

###### `agrag.ingestion.merge.MergePlan.conflicts`

```python
conflicts: list[ConflictRecord] = []
```

###### `agrag.ingestion.merge.MergePlan.merge_count_delta`

```python
merge_count_delta: int = 0
```

###### `agrag.ingestion.merge.MergePlan.new_source_chunk_ids`

```python
new_source_chunk_ids: list[UUID] = []
```

###### `agrag.ingestion.merge.MergePlan.survivor`

```python
survivor: Entity
```

###### `agrag.ingestion.merge.MergePlan.tombstone_ids`

```python
tombstone_ids: list[UUID] = []
```

##### `agrag.ingestion.merge.PropertyRule`

```python
PropertyRule = Callable[[list[object]], object]
```

Per-property conflict resolver.

Takes every candidate value for one property, in encounter order, already
filtered to exclude None, and returns the resolved value.

##### `agrag.ingestion.merge.PropertyRules`

```python
PropertyRules(rules:dict[str, PropertyRule] = dict(), default:PropertyStrategy = PropertyStrategy.KEEP_FIRST) -> None
```

Per-property conflict resolution, with a default for unlisted properties.

**Attributes:**

- [**rules**](#agrag.ingestion.merge.PropertyRules.rules) (<code>[dict](#dict)\[[str](#str), [PropertyRule](#agrag.ingestion.merge.PropertyRule)\]</code>) – Property name to resolver, for properties needing a specific rule.
- [**default**](#agrag.ingestion.merge.PropertyRules.default) (<code>[PropertyStrategy](#agrag.ingestion.merge.PropertyStrategy)</code>) – Strategy applied to a property with no entry in rules.

###### `agrag.ingestion.merge.PropertyRules.default`

```python
default: PropertyStrategy = PropertyStrategy.KEEP_FIRST
```

###### `agrag.ingestion.merge.PropertyRules.rules`

```python
rules: dict[str, PropertyRule] = field(default_factory=dict)
```

##### `agrag.ingestion.merge.PropertyStrategy`

Bases: <code>[StrEnum](#enum.StrEnum)</code>

Fallback rule for a property with no entry in PropertyRules.

**Attributes:**

- [**KEEP_FIRST**](#agrag.ingestion.merge.PropertyStrategy.KEEP_FIRST) –
- [**KEEP_LAST**](#agrag.ingestion.merge.PropertyStrategy.KEEP_LAST) –
- [**MERGE_ALL**](#agrag.ingestion.merge.PropertyStrategy.MERGE_ALL) –

###### `agrag.ingestion.merge.PropertyStrategy.KEEP_FIRST`

```python
KEEP_FIRST = 'keep_first'
```

###### `agrag.ingestion.merge.PropertyStrategy.KEEP_LAST`

```python
KEEP_LAST = 'keep_last'
```

###### `agrag.ingestion.merge.PropertyStrategy.MERGE_ALL`

```python
MERGE_ALL = 'merge_all'
```

##### `agrag.ingestion.merge.apply_merge`

```python
apply_merge(plan:MergePlan, *, graph_store:GraphStore, schema:GraphSchema) -> None
```

Write a computed MergePlan to storage.

Every call runs inside one GraphStore transaction: when tombstone_ids is
non-empty, it first clears merge_key from every entity about to be
absorbed, since canonical selection can pick a different node as
survivor than the one a property rule (e.g. KEEP_FIRST) resolves the
name from, so the survivor's resolved merge_key can equal a still-live
tombstone's own merge_key -- writing the survivor before clearing that
would collide with the per-label merge_key uniqueness constraint. It
then always upserts the survivor and records a merge-key alias for its
current name, and, when tombstone_ids is non-empty, also tombstones,
deletes edges that would become meaningless self-links, transfers what
remains, and dedupes the survivor's resulting neighbourhood. A failure
partway through leaves no half-written state: no survivor without its
alias, no tombstone without its edges transferred, no transferred edge
without its duplicate cleaned up.

**Parameters:**

- **plan** (<code>[MergePlan](#agrag.ingestion.merge.MergePlan)</code>) – The merge to write.
- **graph_store** (<code>[GraphStore](#agrag.graphdb.base.GraphStore)</code>) – Where the merge is written.
- **schema** (<code>[GraphSchema](#agrag.common.data_models.graph_schema.GraphSchema)</code>) – The schema the survivor's label belongs to.

**Raises:**

- <code>[GraphStoreAliasConflictError](#GraphStoreAliasConflictError)</code> – An accepted merge_key is already owned
  by a live entity outside this merge's own survivor and tombstone
  ids -- a concurrent writer accepted that name as an alias of, or
  created it as the canonical name of, a different entity.
- <code>[GraphStoreDataIntegrityError](#GraphStoreDataIntegrityError)</code> – A candidate conflicting alias owner's
  merged_into chain cycles, points at a missing node, or does not
  reach a live node within the hop limit.

##### `agrag.ingestion.merge.compute_merge`

```python
compute_merge(*, existing_entities:list[Entity], mentions:list[ExtractedEntity], schema:GraphSchema, rules:PropertyRules | None = None, description_settings:Any | None = None, description_client:Any | None = None) -> tuple[MergePlan, list[Any]]
```

Compute how existing_entities and mentions combine into one Entity.

No storage is touched. Zero existing entities produces a brand-new Entity.
One produces an updated copy folding in the mentions. Two or more picks a
canonical survivor and marks the rest for tombstoning.

**Parameters:**

- **existing_entities** (<code>[list](#list)\[[Entity](#agrag.common.data_models.entity.Entity)\]</code>) – Already-persisted entities this call reconciles.
- **mentions** (<code>[list](#list)\[[ExtractedEntity](#agrag.common.data_models.extraction.ExtractedEntity)\]</code>) – Fresh ExtractedEntity mentions to fold in.
- **schema** (<code>[GraphSchema](#agrag.common.data_models.graph_schema.GraphSchema)</code>) – Used to look up the entity type's declared properties for the
  canonical-id schema-completeness check.
- **rules** (<code>[PropertyRules](#agrag.ingestion.merge.PropertyRules) | None</code>) – Per-property conflict resolution. Defaults to keep_first.
- **description_settings** (<code>[Any](#typing.Any) | None</code>) – LLM settings for description summarization.
- **description_client** (<code>[Any](#typing.Any) | None</code>) – Injected LLM client for tests.

**Returns:**

- <code>[tuple](#tuple)\[[MergePlan](#agrag.ingestion.merge.MergePlan), [list](#list)\[[Any](#typing.Any)\]\]</code> – The computed MergePlan and any description-LLM failures.

**Raises:**

- <code>[ValueError](#ValueError)</code> – existing_entities and mentions are both empty, or their
  labels disagree.

##### `agrag.ingestion.merge.mentioned_in_id`

```python
mentioned_in_id(chunk_id:UUID, entity_id:UUID) -> UUID
```

Return the deterministic id for a new Chunk -[:MENTIONED_IN]-> Entity edge.

Only a fresh id for a pair with no persisted edge yet is guaranteed to equal
this. An entity merge can transfer an existing edge onto a new entity id
while keeping its old id (see `transfer_relationships_query`), so a
caller writing to an already-persisted pair should look up the edge by
its endpoints first and fall back to this id only when none is found.

**Parameters:**

- **chunk_id** (<code>[UUID](#uuid.UUID)</code>) – The Chunk's id.
- **entity_id** (<code>[UUID](#uuid.UUID)</code>) – The Entity's id.

**Returns:**

- <code>[UUID](#uuid.UUID)</code> – The edge id. Deterministic: same pair always returns same id.

##### `agrag.ingestion.merge.next_chunk_id`

```python
next_chunk_id(from_chunk_id:UUID, to_chunk_id:UUID) -> UUID
```

Return the deterministic id for a Chunk -[:NEXT_CHUNK]-> Chunk edge.

**Parameters:**

- **from_chunk_id** (<code>[UUID](#uuid.UUID)</code>) – The id of the earlier chunk in sequence.
- **to_chunk_id** (<code>[UUID](#uuid.UUID)</code>) – The id of the chunk that follows it.

**Returns:**

- <code>[UUID](#uuid.UUID)</code> – The edge id. Same pair always returns the same id.

##### `agrag.ingestion.merge.part_of_id`

```python
part_of_id(document_node_id:UUID, chunk_id:UUID, version_id:UUID | str) -> UUID
```

Return the id for one versioned Document -[:PART_OF]-> Chunk edge.

**Parameters:**

- **document_node_id** (<code>[UUID](#uuid.UUID)</code>) – The id of the Document graph node.
- **chunk_id** (<code>[UUID](#uuid.UUID)</code>) – The id of the Chunk.
- **version_id** (<code>[UUID](#uuid.UUID) | [str](#str)</code>) – The identifier for this document version.

**Returns:**

- <code>[UUID](#uuid.UUID)</code> – The edge id. Each document version gets a separate relationship id.

##### `agrag.ingestion.merge.relation_id`

```python
relation_id(source_id:UUID, target_id:UUID, rel_type:str) -> UUID
```

Return the deterministic id for a domain relationship triple.

Two concurrent `add()` calls resolving the same `(source_id, target_id, rel_type)` triple can both miss the existing-relation lookup
and each try to create it; since this id depends only on the triple, both
writers compute the same one, so `upsert_relation_query`'s `MERGE`
converges to a single edge instead of two parallel ones with unrelated
random ids. Mirrors `mentioned_in_id`.

**Parameters:**

- **source_id** (<code>[UUID](#uuid.UUID)</code>) – The relationship's source Entity id.
- **target_id** (<code>[UUID](#uuid.UUID)</code>) – The relationship's target Entity id.
- **rel_type** (<code>[str](#str)</code>) – The relationship's type.

**Returns:**

- <code>[UUID](#uuid.UUID)</code> – The relationship id. Same triple always returns the same id.

#### `agrag.ingestion.reports`

Reports returned by Graph pipeline operations.

One class per module under this package; this init re-exports them so
`from agrag.ingestion.reports import AddResult` keeps working.

**Modules:**

- [**add_result**](#agrag.ingestion.reports.add_result) – Graph.add()'s result type.
- [**community_detection_report**](#agrag.ingestion.reports.community_detection_report) – Graph.detect_communities()'s result type.
- [**consolidation_report**](#agrag.ingestion.reports.consolidation_report) – Graph.consolidate()'s result type.
- [**update_result**](#agrag.ingestion.reports.update_result) – Result returned by document lifecycle operations.

**Classes:**

- [**AddResult**](#agrag.ingestion.reports.AddResult) – Graph.add()'s return type — one summary per pipeline stage.
- [**CommunityDetectionReport**](#agrag.ingestion.reports.CommunityDetectionReport) – Report from Graph.detect_communities().
- [**ConsolidationReport**](#agrag.ingestion.reports.ConsolidationReport) – Report from Graph.consolidate().
- [**UpdateResult**](#agrag.ingestion.reports.UpdateResult) – Summary of an update or soft deletion.

##### `agrag.ingestion.reports.AddResult`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

Graph.add()'s return type — one summary per pipeline stage.

**Attributes:**

- [**ingestion**](#agrag.ingestion.reports.AddResult.ingestion) (<code>[IngestStats](#agrag.ingestion.stats.IngestStats)</code>) – Ingestion-stage results.
- [**extraction**](#agrag.ingestion.reports.AddResult.extraction) (<code>[ExtractionStats](#agrag.ingestion.stats.ExtractionStats)</code>) – Extractor output across every chunk this call
  processed.
- [**resolution**](#agrag.ingestion.reports.AddResult.resolution) (<code>[ResolutionStats](#agrag.ingestion.stats.ResolutionStats)</code>) – Resolution's tier-by-tier match counts.
- [**merge**](#agrag.ingestion.reports.AddResult.merge) (<code>[MergeStats](#agrag.ingestion.stats.MergeStats)</code>) – What merge mechanics did with resolution's groups.
- [**storage**](#agrag.ingestion.reports.AddResult.storage) (<code>[StorageStats](#agrag.ingestion.stats.StorageStats)</code>) – What made it to GraphStore, and what didn't.
- [**chunks**](#agrag.ingestion.reports.AddResult.chunks) (<code>[list](#list)\[[Chunk](#agrag.common.data_models.chunk.Chunk)\]</code>) – Every Chunk this call produced. Empty unless
  return_chunks=True — holding full chunk text for a large
  corpus is a real memory cost most callers don't need paid
  for.

###### `agrag.ingestion.reports.AddResult.chunks`

```python
chunks: list[Chunk] = Field(default_factory=list)
```

###### `agrag.ingestion.reports.AddResult.documents`

```python
documents: int
```

Proxy to ingestion.documents for backward compatibility.

###### `agrag.ingestion.reports.AddResult.extraction`

```python
extraction: ExtractionStats = Field(default_factory=ExtractionStats)
```

###### `agrag.ingestion.reports.AddResult.ingestion`

```python
ingestion: IngestStats = Field(default_factory=IngestStats)
```

###### `agrag.ingestion.reports.AddResult.merge`

```python
merge: MergeStats = Field(default_factory=MergeStats)
```

###### `agrag.ingestion.reports.AddResult.quarantined`

```python
quarantined: int
```

Proxy to ingestion.quarantined for backward compatibility.

###### `agrag.ingestion.reports.AddResult.quarantined_items`

```python
quarantined_items: list[StageFailure]
```

Proxy to ingestion.quarantined_items for backward compatibility.

###### `agrag.ingestion.reports.AddResult.resolution`

```python
resolution: ResolutionStats = Field(default_factory=ResolutionStats)
```

###### `agrag.ingestion.reports.AddResult.skipped`

```python
skipped: int
```

Proxy to ingestion.skipped for backward compatibility.

###### `agrag.ingestion.reports.AddResult.sources`

```python
sources: int
```

Proxy to ingestion.sources for backward compatibility.

###### `agrag.ingestion.reports.AddResult.storage`

```python
storage: StorageStats = Field(default_factory=StorageStats)
```

##### `agrag.ingestion.reports.CommunityDetectionReport`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

Report from Graph.detect_communities().

**Attributes:**

- [**communities**](#agrag.ingestion.reports.CommunityDetectionReport.communities) (<code>[list](#list)\[[Community](#agrag.common.data_models.community.Community)\]</code>) – The communities this call found, whether applied or not.
- [**applied**](#agrag.ingestion.reports.CommunityDetectionReport.applied) (<code>[bool](#bool)</code>) – Whether the communities were written.
- [**failures**](#agrag.ingestion.reports.CommunityDetectionReport.failures) (<code>[list](#list)\[[StageFailure](#agrag.ingestion.stats.StageFailure)\]</code>) – Failures generating an applied community's LLM report or
  embedding its report text. A failed community still gets
  written, with a heuristic report or a missing embedding in
  place of the failed step. Always empty when apply is False.

###### `agrag.ingestion.reports.CommunityDetectionReport.applied`

```python
applied: bool = False
```

###### `agrag.ingestion.reports.CommunityDetectionReport.communities`

```python
communities: list[Community] = Field(default_factory=list)
```

###### `agrag.ingestion.reports.CommunityDetectionReport.failures`

```python
failures: list[StageFailure] = Field(default_factory=list)
```

##### `agrag.ingestion.reports.ConsolidationReport`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

Report from Graph.consolidate().

**Attributes:**

- [**would_merge**](#agrag.ingestion.reports.ConsolidationReport.would_merge) (<code>[list](#list)\[[MergePlan](#agrag.ingestion.merge.MergePlan)\]</code>) – The merge plans found, whether applied or not.
- [**applied**](#agrag.ingestion.reports.ConsolidationReport.applied) (<code>[bool](#bool)</code>) – Whether the plans were applied.
- [**failures**](#agrag.ingestion.reports.ConsolidationReport.failures) (<code>[list](#list)\[[StageFailure](#agrag.ingestion.stats.StageFailure)\]</code>) – Failures re-embedding an applied survivor's final text.
  Always empty when apply is False.

###### `agrag.ingestion.reports.ConsolidationReport.applied`

```python
applied: bool = False
```

###### `agrag.ingestion.reports.ConsolidationReport.failures`

```python
failures: list[StageFailure] = Field(default_factory=list)
```

###### `agrag.ingestion.reports.ConsolidationReport.would_merge`

```python
would_merge: list[MergePlan] = Field(default_factory=list)
```

##### `agrag.ingestion.reports.UpdateResult`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

Summary of an update or soft deletion.

**Attributes:**

- [**document_key**](#agrag.ingestion.reports.UpdateResult.document_key) (<code>[str](#str)</code>) – Stable identity used for the document node.
- [**no_op**](#agrag.ingestion.reports.UpdateResult.no_op) (<code>[bool](#bool)</code>) – Whether no graph changes were needed.
- [**previous_content_hash**](#agrag.ingestion.reports.UpdateResult.previous_content_hash) (<code>[str](#str) | None</code>) – Hash stored before the operation, if present.
- [**new_content_hash**](#agrag.ingestion.reports.UpdateResult.new_content_hash) (<code>[str](#str) | None</code>) – Hash written by an update, or `None` on deletion.
- [**chunks_closed**](#agrag.ingestion.reports.UpdateResult.chunks_closed) (<code>[int](#int)</code>) – Number of open PART_OF edges closed.
- [**add_result**](#agrag.ingestion.reports.UpdateResult.add_result) (<code>[AddResult](#agrag.ingestion.reports.add_result.AddResult) | None</code>) – Ingestion details for changed content, if any.

###### `agrag.ingestion.reports.UpdateResult.add_result`

```python
add_result: AddResult | None = None
```

###### `agrag.ingestion.reports.UpdateResult.chunks_closed`

```python
chunks_closed: int = 0
```

###### `agrag.ingestion.reports.UpdateResult.document_key`

```python
document_key: str
```

###### `agrag.ingestion.reports.UpdateResult.new_content_hash`

```python
new_content_hash: str | None = None
```

###### `agrag.ingestion.reports.UpdateResult.no_op`

```python
no_op: bool
```

###### `agrag.ingestion.reports.UpdateResult.previous_content_hash`

```python
previous_content_hash: str | None = None
```

##### `agrag.ingestion.reports.add_result`

Graph.add()'s result type.

**Classes:**

- [**AddResult**](#agrag.ingestion.reports.add_result.AddResult) – Graph.add()'s return type — one summary per pipeline stage.

###### `agrag.ingestion.reports.add_result.AddResult`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

Graph.add()'s return type — one summary per pipeline stage.

**Attributes:**

- [**ingestion**](#agrag.ingestion.reports.add_result.AddResult.ingestion) (<code>[IngestStats](#agrag.ingestion.stats.IngestStats)</code>) – Ingestion-stage results.
- [**extraction**](#agrag.ingestion.reports.add_result.AddResult.extraction) (<code>[ExtractionStats](#agrag.ingestion.stats.ExtractionStats)</code>) – Extractor output across every chunk this call
  processed.
- [**resolution**](#agrag.ingestion.reports.add_result.AddResult.resolution) (<code>[ResolutionStats](#agrag.ingestion.stats.ResolutionStats)</code>) – Resolution's tier-by-tier match counts.
- [**merge**](#agrag.ingestion.reports.add_result.AddResult.merge) (<code>[MergeStats](#agrag.ingestion.stats.MergeStats)</code>) – What merge mechanics did with resolution's groups.
- [**storage**](#agrag.ingestion.reports.add_result.AddResult.storage) (<code>[StorageStats](#agrag.ingestion.stats.StorageStats)</code>) – What made it to GraphStore, and what didn't.
- [**chunks**](#agrag.ingestion.reports.add_result.AddResult.chunks) (<code>[list](#list)\[[Chunk](#agrag.common.data_models.chunk.Chunk)\]</code>) – Every Chunk this call produced. Empty unless
  return_chunks=True — holding full chunk text for a large
  corpus is a real memory cost most callers don't need paid
  for.

####### `agrag.ingestion.reports.add_result.AddResult.chunks`

```python
chunks: list[Chunk] = Field(default_factory=list)
```

####### `agrag.ingestion.reports.add_result.AddResult.documents`

```python
documents: int
```

Proxy to ingestion.documents for backward compatibility.

####### `agrag.ingestion.reports.add_result.AddResult.extraction`

```python
extraction: ExtractionStats = Field(default_factory=ExtractionStats)
```

####### `agrag.ingestion.reports.add_result.AddResult.ingestion`

```python
ingestion: IngestStats = Field(default_factory=IngestStats)
```

####### `agrag.ingestion.reports.add_result.AddResult.merge`

```python
merge: MergeStats = Field(default_factory=MergeStats)
```

####### `agrag.ingestion.reports.add_result.AddResult.quarantined`

```python
quarantined: int
```

Proxy to ingestion.quarantined for backward compatibility.

####### `agrag.ingestion.reports.add_result.AddResult.quarantined_items`

```python
quarantined_items: list[StageFailure]
```

Proxy to ingestion.quarantined_items for backward compatibility.

####### `agrag.ingestion.reports.add_result.AddResult.resolution`

```python
resolution: ResolutionStats = Field(default_factory=ResolutionStats)
```

####### `agrag.ingestion.reports.add_result.AddResult.skipped`

```python
skipped: int
```

Proxy to ingestion.skipped for backward compatibility.

####### `agrag.ingestion.reports.add_result.AddResult.sources`

```python
sources: int
```

Proxy to ingestion.sources for backward compatibility.

####### `agrag.ingestion.reports.add_result.AddResult.storage`

```python
storage: StorageStats = Field(default_factory=StorageStats)
```

##### `agrag.ingestion.reports.community_detection_report`

Graph.detect_communities()'s result type.

**Classes:**

- [**CommunityDetectionReport**](#agrag.ingestion.reports.community_detection_report.CommunityDetectionReport) – Report from Graph.detect_communities().

###### `agrag.ingestion.reports.community_detection_report.CommunityDetectionReport`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

Report from Graph.detect_communities().

**Attributes:**

- [**communities**](#agrag.ingestion.reports.community_detection_report.CommunityDetectionReport.communities) (<code>[list](#list)\[[Community](#agrag.common.data_models.community.Community)\]</code>) – The communities this call found, whether applied or not.
- [**applied**](#agrag.ingestion.reports.community_detection_report.CommunityDetectionReport.applied) (<code>[bool](#bool)</code>) – Whether the communities were written.
- [**failures**](#agrag.ingestion.reports.community_detection_report.CommunityDetectionReport.failures) (<code>[list](#list)\[[StageFailure](#agrag.ingestion.stats.StageFailure)\]</code>) – Failures generating an applied community's LLM report or
  embedding its report text. A failed community still gets
  written, with a heuristic report or a missing embedding in
  place of the failed step. Always empty when apply is False.

####### `agrag.ingestion.reports.community_detection_report.CommunityDetectionReport.applied`

```python
applied: bool = False
```

####### `agrag.ingestion.reports.community_detection_report.CommunityDetectionReport.communities`

```python
communities: list[Community] = Field(default_factory=list)
```

####### `agrag.ingestion.reports.community_detection_report.CommunityDetectionReport.failures`

```python
failures: list[StageFailure] = Field(default_factory=list)
```

##### `agrag.ingestion.reports.consolidation_report`

Graph.consolidate()'s result type.

**Classes:**

- [**ConsolidationReport**](#agrag.ingestion.reports.consolidation_report.ConsolidationReport) – Report from Graph.consolidate().

###### `agrag.ingestion.reports.consolidation_report.ConsolidationReport`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

Report from Graph.consolidate().

**Attributes:**

- [**would_merge**](#agrag.ingestion.reports.consolidation_report.ConsolidationReport.would_merge) (<code>[list](#list)\[[MergePlan](#agrag.ingestion.merge.MergePlan)\]</code>) – The merge plans found, whether applied or not.
- [**applied**](#agrag.ingestion.reports.consolidation_report.ConsolidationReport.applied) (<code>[bool](#bool)</code>) – Whether the plans were applied.
- [**failures**](#agrag.ingestion.reports.consolidation_report.ConsolidationReport.failures) (<code>[list](#list)\[[StageFailure](#agrag.ingestion.stats.StageFailure)\]</code>) – Failures re-embedding an applied survivor's final text.
  Always empty when apply is False.

####### `agrag.ingestion.reports.consolidation_report.ConsolidationReport.applied`

```python
applied: bool = False
```

####### `agrag.ingestion.reports.consolidation_report.ConsolidationReport.failures`

```python
failures: list[StageFailure] = Field(default_factory=list)
```

####### `agrag.ingestion.reports.consolidation_report.ConsolidationReport.would_merge`

```python
would_merge: list[MergePlan] = Field(default_factory=list)
```

##### `agrag.ingestion.reports.update_result`

Result returned by document lifecycle operations.

**Classes:**

- [**UpdateResult**](#agrag.ingestion.reports.update_result.UpdateResult) – Summary of an update or soft deletion.

###### `agrag.ingestion.reports.update_result.UpdateResult`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

Summary of an update or soft deletion.

**Attributes:**

- [**document_key**](#agrag.ingestion.reports.update_result.UpdateResult.document_key) (<code>[str](#str)</code>) – Stable identity used for the document node.
- [**no_op**](#agrag.ingestion.reports.update_result.UpdateResult.no_op) (<code>[bool](#bool)</code>) – Whether no graph changes were needed.
- [**previous_content_hash**](#agrag.ingestion.reports.update_result.UpdateResult.previous_content_hash) (<code>[str](#str) | None</code>) – Hash stored before the operation, if present.
- [**new_content_hash**](#agrag.ingestion.reports.update_result.UpdateResult.new_content_hash) (<code>[str](#str) | None</code>) – Hash written by an update, or `None` on deletion.
- [**chunks_closed**](#agrag.ingestion.reports.update_result.UpdateResult.chunks_closed) (<code>[int](#int)</code>) – Number of open PART_OF edges closed.
- [**add_result**](#agrag.ingestion.reports.update_result.UpdateResult.add_result) (<code>[AddResult](#agrag.ingestion.reports.add_result.AddResult) | None</code>) – Ingestion details for changed content, if any.

####### `agrag.ingestion.reports.update_result.UpdateResult.add_result`

```python
add_result: AddResult | None = None
```

####### `agrag.ingestion.reports.update_result.UpdateResult.chunks_closed`

```python
chunks_closed: int = 0
```

####### `agrag.ingestion.reports.update_result.UpdateResult.document_key`

```python
document_key: str
```

####### `agrag.ingestion.reports.update_result.UpdateResult.new_content_hash`

```python
new_content_hash: str | None = None
```

####### `agrag.ingestion.reports.update_result.UpdateResult.no_op`

```python
no_op: bool
```

####### `agrag.ingestion.reports.update_result.UpdateResult.previous_content_hash`

```python
previous_content_hash: str | None = None
```

#### `agrag.ingestion.resolve`

Entity resolution: deciding which ExtractedEntity mentions are the same thing.

**Classes:**

- [**CandidateSource**](#agrag.ingestion.resolve.CandidateSource) – Narrows which entity pairs resolution compares — the blocking step.
- [**Comparator**](#agrag.ingestion.resolve.Comparator) – One matching strategy a Resolver runs against a candidate pair.
- [**ComparisonVerdict**](#agrag.ingestion.resolve.ComparisonVerdict) – A Comparator's verdict on one entity pair.
- [**ExactMatch**](#agrag.ingestion.resolve.ExactMatch) – Matches when normalized text is identical. Never returns NO_MATCH.
- [**FuzzyMatch**](#agrag.ingestion.resolve.FuzzyMatch) – Matches by string similarity, within a confident-match/distinct band.
- [**InBatchCandidateSource**](#agrag.ingestion.resolve.InBatchCandidateSource) – Blocks by label: only entities sharing a label are ever compared.
- [**LLMVerify**](#agrag.ingestion.resolve.LLMVerify) – Asks an LLM to verify an ambiguous pair. Last resort; never UNCERTAIN.
- [**ResolutionGroup**](#agrag.ingestion.resolve.ResolutionGroup) – One set of ExtractedEntity indices resolution decided are the same entity.
- [**Resolver**](#agrag.ingestion.resolve.Resolver) – Runs an ordered comparator sequence over blocked candidate pairs.

##### `agrag.ingestion.resolve.CandidateSource`

Bases: <code>[ABC](#abc.ABC)</code>

Narrows which entity pairs resolution compares — the blocking step.

**Functions:**

- [**candidates_for**](#agrag.ingestion.resolve.CandidateSource.candidates_for) – Return indices worth comparing against entities[index].

###### `agrag.ingestion.resolve.CandidateSource.candidates_for`

```python
candidates_for(index:int, entities:list[ExtractedEntity]) -> list[int]
```

Return indices worth comparing against entities[index].

**Parameters:**

- **index** (<code>[int](#int)</code>) – The entity to find candidates for.
- **entities** (<code>[list](#list)\[[ExtractedEntity](#agrag.common.data_models.extraction.ExtractedEntity)\]</code>) – The full entity list this call is scoped to.

**Returns:**

- <code>[list](#list)\[[int](#int)\]</code> – Indices into `entities`, excluding `index` itself. Order does
- <code>[list](#list)\[[int](#int)\]</code> – not matter; duplicates are harmless but wasteful.

##### `agrag.ingestion.resolve.Comparator`

Bases: <code>[ABC](#abc.ABC)</code>

One matching strategy a Resolver runs against a candidate pair.

**Functions:**

- [**compare**](#agrag.ingestion.resolve.Comparator.compare) – Compare two entities.

###### `agrag.ingestion.resolve.Comparator.compare`

```python
compare(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonVerdict
```

Compare two entities.

**Parameters:**

- **a** (<code>[ExtractedEntity](#agrag.common.data_models.extraction.ExtractedEntity)</code>) – The first entity.
- **b** (<code>[ExtractedEntity](#agrag.common.data_models.extraction.ExtractedEntity)</code>) – The second entity.

**Returns:**

- <code>[ComparisonVerdict](#agrag.ingestion.resolve.ComparisonVerdict)</code> – This comparator's verdict. UNCERTAIN defers to the next comparator.

##### `agrag.ingestion.resolve.ComparisonVerdict`

Bases: <code>[StrEnum](#enum.StrEnum)</code>

A Comparator's verdict on one entity pair.

**Attributes:**

- [**MATCH**](#agrag.ingestion.resolve.ComparisonVerdict.MATCH) – The comparator is confident these are the same entity.
- [**NO_MATCH**](#agrag.ingestion.resolve.ComparisonVerdict.NO_MATCH) – The comparator is confident these are different entities.
- [**UNCERTAIN**](#agrag.ingestion.resolve.ComparisonVerdict.UNCERTAIN) – This comparator can't decide; the next one gets a turn.

###### `agrag.ingestion.resolve.ComparisonVerdict.MATCH`

```python
MATCH = 'match'
```

###### `agrag.ingestion.resolve.ComparisonVerdict.NO_MATCH`

```python
NO_MATCH = 'no_match'
```

###### `agrag.ingestion.resolve.ComparisonVerdict.UNCERTAIN`

```python
UNCERTAIN = 'uncertain'
```

##### `agrag.ingestion.resolve.ExactMatch`

Bases: <code>[Comparator](#agrag.ingestion.resolve.Comparator)</code>

Matches when normalized text is identical. Never returns NO_MATCH.

**Functions:**

- [**compare**](#agrag.ingestion.resolve.ExactMatch.compare) – Return MATCH on identical normalized text, else UNCERTAIN.

###### `agrag.ingestion.resolve.ExactMatch.compare`

```python
compare(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonVerdict
```

Return MATCH on identical normalized text, else UNCERTAIN.

##### `agrag.ingestion.resolve.FuzzyMatch`

```python
FuzzyMatch(*, match_above:float = 0.92, no_match_below:float = 0.7) -> None
```

Bases: <code>[Comparator](#agrag.ingestion.resolve.Comparator)</code>

Matches by string similarity, within a confident-match/distinct band.

**Attributes:**

- [**match_above**](#agrag.ingestion.resolve.FuzzyMatch.match_above) – A similarity score at or above this is a confident match.
- [**no_match_below**](#agrag.ingestion.resolve.FuzzyMatch.no_match_below) – A similarity score below this is a confident non-match.
  A score in between is UNCERTAIN and defers to the next comparator.

**Functions:**

- [**compare**](#agrag.ingestion.resolve.FuzzyMatch.compare) – Return a verdict from token-sort-ratio similarity.

###### `agrag.ingestion.resolve.FuzzyMatch.compare`

```python
compare(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonVerdict
```

Return a verdict from token-sort-ratio similarity.

###### `agrag.ingestion.resolve.FuzzyMatch.match_above`

```python
match_above = match_above
```

###### `agrag.ingestion.resolve.FuzzyMatch.no_match_below`

```python
no_match_below = no_match_below
```

##### `agrag.ingestion.resolve.InBatchCandidateSource`

Bases: <code>[CandidateSource](#agrag.ingestion.resolve.CandidateSource)</code>

Blocks by label: only entities sharing a label are ever compared.

Scoped to whatever entity list a caller passes to candidates_for — today,
always the current extraction batch. A future graph-backed candidate source
can replace this without changing any Comparator, since comparators only
ever see the pairs a CandidateSource proposes.

**Functions:**

- [**candidates_for**](#agrag.ingestion.resolve.InBatchCandidateSource.candidates_for) – Return every other entity sharing entities[index]'s label.

###### `agrag.ingestion.resolve.InBatchCandidateSource.candidates_for`

```python
candidates_for(index:int, entities:list[ExtractedEntity]) -> list[int]
```

Return every other entity sharing entities[index]'s label.

##### `agrag.ingestion.resolve.LLMVerify`

```python
LLMVerify(*, chunks_by_id:dict[UUID, Chunk], settings:ExtractionLLMSettings | None = None, client:object | None = None) -> None
```

Bases: <code>[Comparator](#agrag.ingestion.resolve.Comparator)</code>

Asks an LLM to verify an ambiguous pair. Last resort; never UNCERTAIN.

Never raises from an LLM-call failure: it resolves to NO_MATCH instead, by
the same fail-safe design as every comparator a Resolver runs — an
ambiguous or failed comparison never merges two entities. A missing package
extra is a configuration error, not an ambiguous judgment call, and is
raised outright instead (see compare's Raises section).

**Functions:**

- [**compare**](#agrag.ingestion.resolve.LLMVerify.compare) – Return the LLM's verdict, or NO_MATCH if the call itself fails.

**Attributes:**

- [**chunks_by_id**](#agrag.ingestion.resolve.LLMVerify.chunks_by_id) –
- [**settings**](#agrag.ingestion.resolve.LLMVerify.settings) –

**Parameters:**

- **chunks_by_id** (<code>[dict](#dict)\[[UUID](#uuid.UUID), [Chunk](#agrag.common.data_models.chunk.Chunk)\]</code>) – Maps a Chunk id to the Chunk, for prompt context.
- **settings** (<code>[ExtractionLLMSettings](#agrag.ingestion.extract.ExtractionLLMSettings) | None</code>) – LLM client config. Defaults to `ExtractionLLMSettings()`.
  Ignored when `client` is given: an injected client also
  disables `settings.retry`, since a caller building its own
  client is assumed to own its own retry behavior too.
- **client** (<code>[object](#object) | None</code>) – An already-built BAML client. Tests inject a fake here.

###### `agrag.ingestion.resolve.LLMVerify.chunks_by_id`

```python
chunks_by_id = chunks_by_id
```

###### `agrag.ingestion.resolve.LLMVerify.compare`

```python
compare(a:ExtractedEntity, b:ExtractedEntity) -> ComparisonVerdict
```

Return the LLM's verdict, or NO_MATCH if the call itself fails.

**Raises:**

- <code>[ExtractorMissingExtraError](#agrag.ingestion.extract.ExtractorMissingExtraError)</code> – The `llm` package extra is not
  installed.

###### `agrag.ingestion.resolve.LLMVerify.settings`

```python
settings = settings
```

##### `agrag.ingestion.resolve.ResolutionGroup`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

One set of ExtractedEntity indices resolution decided are the same entity.

**Attributes:**

- [**entity_indices**](#agrag.ingestion.resolve.ResolutionGroup.entity_indices) (<code>[list](#list)\[[int](#int)\]</code>) – Indices into the entity list passed to Resolver.resolve.
  A group of one means resolution found no match for that entity.

###### `agrag.ingestion.resolve.ResolutionGroup.entity_indices`

```python
entity_indices: list[int]
```

##### `agrag.ingestion.resolve.Resolver`

```python
Resolver(*, comparators:list[Comparator], candidate_source:CandidateSource) -> None
```

Runs an ordered comparator sequence over blocked candidate pairs.

Groups every pair a comparator confirms as a match into a ResolutionGroup.

**Functions:**

- [**resolve**](#agrag.ingestion.resolve.Resolver.resolve) – Group entities that resolution decided are the same thing.

**Attributes:**

- [**candidate_source**](#agrag.ingestion.resolve.Resolver.candidate_source) –
- [**comparators**](#agrag.ingestion.resolve.Resolver.comparators) –

**Parameters:**

- **comparators** (<code>[list](#list)\[[Comparator](#agrag.ingestion.resolve.Comparator)\]</code>) – Tried in order per candidate pair. The first
  non-UNCERTAIN verdict wins; if every comparator is UNCERTAIN,
  the pair does not merge.
- **candidate_source** (<code>[CandidateSource](#agrag.ingestion.resolve.CandidateSource)</code>) – Narrows which pairs get compared at all.

###### `agrag.ingestion.resolve.Resolver.candidate_source`

```python
candidate_source = candidate_source
```

###### `agrag.ingestion.resolve.Resolver.comparators`

```python
comparators = comparators
```

###### `agrag.ingestion.resolve.Resolver.resolve`

```python
resolve(entities:list[ExtractedEntity]) -> list[ResolutionGroup]
```

Group entities that resolution decided are the same thing.

**Parameters:**

- **entities** (<code>[list](#list)\[[ExtractedEntity](#agrag.common.data_models.extraction.ExtractedEntity)\]</code>) – The entities to resolve. Only entities passed in the
  same call are ever compared against each other — resolving
  against previously-resolved entities from an earlier call is
  not supported by this Resolver.

**Returns:**

- <code>[list](#list)\[[ResolutionGroup](#agrag.ingestion.resolve.ResolutionGroup)\]</code> – One ResolutionGroup per distinct entity found. Every input index
- <code>[list](#list)\[[ResolutionGroup](#agrag.ingestion.resolve.ResolutionGroup)\]</code> – appears in exactly one group.

#### `agrag.ingestion.stats`

Per-stage observability types for the ingestion pipeline.

One class per module under this package; this init re-exports them so
`from agrag.ingestion.stats import StageFailure` keeps working.

**Modules:**

- [**extraction**](#agrag.ingestion.stats.extraction) – Extraction-stage stats.
- [**ingest**](#agrag.ingestion.stats.ingest) – Ingestion-stage stats.
- [**merge**](#agrag.ingestion.stats.merge) – Merge-stage stats.
- [**resolution**](#agrag.ingestion.stats.resolution) – Resolution-stage stats.
- [**stage_failure**](#agrag.ingestion.stats.stage_failure) – Per-stage failure record and its per-call cap.
- [**storage**](#agrag.ingestion.stats.storage) – Storage-write-stage stats.

**Classes:**

- [**CappedFailures**](#agrag.ingestion.stats.CappedFailures) – A capped failure list plus the true count it was built from.
- [**ExtractionStats**](#agrag.ingestion.stats.ExtractionStats) – Extraction-stage results.
- [**IngestStats**](#agrag.ingestion.stats.IngestStats) – Ingestion-stage results.
- [**MergeStats**](#agrag.ingestion.stats.MergeStats) – Merge-stage results.
- [**ResolutionStats**](#agrag.ingestion.stats.ResolutionStats) – Resolution-stage results.
- [**StageFailure**](#agrag.ingestion.stats.StageFailure) – One item's failure within a pipeline stage.
- [**StorageStats**](#agrag.ingestion.stats.StorageStats) – Storage-write-stage results.

**Functions:**

- [**cap_failures**](#agrag.ingestion.stats.cap_failures) – Return failures capped per stage, with the untruncated true count.

**Attributes:**

- [**MAX_FAILURES_PER_STAGE**](#agrag.ingestion.stats.MAX_FAILURES_PER_STAGE) –

##### `agrag.ingestion.stats.CappedFailures`

Bases: <code>[NamedTuple](#typing.NamedTuple)</code>

A capped failure list plus the true count it was built from.

**Attributes:**

- [**items**](#agrag.ingestion.stats.CappedFailures.items) (<code>[list](#list)\[[StageFailure](#agrag.ingestion.stats.stage_failure.StageFailure)\]</code>) – The failure records, truncated to the per-stage cap.
- [**total**](#agrag.ingestion.stats.CappedFailures.total) (<code>[int](#int)</code>) – How many failures the stage actually recorded, before any
  truncation.
- [**truncated**](#agrag.ingestion.stats.CappedFailures.truncated) (<code>[bool](#bool)</code>) – Whether `items` was cut to the per-stage cap.

###### `agrag.ingestion.stats.CappedFailures.items`

```python
items: list[StageFailure]
```

###### `agrag.ingestion.stats.CappedFailures.total`

```python
total: int
```

###### `agrag.ingestion.stats.CappedFailures.truncated`

```python
truncated: bool
```

##### `agrag.ingestion.stats.ExtractionStats`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

Extraction-stage results.

**Attributes:**

- [**chunks_processed**](#agrag.ingestion.stats.ExtractionStats.chunks_processed) (<code>[int](#int)</code>) – Chunks the stage ran the extractor on.
- [**entities_extracted**](#agrag.ingestion.stats.ExtractionStats.entities_extracted) (<code>[int](#int)</code>) – Entities the extractor returned.
- [**relations_extracted**](#agrag.ingestion.stats.ExtractionStats.relations_extracted) (<code>[int](#int)</code>) – Relations the extractor returned.
- [**failures**](#agrag.ingestion.stats.ExtractionStats.failures) (<code>[list](#list)\[[StageFailure](#agrag.ingestion.stats.stage_failure.StageFailure)\]</code>) – Per-item failures, capped per call.
- [**failures_total**](#agrag.ingestion.stats.ExtractionStats.failures_total) (<code>[int](#int)</code>) – Failures recorded before capping.
- [**failures_truncated**](#agrag.ingestion.stats.ExtractionStats.failures_truncated) (<code>[bool](#bool)</code>) – Whether `failures` was cut to the cap.

###### `agrag.ingestion.stats.ExtractionStats.chunks_processed`

```python
chunks_processed: int = 0
```

###### `agrag.ingestion.stats.ExtractionStats.entities_extracted`

```python
entities_extracted: int = 0
```

###### `agrag.ingestion.stats.ExtractionStats.failures`

```python
failures: list[StageFailure] = Field(default_factory=list)
```

###### `agrag.ingestion.stats.ExtractionStats.failures_total`

```python
failures_total: int = 0
```

###### `agrag.ingestion.stats.ExtractionStats.failures_truncated`

```python
failures_truncated: bool = False
```

###### `agrag.ingestion.stats.ExtractionStats.relations_extracted`

```python
relations_extracted: int = 0
```

##### `agrag.ingestion.stats.IngestStats`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

Ingestion-stage results.

**Attributes:**

- [**documents**](#agrag.ingestion.stats.IngestStats.documents) (<code>[int](#int)</code>) –
- [**quarantined**](#agrag.ingestion.stats.IngestStats.quarantined) (<code>[int](#int)</code>) –
- [**quarantined_items**](#agrag.ingestion.stats.IngestStats.quarantined_items) (<code>[list](#list)\[[StageFailure](#agrag.ingestion.stats.stage_failure.StageFailure)\]</code>) –
- [**skipped**](#agrag.ingestion.stats.IngestStats.skipped) (<code>[int](#int)</code>) –
- [**sources**](#agrag.ingestion.stats.IngestStats.sources) (<code>[int](#int)</code>) –

###### `agrag.ingestion.stats.IngestStats.documents`

```python
documents: int = 0
```

###### `agrag.ingestion.stats.IngestStats.quarantined`

```python
quarantined: int = 0
```

###### `agrag.ingestion.stats.IngestStats.quarantined_items`

```python
quarantined_items: list[StageFailure] = Field(default_factory=list)
```

###### `agrag.ingestion.stats.IngestStats.skipped`

```python
skipped: int = 0
```

###### `agrag.ingestion.stats.IngestStats.sources`

```python
sources: int = 0
```

##### `agrag.ingestion.stats.MAX_FAILURES_PER_STAGE`

```python
MAX_FAILURES_PER_STAGE = 200
```

##### `agrag.ingestion.stats.MergeStats`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

Merge-stage results.

**Attributes:**

- [**nodes_created**](#agrag.ingestion.stats.MergeStats.nodes_created) (<code>[int](#int)</code>) – Brand-new entities materialized this call.
- [**nodes_updated**](#agrag.ingestion.stats.MergeStats.nodes_updated) (<code>[int](#int)</code>) – Existing entities that absorbed new mention data
  without tombstoning anything.
- [**nodes_merged**](#agrag.ingestion.stats.MergeStats.nodes_merged) (<code>[int](#int)</code>) – Entities tombstoned into a survivor this call.
- [**conflicts_resolved**](#agrag.ingestion.stats.MergeStats.conflicts_resolved) (<code>[int](#int)</code>) – Total property/description conflicts resolved
  across every merge this call performed.
- [**failures**](#agrag.ingestion.stats.MergeStats.failures) (<code>[list](#list)\[[StageFailure](#agrag.ingestion.stats.stage_failure.StageFailure)\]</code>) – Includes an LLM failure during description
  summarization. The merge still falls back to concatenation and
  completes, but the failure is recorded here.
- [**failures_total**](#agrag.ingestion.stats.MergeStats.failures_total) (<code>[int](#int)</code>) – Failures recorded before capping.
- [**failures_truncated**](#agrag.ingestion.stats.MergeStats.failures_truncated) (<code>[bool](#bool)</code>) – Whether `failures` was cut to the cap.

###### `agrag.ingestion.stats.MergeStats.conflicts_resolved`

```python
conflicts_resolved: int = 0
```

###### `agrag.ingestion.stats.MergeStats.failures`

```python
failures: list[StageFailure] = Field(default_factory=list)
```

###### `agrag.ingestion.stats.MergeStats.failures_total`

```python
failures_total: int = 0
```

###### `agrag.ingestion.stats.MergeStats.failures_truncated`

```python
failures_truncated: bool = False
```

###### `agrag.ingestion.stats.MergeStats.nodes_created`

```python
nodes_created: int = 0
```

###### `agrag.ingestion.stats.MergeStats.nodes_merged`

```python
nodes_merged: int = 0
```

###### `agrag.ingestion.stats.MergeStats.nodes_updated`

```python
nodes_updated: int = 0
```

##### `agrag.ingestion.stats.ResolutionStats`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

Resolution-stage results.

**Attributes:**

- [**exact_match_hits**](#agrag.ingestion.stats.ResolutionStats.exact_match_hits) (<code>[int](#int)</code>) – Mentions that matched an already-persisted
  entity via the global exact-match tier.
- [**in_batch_groups**](#agrag.ingestion.stats.ResolutionStats.in_batch_groups) (<code>[int](#int)</code>) – Resolution groups the in-batch fuzzy/LLM tier
  found.
- [**ambiguous_count**](#agrag.ingestion.stats.ResolutionStats.ambiguous_count) (<code>[int](#int)</code>) – Comparisons no comparator could confidently
  decide. These pairs are never merged.

###### `agrag.ingestion.stats.ResolutionStats.ambiguous_count`

```python
ambiguous_count: int = 0
```

###### `agrag.ingestion.stats.ResolutionStats.exact_match_hits`

```python
exact_match_hits: int = 0
```

###### `agrag.ingestion.stats.ResolutionStats.in_batch_groups`

```python
in_batch_groups: int = 0
```

##### `agrag.ingestion.stats.StageFailure`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

One item's failure within a pipeline stage.

**Attributes:**

- [**item_id**](#agrag.ingestion.stats.StageFailure.item_id) (<code>[str](#str)</code>) – The chunk id, mention id, or batch id — whichever unit
  the stage failed on.
- [**error_type**](#agrag.ingestion.stats.StageFailure.error_type) (<code>[str](#str)</code>) – The exception's class name.
- [**error_message**](#agrag.ingestion.stats.StageFailure.error_message) (<code>[str](#str)</code>) – The exception's message.
- [**trace_id**](#agrag.ingestion.stats.StageFailure.trace_id) (<code>[str](#str) | None</code>) – The OTel trace id correlating to the full span detail,
  when tracing is configured.
- [**span_id**](#agrag.ingestion.stats.StageFailure.span_id) (<code>[str](#str) | None</code>) – The OTel span id within that trace.

###### `agrag.ingestion.stats.StageFailure.error_message`

```python
error_message: str
```

###### `agrag.ingestion.stats.StageFailure.error_type`

```python
error_type: str
```

###### `agrag.ingestion.stats.StageFailure.item_id`

```python
item_id: str
```

###### `agrag.ingestion.stats.StageFailure.span_id`

```python
span_id: str | None = None
```

###### `agrag.ingestion.stats.StageFailure.trace_id`

```python
trace_id: str | None = None
```

##### `agrag.ingestion.stats.StorageStats`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

Storage-write-stage results.

**Attributes:**

- [**nodes_written**](#agrag.ingestion.stats.StorageStats.nodes_written) (<code>[int](#int)</code>) – Chunk and Entity nodes together, one aggregate
  count rather than a sub-count per kind — both are written in
  the same final phase, so there is one natural accounting
  point.
- [**relationships_written**](#agrag.ingestion.stats.StorageStats.relationships_written) (<code>[int](#int)</code>) – Domain Relation and MENTIONED_IN edges
  together, for the same reason.
- [**failures**](#agrag.ingestion.stats.StorageStats.failures) (<code>[list](#list)\[[StageFailure](#agrag.ingestion.stats.stage_failure.StageFailure)\]</code>) – Isolated graph-write failures are reported per record and
  capped per call. Conversion, embedding, vector-store, and other
  non-isolatable graph failures can use one stage-level failure.
  The counts include only records that landed.
- [**failures_total**](#agrag.ingestion.stats.StorageStats.failures_total) (<code>[int](#int)</code>) – Failures recorded before capping.
- [**failures_truncated**](#agrag.ingestion.stats.StorageStats.failures_truncated) (<code>[bool](#bool)</code>) – Whether `failures` was cut to the cap.

###### `agrag.ingestion.stats.StorageStats.failures`

```python
failures: list[StageFailure] = Field(default_factory=list)
```

###### `agrag.ingestion.stats.StorageStats.failures_total`

```python
failures_total: int = 0
```

###### `agrag.ingestion.stats.StorageStats.failures_truncated`

```python
failures_truncated: bool = False
```

###### `agrag.ingestion.stats.StorageStats.nodes_written`

```python
nodes_written: int = 0
```

###### `agrag.ingestion.stats.StorageStats.relationships_written`

```python
relationships_written: int = 0
```

##### `agrag.ingestion.stats.cap_failures`

```python
cap_failures(failures:list[StageFailure]) -> CappedFailures
```

Return failures capped per stage, with the untruncated true count.

Logs a warning when truncation occurs, since the capped list alone no
longer reflects how many items actually failed.

**Parameters:**

- **failures** (<code>[list](#list)\[[StageFailure](#agrag.ingestion.stats.stage_failure.StageFailure)\]</code>) – Every failure the stage recorded.

**Returns:**

- <code>[CappedFailures](#agrag.ingestion.stats.stage_failure.CappedFailures)</code> – The capped list, the true failure count, and whether the list was
- <code>[CappedFailures](#agrag.ingestion.stats.stage_failure.CappedFailures)</code> – truncated.

##### `agrag.ingestion.stats.extraction`

Extraction-stage stats.

**Classes:**

- [**ExtractionStats**](#agrag.ingestion.stats.extraction.ExtractionStats) – Extraction-stage results.

###### `agrag.ingestion.stats.extraction.ExtractionStats`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

Extraction-stage results.

**Attributes:**

- [**chunks_processed**](#agrag.ingestion.stats.extraction.ExtractionStats.chunks_processed) (<code>[int](#int)</code>) – Chunks the stage ran the extractor on.
- [**entities_extracted**](#agrag.ingestion.stats.extraction.ExtractionStats.entities_extracted) (<code>[int](#int)</code>) – Entities the extractor returned.
- [**relations_extracted**](#agrag.ingestion.stats.extraction.ExtractionStats.relations_extracted) (<code>[int](#int)</code>) – Relations the extractor returned.
- [**failures**](#agrag.ingestion.stats.extraction.ExtractionStats.failures) (<code>[list](#list)\[[StageFailure](#agrag.ingestion.stats.stage_failure.StageFailure)\]</code>) – Per-item failures, capped per call.
- [**failures_total**](#agrag.ingestion.stats.extraction.ExtractionStats.failures_total) (<code>[int](#int)</code>) – Failures recorded before capping.
- [**failures_truncated**](#agrag.ingestion.stats.extraction.ExtractionStats.failures_truncated) (<code>[bool](#bool)</code>) – Whether `failures` was cut to the cap.

####### `agrag.ingestion.stats.extraction.ExtractionStats.chunks_processed`

```python
chunks_processed: int = 0
```

####### `agrag.ingestion.stats.extraction.ExtractionStats.entities_extracted`

```python
entities_extracted: int = 0
```

####### `agrag.ingestion.stats.extraction.ExtractionStats.failures`

```python
failures: list[StageFailure] = Field(default_factory=list)
```

####### `agrag.ingestion.stats.extraction.ExtractionStats.failures_total`

```python
failures_total: int = 0
```

####### `agrag.ingestion.stats.extraction.ExtractionStats.failures_truncated`

```python
failures_truncated: bool = False
```

####### `agrag.ingestion.stats.extraction.ExtractionStats.relations_extracted`

```python
relations_extracted: int = 0
```

##### `agrag.ingestion.stats.ingest`

Ingestion-stage stats.

**Classes:**

- [**IngestStats**](#agrag.ingestion.stats.ingest.IngestStats) – Ingestion-stage results.

###### `agrag.ingestion.stats.ingest.IngestStats`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

Ingestion-stage results.

**Attributes:**

- [**documents**](#agrag.ingestion.stats.ingest.IngestStats.documents) (<code>[int](#int)</code>) –
- [**quarantined**](#agrag.ingestion.stats.ingest.IngestStats.quarantined) (<code>[int](#int)</code>) –
- [**quarantined_items**](#agrag.ingestion.stats.ingest.IngestStats.quarantined_items) (<code>[list](#list)\[[StageFailure](#agrag.ingestion.stats.stage_failure.StageFailure)\]</code>) –
- [**skipped**](#agrag.ingestion.stats.ingest.IngestStats.skipped) (<code>[int](#int)</code>) –
- [**sources**](#agrag.ingestion.stats.ingest.IngestStats.sources) (<code>[int](#int)</code>) –

####### `agrag.ingestion.stats.ingest.IngestStats.documents`

```python
documents: int = 0
```

####### `agrag.ingestion.stats.ingest.IngestStats.quarantined`

```python
quarantined: int = 0
```

####### `agrag.ingestion.stats.ingest.IngestStats.quarantined_items`

```python
quarantined_items: list[StageFailure] = Field(default_factory=list)
```

####### `agrag.ingestion.stats.ingest.IngestStats.skipped`

```python
skipped: int = 0
```

####### `agrag.ingestion.stats.ingest.IngestStats.sources`

```python
sources: int = 0
```

##### `agrag.ingestion.stats.merge`

Merge-stage stats.

**Classes:**

- [**MergeStats**](#agrag.ingestion.stats.merge.MergeStats) – Merge-stage results.

###### `agrag.ingestion.stats.merge.MergeStats`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

Merge-stage results.

**Attributes:**

- [**nodes_created**](#agrag.ingestion.stats.merge.MergeStats.nodes_created) (<code>[int](#int)</code>) – Brand-new entities materialized this call.
- [**nodes_updated**](#agrag.ingestion.stats.merge.MergeStats.nodes_updated) (<code>[int](#int)</code>) – Existing entities that absorbed new mention data
  without tombstoning anything.
- [**nodes_merged**](#agrag.ingestion.stats.merge.MergeStats.nodes_merged) (<code>[int](#int)</code>) – Entities tombstoned into a survivor this call.
- [**conflicts_resolved**](#agrag.ingestion.stats.merge.MergeStats.conflicts_resolved) (<code>[int](#int)</code>) – Total property/description conflicts resolved
  across every merge this call performed.
- [**failures**](#agrag.ingestion.stats.merge.MergeStats.failures) (<code>[list](#list)\[[StageFailure](#agrag.ingestion.stats.stage_failure.StageFailure)\]</code>) – Includes an LLM failure during description
  summarization. The merge still falls back to concatenation and
  completes, but the failure is recorded here.
- [**failures_total**](#agrag.ingestion.stats.merge.MergeStats.failures_total) (<code>[int](#int)</code>) – Failures recorded before capping.
- [**failures_truncated**](#agrag.ingestion.stats.merge.MergeStats.failures_truncated) (<code>[bool](#bool)</code>) – Whether `failures` was cut to the cap.

####### `agrag.ingestion.stats.merge.MergeStats.conflicts_resolved`

```python
conflicts_resolved: int = 0
```

####### `agrag.ingestion.stats.merge.MergeStats.failures`

```python
failures: list[StageFailure] = Field(default_factory=list)
```

####### `agrag.ingestion.stats.merge.MergeStats.failures_total`

```python
failures_total: int = 0
```

####### `agrag.ingestion.stats.merge.MergeStats.failures_truncated`

```python
failures_truncated: bool = False
```

####### `agrag.ingestion.stats.merge.MergeStats.nodes_created`

```python
nodes_created: int = 0
```

####### `agrag.ingestion.stats.merge.MergeStats.nodes_merged`

```python
nodes_merged: int = 0
```

####### `agrag.ingestion.stats.merge.MergeStats.nodes_updated`

```python
nodes_updated: int = 0
```

##### `agrag.ingestion.stats.resolution`

Resolution-stage stats.

**Classes:**

- [**ResolutionStats**](#agrag.ingestion.stats.resolution.ResolutionStats) – Resolution-stage results.

###### `agrag.ingestion.stats.resolution.ResolutionStats`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

Resolution-stage results.

**Attributes:**

- [**exact_match_hits**](#agrag.ingestion.stats.resolution.ResolutionStats.exact_match_hits) (<code>[int](#int)</code>) – Mentions that matched an already-persisted
  entity via the global exact-match tier.
- [**in_batch_groups**](#agrag.ingestion.stats.resolution.ResolutionStats.in_batch_groups) (<code>[int](#int)</code>) – Resolution groups the in-batch fuzzy/LLM tier
  found.
- [**ambiguous_count**](#agrag.ingestion.stats.resolution.ResolutionStats.ambiguous_count) (<code>[int](#int)</code>) – Comparisons no comparator could confidently
  decide. These pairs are never merged.

####### `agrag.ingestion.stats.resolution.ResolutionStats.ambiguous_count`

```python
ambiguous_count: int = 0
```

####### `agrag.ingestion.stats.resolution.ResolutionStats.exact_match_hits`

```python
exact_match_hits: int = 0
```

####### `agrag.ingestion.stats.resolution.ResolutionStats.in_batch_groups`

```python
in_batch_groups: int = 0
```

##### `agrag.ingestion.stats.stage_failure`

Per-stage failure record and its per-call cap.

**Classes:**

- [**CappedFailures**](#agrag.ingestion.stats.stage_failure.CappedFailures) – A capped failure list plus the true count it was built from.
- [**StageFailure**](#agrag.ingestion.stats.stage_failure.StageFailure) – One item's failure within a pipeline stage.

**Functions:**

- [**cap_failures**](#agrag.ingestion.stats.stage_failure.cap_failures) – Return failures capped per stage, with the untruncated true count.

**Attributes:**

- [**MAX_FAILURES_PER_STAGE**](#agrag.ingestion.stats.stage_failure.MAX_FAILURES_PER_STAGE) –
- [**logger**](#agrag.ingestion.stats.stage_failure.logger) –

###### `agrag.ingestion.stats.stage_failure.CappedFailures`

Bases: <code>[NamedTuple](#typing.NamedTuple)</code>

A capped failure list plus the true count it was built from.

**Attributes:**

- [**items**](#agrag.ingestion.stats.stage_failure.CappedFailures.items) (<code>[list](#list)\[[StageFailure](#agrag.ingestion.stats.stage_failure.StageFailure)\]</code>) – The failure records, truncated to the per-stage cap.
- [**total**](#agrag.ingestion.stats.stage_failure.CappedFailures.total) (<code>[int](#int)</code>) – How many failures the stage actually recorded, before any
  truncation.
- [**truncated**](#agrag.ingestion.stats.stage_failure.CappedFailures.truncated) (<code>[bool](#bool)</code>) – Whether `items` was cut to the per-stage cap.

####### `agrag.ingestion.stats.stage_failure.CappedFailures.items`

```python
items: list[StageFailure]
```

####### `agrag.ingestion.stats.stage_failure.CappedFailures.total`

```python
total: int
```

####### `agrag.ingestion.stats.stage_failure.CappedFailures.truncated`

```python
truncated: bool
```

###### `agrag.ingestion.stats.stage_failure.MAX_FAILURES_PER_STAGE`

```python
MAX_FAILURES_PER_STAGE = 200
```

###### `agrag.ingestion.stats.stage_failure.StageFailure`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

One item's failure within a pipeline stage.

**Attributes:**

- [**item_id**](#agrag.ingestion.stats.stage_failure.StageFailure.item_id) (<code>[str](#str)</code>) – The chunk id, mention id, or batch id — whichever unit
  the stage failed on.
- [**error_type**](#agrag.ingestion.stats.stage_failure.StageFailure.error_type) (<code>[str](#str)</code>) – The exception's class name.
- [**error_message**](#agrag.ingestion.stats.stage_failure.StageFailure.error_message) (<code>[str](#str)</code>) – The exception's message.
- [**trace_id**](#agrag.ingestion.stats.stage_failure.StageFailure.trace_id) (<code>[str](#str) | None</code>) – The OTel trace id correlating to the full span detail,
  when tracing is configured.
- [**span_id**](#agrag.ingestion.stats.stage_failure.StageFailure.span_id) (<code>[str](#str) | None</code>) – The OTel span id within that trace.

####### `agrag.ingestion.stats.stage_failure.StageFailure.error_message`

```python
error_message: str
```

####### `agrag.ingestion.stats.stage_failure.StageFailure.error_type`

```python
error_type: str
```

####### `agrag.ingestion.stats.stage_failure.StageFailure.item_id`

```python
item_id: str
```

####### `agrag.ingestion.stats.stage_failure.StageFailure.span_id`

```python
span_id: str | None = None
```

####### `agrag.ingestion.stats.stage_failure.StageFailure.trace_id`

```python
trace_id: str | None = None
```

###### `agrag.ingestion.stats.stage_failure.cap_failures`

```python
cap_failures(failures:list[StageFailure]) -> CappedFailures
```

Return failures capped per stage, with the untruncated true count.

Logs a warning when truncation occurs, since the capped list alone no
longer reflects how many items actually failed.

**Parameters:**

- **failures** (<code>[list](#list)\[[StageFailure](#agrag.ingestion.stats.stage_failure.StageFailure)\]</code>) – Every failure the stage recorded.

**Returns:**

- <code>[CappedFailures](#agrag.ingestion.stats.stage_failure.CappedFailures)</code> – The capped list, the true failure count, and whether the list was
- <code>[CappedFailures](#agrag.ingestion.stats.stage_failure.CappedFailures)</code> – truncated.

###### `agrag.ingestion.stats.stage_failure.logger`

```python
logger = logging.getLogger(__name__)
```

##### `agrag.ingestion.stats.storage`

Storage-write-stage stats.

**Classes:**

- [**StorageStats**](#agrag.ingestion.stats.storage.StorageStats) – Storage-write-stage results.

###### `agrag.ingestion.stats.storage.StorageStats`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

Storage-write-stage results.

**Attributes:**

- [**nodes_written**](#agrag.ingestion.stats.storage.StorageStats.nodes_written) (<code>[int](#int)</code>) – Chunk and Entity nodes together, one aggregate
  count rather than a sub-count per kind — both are written in
  the same final phase, so there is one natural accounting
  point.
- [**relationships_written**](#agrag.ingestion.stats.storage.StorageStats.relationships_written) (<code>[int](#int)</code>) – Domain Relation and MENTIONED_IN edges
  together, for the same reason.
- [**failures**](#agrag.ingestion.stats.storage.StorageStats.failures) (<code>[list](#list)\[[StageFailure](#agrag.ingestion.stats.stage_failure.StageFailure)\]</code>) – Isolated graph-write failures are reported per record and
  capped per call. Conversion, embedding, vector-store, and other
  non-isolatable graph failures can use one stage-level failure.
  The counts include only records that landed.
- [**failures_total**](#agrag.ingestion.stats.storage.StorageStats.failures_total) (<code>[int](#int)</code>) – Failures recorded before capping.
- [**failures_truncated**](#agrag.ingestion.stats.storage.StorageStats.failures_truncated) (<code>[bool](#bool)</code>) – Whether `failures` was cut to the cap.

####### `agrag.ingestion.stats.storage.StorageStats.failures`

```python
failures: list[StageFailure] = Field(default_factory=list)
```

####### `agrag.ingestion.stats.storage.StorageStats.failures_total`

```python
failures_total: int = 0
```

####### `agrag.ingestion.stats.storage.StorageStats.failures_truncated`

```python
failures_truncated: bool = False
```

####### `agrag.ingestion.stats.storage.StorageStats.nodes_written`

```python
nodes_written: int = 0
```

####### `agrag.ingestion.stats.storage.StorageStats.relationships_written`

```python
relationships_written: int = 0
```

### `agrag.observability`

OpenTelemetry wiring for the ingestion layer.

This module imports only `opentelemetry-api`. The SDK and exporters stay in
the optional `observability` extra and are never imported here; a caller
wires them before opening a graph. The tracer is constructor-injected, never
ambient.

**Functions:**

- [**get_tracer**](#agrag.observability.get_tracer) – Return a usable tracer.
- [**traced**](#agrag.observability.traced) – Wrap a call in a span on the given tracer.

#### `agrag.observability.get_tracer`

```python
get_tracer(tracer:Tracer | None) -> Tracer
```

Return a usable tracer.

**Parameters:**

- **tracer** (<code>[Tracer](#opentelemetry.trace.Tracer) | None</code>) – A caller-supplied tracer, or `None` to use OpenTelemetry's
  global no-op tracer.

**Returns:**

- <code>[Tracer](#opentelemetry.trace.Tracer)</code> – The supplied tracer, or the global no-op tracer when the caller passed `None`.

#### `agrag.observability.traced`

```python
traced(tracer:Tracer | None) -> Callable[[Callable], Callable]
```

Wrap a call in a span on the given tracer.

Use this at each pipeline call site (loader, chunker). It works on both
sync and async functions; the span name is the wrapped callable's
qualified name.

**Parameters:**

- **tracer** (<code>[Tracer](#opentelemetry.trace.Tracer) | None</code>) – The tracer to record on, or `None` for a no-op span.

**Returns:**

- <code>[Callable](#typing.Callable)\[\[[Callable](#typing.Callable)\], [Callable](#typing.Callable)\]</code> – A decorator that wraps the target callable in a span.

### `agrag.retrieval`

Retrieval package: search engine, fusion, reranking, and retrievers.

**Modules:**

- [**community_context**](#agrag.retrieval.community_context) – Community-report enrichment: local-search-style budget-capped context.
- [**errors**](#agrag.retrieval.errors) – Errors that the retrieval layer raises.
- [**filters**](#agrag.retrieval.filters) – Constraints applied across every retrieval method in one call.
- [**fusion**](#agrag.retrieval.fusion) – Reciprocal Rank Fusion: combine ranked results from multiple methods.
- [**identity**](#agrag.retrieval.identity) – Shared identity resolution for merged_into chains.
- [**methods**](#agrag.retrieval.methods) – Low-level search method helpers shared by retrievers.
- [**recipes**](#agrag.retrieval.recipes) – Named, data-only configurations of what SearchEngine runs.
- [**rerank**](#agrag.retrieval.rerank) – Rerankers that reorder fused search results.
- [**retrievers**](#agrag.retrieval.retrievers) – Retriever implementations for entity, chunk, BFS, and text2cypher search.
- [**search_engine**](#agrag.retrieval.search_engine) – Retrieval's public entry point, independent of Graph.
- [**settings**](#agrag.retrieval.settings) – Env-backed configuration for retrieval methods and fusion.

#### `agrag.retrieval.community_context`

Community-report enrichment: local-search-style budget-capped context.

**Functions:**

- [**community_context**](#agrag.retrieval.community_context.community_context) – Return the top-overlapping communities' reports for a set of entities.

##### `agrag.retrieval.community_context.community_context`

```python
community_context(entity_ids:list[UUID], *, graph_store:GraphStore, top_k:int = 3, filters:SearchFilters | None = None) -> list[SearchResult]
```

Return the top-overlapping communities' reports for a set of entities.

Ranks candidate communities by how many of entity_ids are their
members (Microsoft GraphRAG's local-search pattern), then returns the
top_k as SearchResults so they flow through the same Fusion/Ledger
machinery as any other result.

**Parameters:**

- **entity_ids** (<code>[list](#list)\[[UUID](#uuid.UUID)\]</code>) – The entity ids already found by a search's other
  retrieval methods.
- **graph_store** (<code>[GraphStore](#agrag.graphdb.base.GraphStore)</code>) – Where the overlap lookup runs.
- **top_k** (<code>[int](#int)</code>) – The maximum number of communities to return. Zero or
  negative returns no results without querying.
- **filters** (<code>[SearchFilters](#agrag.retrieval.filters.SearchFilters) | None</code>) – Applied to the candidate community node via
  `document_ids`/`properties` (`to_cypher_where`); labels
  are not applied, since they check node labels and a Community
  node never carries an entity label. Community nodes carry no
  document or tenant scope of their own, so a filter naming a
  property Community nodes never have matches no communities --
  a document- or property-scoped search gets no community
  enrichment rather than one drawn from outside its scope.

**Returns:**

- <code>[list](#list)\[[SearchResult](#agrag.common.data_models.search_result.SearchResult)\]</code> – Up to top_k SearchResults wrapping Community items, highest overlap
- <code>[list](#list)\[[SearchResult](#agrag.common.data_models.search_result.SearchResult)\]</code> – first. Empty when entity_ids is empty or no community overlaps.

#### `agrag.retrieval.errors`

Errors that the retrieval layer raises.

**Classes:**

- [**AllRetrievalMethodsFailedError**](#agrag.retrieval.errors.AllRetrievalMethodsFailedError) – Every retrieval method a Recipe named failed.
- [**RetrievalError**](#agrag.retrieval.errors.RetrievalError) – The base class for every retrieval error.
- [**UnknownRecipeMethodError**](#agrag.retrieval.errors.UnknownRecipeMethodError) – A Recipe named a method SearchEngine does not know how to run.

##### `agrag.retrieval.errors.AllRetrievalMethodsFailedError`

```python
AllRetrievalMethodsFailedError(failures:dict[str, BaseException]) -> None
```

Bases: <code>[RetrievalError](#agrag.retrieval.errors.RetrievalError)</code>

Every retrieval method a Recipe named failed.

Raised instead of returning an empty result list so a total
retrieval outage is not mistaken for a query with no matches.

**Attributes:**

- [**failures**](#agrag.retrieval.errors.AllRetrievalMethodsFailedError.failures) – Each failed method name mapped to the exception it
  raised.

###### `agrag.retrieval.errors.AllRetrievalMethodsFailedError.failures`

```python
failures = failures
```

##### `agrag.retrieval.errors.RetrievalError`

Bases: <code>[Exception](#Exception)</code>

The base class for every retrieval error.

##### `agrag.retrieval.errors.UnknownRecipeMethodError`

```python
UnknownRecipeMethodError(unknown:list[str], known:list[str]) -> None
```

Bases: <code>[RetrievalError](#agrag.retrieval.errors.RetrievalError)</code>

A Recipe named a method SearchEngine does not know how to run.

A misspelled method name is a configuration error and must be
raised at search time so an empty successful search cannot
silently hide a typo.

**Attributes:**

- [**unknown**](#agrag.retrieval.errors.UnknownRecipeMethodError.unknown) – The method names the recipe listed that are not in
  the retriever registry.
- [**known**](#agrag.retrieval.errors.UnknownRecipeMethodError.known) – The method names this SearchEngine can run.

###### `agrag.retrieval.errors.UnknownRecipeMethodError.known`

```python
known = list(known)
```

###### `agrag.retrieval.errors.UnknownRecipeMethodError.unknown`

```python
unknown = list(unknown)
```

#### `agrag.retrieval.filters`

Constraints applied across every retrieval method in one call.

**Classes:**

- [**SearchFilters**](#agrag.retrieval.filters.SearchFilters) – Constraints applied across every retrieval method in one call.

##### `agrag.retrieval.filters.SearchFilters`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

Constraints applied across every retrieval method in one call.

**Attributes:**

- [**labels**](#agrag.retrieval.filters.SearchFilters.labels) (<code>[list](#list)\[[str](#str)\]</code>) – Entity labels a result must have, when searching
  entities.
- [**relation_types**](#agrag.retrieval.filters.SearchFilters.relation_types) (<code>[list](#list)\[[str](#str)\]</code>) – Relation types a traversal may cross.
- [**document_ids**](#agrag.retrieval.filters.SearchFilters.document_ids) (<code>[list](#list)\[[str](#str)\]</code>) – Restrict chunk results to these source
  documents.
- [**properties**](#agrag.retrieval.filters.SearchFilters.properties) (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\]</code>) – Exact-match property filters, applied
  identically to vector-store payload filters and Cypher
  WHERE clauses.

**Functions:**

- [**to_cypher_where**](#agrag.retrieval.filters.SearchFilters.to_cypher_where) – Return a parameterized WHERE clause fragment.
- [**to_payload_filter**](#agrag.retrieval.filters.SearchFilters.to_payload_filter) – Return a flat-dict filter for VectorStore search calls.
- [**to_property_filter**](#agrag.retrieval.filters.SearchFilters.to_property_filter) – Return a flat-dict filter over node properties only.

###### `agrag.retrieval.filters.SearchFilters.document_ids`

```python
document_ids: list[str] = Field(default_factory=list)
```

###### `agrag.retrieval.filters.SearchFilters.labels`

```python
labels: list[str] = Field(default_factory=list)
```

###### `agrag.retrieval.filters.SearchFilters.properties`

```python
properties: dict[str, Any] = Field(default_factory=dict)
```

###### `agrag.retrieval.filters.SearchFilters.relation_types`

```python
relation_types: list[str] = Field(default_factory=list)
```

###### `agrag.retrieval.filters.SearchFilters.to_cypher_where`

```python
to_cypher_where(node_var:str = 'node') -> tuple[str, dict[str, Any]]
```

Return a parameterized WHERE clause fragment.

Labels are emitted as native Cypher node labels (`node:Label`)
rather than property filters, since Neo4j represents entity types
as labels on nodes. Document-id and property filters go through
`filter_clause` as before.

**Parameters:**

- **node_var** (<code>[str](#str)</code>) – The Cypher variable bound to the node.

**Returns:**

- <code>[tuple](#tuple)\[[str](#str), [dict](#dict)\[[str](#str), [Any](#typing.Any)\]\]</code> – The WHERE clause text and parameters dict.

###### `agrag.retrieval.filters.SearchFilters.to_payload_filter`

```python
to_payload_filter() -> dict[str, Any]
```

Return a flat-dict filter for VectorStore search calls.

Labels become a `label` payload key, which is how a
VectorStore records the graph label a record came from. A
GraphStore holds labels on the node itself, not as a property,
so the native path uses `to_property_filter` instead and
selects labels by the index it searches.

**Returns:**

- <code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\]</code> – A dict suitable for VectorStore.search/hybrid_search
- <code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\]</code> – filters parameter.

###### `agrag.retrieval.filters.SearchFilters.to_property_filter`

```python
to_property_filter() -> dict[str, Any]
```

Return a flat-dict filter over node properties only.

Excludes `labels`, which are node labels rather than
properties on every graph backend this project supports.

**Returns:**

- <code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\]</code> – A dict of property name to expected value, where a list
- <code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\]</code> – value means any of.

#### `agrag.retrieval.fusion`

Reciprocal Rank Fusion: combine ranked results from multiple methods.

**Functions:**

- [**fuse**](#agrag.retrieval.fusion.fuse) – Combine every method's ranked results into one deduplicated list.

##### `agrag.retrieval.fusion.fuse`

```python
fuse(results_by_method:dict[str, list[SearchResult]], *, rrf_k:int = 60) -> list[SearchResult]
```

Combine every method's ranked results into one deduplicated list.

Runs unconditionally, even for a single method, so a Rerank pass
never sees duplicates. Uses Reciprocal Rank Fusion: an item's
fused score is the sum of 1 / (rrf_k + rank) across every method
that returned it.

Each method contributes at most one vote per item, scored at the
item's best (lowest) rank within that method. A multi-label
entity that surfaces in two positions of one method's output, or
a pre-fusion `merged_into` collapse, only adds one vote from
that method, so duplicate hits from a single retriever cannot
unfairly promote an item over a single best hit from another
method.

Deduplication uses SearchResult.identity_key, which is (type, id)
after hydration has already resolved any merged_into chain to the
live survivor. Fusion does not re-resolve identity; it trusts that
every SearchResult it receives already carries a live id.

**Parameters:**

- **results_by_method** (<code>[dict](#dict)\[[str](#str), [list](#list)\[[SearchResult](#agrag.common.data_models.search_result.SearchResult)\]\]</code>) – Each method's own ranked output, keyed by
  method name.
- **rrf_k** (<code>[int](#int)</code>) – The RRF constant; higher values flatten the influence
  of rank position.

**Returns:**

- <code>[list](#list)\[[SearchResult](#agrag.common.data_models.search_result.SearchResult)\]</code> – One list, ranked by fused score descending, one entry per
- <code>[list](#list)\[[SearchResult](#agrag.common.data_models.search_result.SearchResult)\]</code> – distinct identity_key.

#### `agrag.retrieval.identity`

Shared identity resolution for merged_into chains.

**Functions:**

- [**resolve_entity**](#agrag.retrieval.identity.resolve_entity) – Return the live Entity behind an id, following merged_into.

**Attributes:**

- [**MAX_MERGE_HOPS**](#agrag.retrieval.identity.MAX_MERGE_HOPS) –

##### `agrag.retrieval.identity.MAX_MERGE_HOPS`

```python
MAX_MERGE_HOPS = 32
```

##### `agrag.retrieval.identity.resolve_entity`

```python
resolve_entity(graph_store:GraphStore, entity_id:UUID) -> Entity
```

Return the live Entity behind an id, following merged_into.

Every retrieval path that can produce an entity id must call
this before wrapping the id in a SearchResult. This is the
single place the merged_into invariant is enforced.

A merge writes a `merged_into` property on the tombstone rather
than a relationship, so the chain is walked one hop per query.

**Parameters:**

- **graph_store** (<code>[GraphStore](#agrag.graphdb.base.GraphStore)</code>) – Where the entity and its possible tombstone
  chain live.
- **entity_id** (<code>[UUID](#uuid.UUID)</code>) – The id a retrieval method found, which may or
  may not still be live.

**Returns:**

- <code>[Entity](#agrag.common.data_models.entity.Entity)</code> – The live Entity, after resolving zero or more hops.

**Raises:**

- <code>[ValueError](#ValueError)</code> – The id does not exist, its node cannot be parsed,
  the chain points at a missing node, the chain cycles, or it
  is longer than `MAX_MERGE_HOPS`.

#### `agrag.retrieval.methods`

Low-level search method helpers shared by retrievers.

**Modules:**

- [**vector**](#agrag.retrieval.methods.vector) – Shared vector search helper for GraphStore and VectorStore.

##### `agrag.retrieval.methods.vector`

Shared vector search helper for GraphStore and VectorStore.

**Functions:**

- [**vector_search**](#agrag.retrieval.methods.vector.vector_search) – Embed query and search on whichever store is configured.

###### `agrag.retrieval.methods.vector.vector_search`

```python
vector_search(query:str, *, embedder:Embedder, graph_store:GraphStore, vector_store:VectorStore | None, collection:str, labels:Sequence[str], limit:int, filters:SearchFilters | None, settings:RetrievalSettings) -> list[VectorHit]
```

Embed query and search on whichever store is configured.

When vector_store is set, runs hybrid_search there (dense plus
BM25, blended by settings.hybrid_alpha) against `collection`.
When it is None, runs GraphStore's native vector_search once per
label in `labels` and merges the hits, ignoring hybrid_alpha
since that path is dense-only. One native vector index exists per
label, so a search over several labels is several searches.

**Parameters:**

- **query** (<code>[str](#str)</code>) – The natural-language query text to embed.
- **embedder** (<code>[Embedder](#agrag.embedding.base.Embedder)</code>) – Produces the query's dense vector.
- **graph_store** (<code>[GraphStore](#agrag.graphdb.base.GraphStore)</code>) – The GraphStore-native fallback target.
- **vector_store** (<code>[VectorStore](#agrag.vectordb.base.VectorStore) | None</code>) – The optional VectorStore target; None selects
  the GraphStore-native path.
- **collection** (<code>[str](#str)</code>) – The VectorStore collection name.
- **labels** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\]</code>) – The node labels to search on the GraphStore-native
  path, each backed by its own vector index.
- **limit** (<code>[int](#int)</code>) – Maximum hits to return.
- **filters** (<code>[SearchFilters](#agrag.retrieval.filters.SearchFilters) | None</code>) – Constraints translated to whichever store is
  searched. Labels are a payload key on the VectorStore
  path and choose the searched indexes on the native path,
  so they are not sent as node property filters.
- **settings** (<code>[RetrievalSettings](#agrag.retrieval.settings.RetrievalSettings)</code>) – Supplies hybrid_alpha for the VectorStore path.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – Ranked VectorHits, from whichever store was searched.

**Raises:**

- <code>[ValueError](#ValueError)</code> – The native path was selected with no labels to
  search.

#### `agrag.retrieval.recipes`

Named, data-only configurations of what SearchEngine runs.

**Classes:**

- [**Recipe**](#agrag.retrieval.recipes.Recipe) – A named configuration of what SearchEngine runs for a query.

**Attributes:**

- [**CHUNK**](#agrag.retrieval.recipes.CHUNK) –
- [**ENTITY**](#agrag.retrieval.recipes.ENTITY) –
- [**GRAPH_EXPAND**](#agrag.retrieval.recipes.GRAPH_EXPAND) –
- [**HYBRID**](#agrag.retrieval.recipes.HYBRID) –
- [**HYBRID_RERANKED**](#agrag.retrieval.recipes.HYBRID_RERANKED) –
- [**THEMATIC**](#agrag.retrieval.recipes.THEMATIC) –

##### `agrag.retrieval.recipes.CHUNK`

```python
CHUNK = Recipe(methods=['chunk'], limit=10)
```

##### `agrag.retrieval.recipes.ENTITY`

```python
ENTITY = Recipe(methods=['entity'], limit=10)
```

##### `agrag.retrieval.recipes.GRAPH_EXPAND`

```python
GRAPH_EXPAND = Recipe(methods=['entity'], bfs=True, limit=20, community_expand=True)
```

##### `agrag.retrieval.recipes.HYBRID`

```python
HYBRID = Recipe(methods=['entity', 'chunk'], limit=10)
```

##### `agrag.retrieval.recipes.HYBRID_RERANKED`

```python
HYBRID_RERANKED = Recipe(methods=['entity', 'chunk'], reranker='cross_encoder', limit=10, community_expand=True)
```

##### `agrag.retrieval.recipes.Recipe`

Bases: <code>[BaseModel](#pydantic.BaseModel)</code>

A named configuration of what SearchEngine runs for a query.

**Attributes:**

- [**methods**](#agrag.retrieval.recipes.Recipe.methods) (<code>[list](#list)\[[str](#str)\]</code>) – Which retrieval methods to fan out to
  concurrently, by name.
- [**bfs**](#agrag.retrieval.recipes.Recipe.bfs) (<code>[bool](#bool)</code>) – Whether to run a BFS expansion after methods
  complete, seeded from their entity results. BFS
  needs seed ids methods produce, so it cannot run
  concurrently with them.
- [**bfs_depth**](#agrag.retrieval.recipes.Recipe.bfs_depth) (<code>[int](#int) | None</code>) – Traversal depth when bfs is true. None uses
  RetrievalSettings.traversal_depth.
- [**reranker**](#agrag.retrieval.recipes.Recipe.reranker) (<code>[Literal](#typing.Literal)['cross_encoder', 'node_distance'] | None</code>) – The optional Rerank pass to run after Fusion.
  None skips reranking.
- [**limit**](#agrag.retrieval.recipes.Recipe.limit) (<code>[int](#int)</code>) – The maximum number of results SearchEngine
  returns.
- [**community_expand**](#agrag.retrieval.recipes.Recipe.community_expand) (<code>[bool](#bool)</code>) – Whether to fetch and fuse in overlapping
  communities' reports after BFS.
- [**community_top_k**](#agrag.retrieval.recipes.Recipe.community_top_k) (<code>[int](#int)</code>) – How many communities community_context
  returns, and (when reranker is cross_encoder) how many
  are reserved a slot after rerank.

###### `agrag.retrieval.recipes.Recipe.bfs`

```python
bfs: bool = False
```

###### `agrag.retrieval.recipes.Recipe.bfs_depth`

```python
bfs_depth: int | None = None
```

###### `agrag.retrieval.recipes.Recipe.community_expand`

```python
community_expand: bool = False
```

###### `agrag.retrieval.recipes.Recipe.community_top_k`

```python
community_top_k: int = 3
```

###### `agrag.retrieval.recipes.Recipe.limit`

```python
limit: int = 10
```

###### `agrag.retrieval.recipes.Recipe.methods`

```python
methods: list[str]
```

###### `agrag.retrieval.recipes.Recipe.reranker`

```python
reranker: Literal['cross_encoder', 'node_distance'] | None = None
```

##### `agrag.retrieval.recipes.THEMATIC`

```python
THEMATIC = Recipe(methods=['community'], limit=5)
```

#### `agrag.retrieval.rerank`

Rerankers that reorder fused search results.

**Modules:**

- [**cross_encoder**](#agrag.retrieval.rerank.cross_encoder) – Cross-encoder reranker using sentence-transformers.
- [**node_distance**](#agrag.retrieval.rerank.node_distance) – Node distance reranker: reorder by graph proximity to seeds.

##### `agrag.retrieval.rerank.cross_encoder`

Cross-encoder reranker using sentence-transformers.

**Functions:**

- [**cross_encoder_rerank**](#agrag.retrieval.rerank.cross_encoder.cross_encoder_rerank) – Rerank results using a cross-encoder model.

###### `agrag.retrieval.rerank.cross_encoder.cross_encoder_rerank`

```python
cross_encoder_rerank(query:str, results:list[SearchResult], *, model:str = 'cross-encoder/ms-marco-MiniLM-L-6-v2', min_score:float | None = None) -> list[SearchResult]
```

Rerank results using a cross-encoder model.

Requires the `embed-local` extra (sentence-transformers). Scores
(query, text) pairs and reorders by relevance. Drops results scoring
below min_score when set. The model is cached per name (see
\_load_cross_encoder), and the blocking predict() call runs via
asyncio.to_thread so a larger configured model cannot stall the event
loop for other concurrent search() calls. Concurrent first loads of the
same model share one in-flight construction behind a per-model lock, so
only one instance (and one download) occurs.

**Parameters:**

- **query** (<code>[str](#str)</code>) – The natural-language query text.
- **results** (<code>[list](#list)\[[SearchResult](#agrag.common.data_models.search_result.SearchResult)\]</code>) – The fused results to rerank.
- **model** (<code>[str](#str)</code>) – The sentence-transformers CrossEncoder model name/path.
  Callers pass RetrievalSettings.cross_encoder_model.
- **min_score** (<code>[float](#float) | None</code>) – Optional minimum score threshold. Results below this
  are dropped.

**Returns:**

- <code>[list](#list)\[[SearchResult](#agrag.common.data_models.search_result.SearchResult)\]</code> – Results reranked by cross-encoder score, descending.

##### `agrag.retrieval.rerank.node_distance`

Node distance reranker: reorder by graph proximity to seeds.

**Functions:**

- [**node_distance_rerank**](#agrag.retrieval.rerank.node_distance.node_distance_rerank) – Rerank results by graph proximity to seed entity ids.

###### `agrag.retrieval.rerank.node_distance.node_distance_rerank`

```python
node_distance_rerank(results:list[SearchResult], *, graph_store:GraphStore, seed_ids:list[UUID]) -> list[SearchResult]
```

Rerank results by graph proximity to seed entity ids.

Uses shortest-path distance from each result entity to the
closest seed entity. Entities closer to seeds rank higher.
Results without an entity item (chunks, relations) are placed
at the end with a high distance penalty.

**Parameters:**

- **results** (<code>[list](#list)\[[SearchResult](#agrag.common.data_models.search_result.SearchResult)\]</code>) – The fused results to rerank.
- **graph_store** (<code>[GraphStore](#agrag.graphdb.base.GraphStore)</code>) – The graph store for shortest-path queries.
- **seed_ids** (<code>[list](#list)\[[UUID](#uuid.UUID)\]</code>) – The seed entity ids to measure distance from. Seeds
  are the query's direct hits, not the whole candidate list:
  a candidate that is its own seed measures distance zero,
  so seeding with every candidate leaves the order unchanged.

**Returns:**

- <code>[list](#list)\[[SearchResult](#agrag.common.data_models.search_result.SearchResult)\]</code> – Results reranked by proximity, closest first.

#### `agrag.retrieval.retrievers`

Retriever implementations for entity, chunk, BFS, and text2cypher search.

**Modules:**

- [**base**](#agrag.retrieval.retrievers.base) – Abstract base class for retrieval methods.
- [**bfs**](#agrag.retrieval.retrievers.bfs) – BFS retriever: graph traversal from seed entity ids.
- [**chunk**](#agrag.retrieval.retrievers.chunk) – Chunk retriever: dense vector search over chunks.
- [**community**](#agrag.retrieval.retrievers.community) – Community retriever: dense vector search over community reports.
- [**entity**](#agrag.retrieval.retrievers.entity) – Entity retriever: dense vector search over entities.
- [**text2cypher**](#agrag.retrieval.retrievers.text2cypher) – Text2Cypher retriever: generate Cypher from natural language.

##### `agrag.retrieval.retrievers.base`

Abstract base class for retrieval methods.

**Classes:**

- [**Retriever**](#agrag.retrieval.retrievers.base.Retriever) – One retrieval method: given a query, return SearchResults.

###### `agrag.retrieval.retrievers.base.Retriever`

Bases: <code>[ABC](#abc.ABC)</code>

One retrieval method: given a query, return SearchResults.

Subclasses own exactly one strategy (dense entity search, chunk
search, BFS expansion). SearchEngine fans a query out to every
Retriever a Recipe names and hands the combined output to Fusion.

**Functions:**

- [**retrieve**](#agrag.retrieval.retrievers.base.Retriever.retrieve) – Run this retrieval method and return hydrated results.

**Attributes:**

- [**name**](#agrag.retrieval.retrievers.base.Retriever.name) (<code>[str](#str)</code>) –

####### `agrag.retrieval.retrievers.base.Retriever.name`

```python
name: str
```

####### `agrag.retrieval.retrievers.base.Retriever.retrieve`

```python
retrieve(query:str, *, filters:SearchFilters | None = None, limit:int = 10) -> list[SearchResult]
```

Run this retrieval method and return hydrated results.

##### `agrag.retrieval.retrievers.bfs`

BFS retriever: graph traversal from seed entity ids.

**Classes:**

- [**BFSRetriever**](#agrag.retrieval.retrievers.bfs.BFSRetriever) – Graph traversal from seed entity ids.

###### `agrag.retrieval.retrievers.bfs.BFSRetriever`

```python
BFSRetriever(*, graph_store:GraphStore, settings:RetrievalSettings | None = None) -> None
```

Bases: <code>[Retriever](#agrag.retrieval.retrievers.base.Retriever)</code>

Graph traversal from seed entity ids.

Takes seed entity ids (from a prior EntityRetriever call, or
supplied directly), runs bfs_expand_query, and hydrates the
returned entities through resolve_entity and relations directly.
Degree-capped by RetrievalSettings.traversal_limit.

**Functions:**

- [**retrieve**](#agrag.retrieval.retrievers.bfs.BFSRetriever.retrieve) – Run BFS expansion from seed entity ids.

**Attributes:**

- [**name**](#agrag.retrieval.retrievers.bfs.BFSRetriever.name) –

**Parameters:**

- **graph_store** (<code>[GraphStore](#agrag.graphdb.base.GraphStore)</code>) – The graph store to traverse.
- **settings** (<code>[RetrievalSettings](#agrag.retrieval.settings.RetrievalSettings) | None</code>) – Retrieval configuration; defaults from
  environment.

####### `agrag.retrieval.retrievers.bfs.BFSRetriever.name`

```python
name = 'bfs'
```

####### `agrag.retrieval.retrievers.bfs.BFSRetriever.retrieve`

```python
retrieve(query:str, *, filters:SearchFilters | None = None, limit:int | None = None, seed_ids:list[UUID] | None = None, depth:int | None = None) -> list[SearchResult]
```

Run BFS expansion from seed entity ids.

**Parameters:**

- **query** (<code>[str](#str)</code>) – The natural-language query text (unused for BFS,
  kept for interface consistency).
- **filters** (<code>[SearchFilters](#agrag.retrieval.filters.SearchFilters) | None</code>) – Constraints applied to traversal. relation_types
  restrict which relationships the traversal crosses;
  property filters apply to neighbor nodes.
- **limit** (<code>[int](#int) | None</code>) – Maximum results. None uses traversal_limit.
- **seed_ids** (<code>[list](#list)\[[UUID](#uuid.UUID)\] | None</code>) – The entity ids to expand from. If None, BFS
  returns empty.
- **depth** (<code>[int](#int) | None</code>) – BFS hops. None uses
  RetrievalSettings.traversal_depth.

**Returns:**

- <code>[list](#list)\[[SearchResult](#agrag.common.data_models.search_result.SearchResult)\]</code> – SearchResults with entities and relations found via BFS.

##### `agrag.retrieval.retrievers.chunk`

Chunk retriever: dense vector search over chunks.

**Classes:**

- [**ChunkRetriever**](#agrag.retrieval.retrievers.chunk.ChunkRetriever) – Dense chunk search via vector similarity.

###### `agrag.retrieval.retrievers.chunk.ChunkRetriever`

```python
ChunkRetriever(*, graph_store:GraphStore, embedder:Embedder, vector_store:VectorStore | None = None, settings:RetrievalSettings | None = None) -> None
```

Bases: <code>[Retriever](#agrag.retrieval.retrievers.base.Retriever)</code>

Dense chunk search via vector similarity.

Chunks are never tombstoned, so no merged_into resolution is
needed. Embeds the query, searches via the GraphStore-native or
VectorStore path, then hydrates each hit into a Chunk. The native
path searches the `Chunk` vector index ingestion provisions; the
VectorStore path searches `chunk_collection`.

**Functions:**

- [**retrieve**](#agrag.retrieval.retrievers.chunk.ChunkRetriever.retrieve) – Run chunk search and return hydrated results.

**Attributes:**

- [**name**](#agrag.retrieval.retrievers.chunk.ChunkRetriever.name) –

**Parameters:**

- **graph_store** (<code>[GraphStore](#agrag.graphdb.base.GraphStore)</code>) – Backs chunk search when vector_store is
  absent.
- **embedder** (<code>[Embedder](#agrag.embedding.base.Embedder)</code>) – Produces query vectors.
- **vector_store** (<code>[VectorStore](#agrag.vectordb.base.VectorStore) | None</code>) – Optional VectorStore for hybrid search.
- **settings** (<code>[RetrievalSettings](#agrag.retrieval.settings.RetrievalSettings) | None</code>) – Retrieval configuration; defaults from
  environment.

####### `agrag.retrieval.retrievers.chunk.ChunkRetriever.name`

```python
name = 'chunk'
```

####### `agrag.retrieval.retrievers.chunk.ChunkRetriever.retrieve`

```python
retrieve(query:str, *, filters:SearchFilters | None = None, limit:int | None = None) -> list[SearchResult]
```

Run chunk search and return hydrated results.

**Parameters:**

- **query** (<code>[str](#str)</code>) – The natural-language query text.
- **filters** (<code>[SearchFilters](#agrag.retrieval.filters.SearchFilters) | None</code>) – Constraints applied to the search.
- **limit** (<code>[int](#int) | None</code>) – Maximum results. None uses settings.chunk_top_k.
  Zero or negative returns no results without searching.

**Returns:**

- <code>[list](#list)\[[SearchResult](#agrag.common.data_models.search_result.SearchResult)\]</code> – Ranked SearchResults with hydrated Chunk items.

##### `agrag.retrieval.retrievers.community`

Community retriever: dense vector search over community reports.

**Classes:**

- [**CommunityRetriever**](#agrag.retrieval.retrievers.community.CommunityRetriever) – Dense search over community reports, for direct thematic questions.

###### `agrag.retrieval.retrievers.community.CommunityRetriever`

```python
CommunityRetriever(*, graph_store:GraphStore, embedder:Embedder, vector_store:VectorStore | None = None, settings:RetrievalSettings | None = None) -> None
```

Bases: <code>[Retriever](#agrag.retrieval.retrievers.base.Retriever)</code>

Dense search over community reports, for direct thematic questions.

**Functions:**

- [**retrieve**](#agrag.retrieval.retrievers.community.CommunityRetriever.retrieve) – Run community-report search and return hydrated results.

**Attributes:**

- [**name**](#agrag.retrieval.retrievers.community.CommunityRetriever.name) –

####### `agrag.retrieval.retrievers.community.CommunityRetriever.name`

```python
name = 'community'
```

####### `agrag.retrieval.retrievers.community.CommunityRetriever.retrieve`

```python
retrieve(query:str, *, filters:SearchFilters | None = None, limit:int | None = None) -> list[SearchResult]
```

Run community-report search and return hydrated results.

**Parameters:**

- **query** (<code>[str](#str)</code>) – The natural-language query text.
- **filters** (<code>[SearchFilters](#agrag.retrieval.filters.SearchFilters) | None</code>) – Constraints applied to the search.
- **limit** (<code>[int](#int) | None</code>) – Maximum results. None uses settings.community_top_k.
  Zero or negative returns no results without searching.

##### `agrag.retrieval.retrievers.entity`

Entity retriever: dense vector search over entities.

**Classes:**

- [**EntityRetriever**](#agrag.retrieval.retrievers.entity.EntityRetriever) – Dense entity search via vector similarity.

###### `agrag.retrieval.retrievers.entity.EntityRetriever`

```python
EntityRetriever(*, graph_store:GraphStore, embedder:Embedder, vector_store:VectorStore | None = None, settings:RetrievalSettings | None = None, entity_labels:Sequence[str] | None = None) -> None
```

Bases: <code>[Retriever](#agrag.retrieval.retrievers.base.Retriever)</code>

Dense entity search via vector similarity.

Embeds the query, searches via the GraphStore-native or
VectorStore path, then resolves every hit through
`resolve_entity` so the caller can trust `item.id` is live.

The native path searches one vector index per entity label, so it
needs the labels ingestion provisioned indexes for: the label
filter when the caller sets one, otherwise `entity_labels`.

**Functions:**

- [**retrieve**](#agrag.retrieval.retrievers.entity.EntityRetriever.retrieve) – Run entity search and return hydrated results.

**Attributes:**

- [**name**](#agrag.retrieval.retrievers.entity.EntityRetriever.name) –

**Parameters:**

- **graph_store** (<code>[GraphStore](#agrag.graphdb.base.GraphStore)</code>) – Backs entity search when vector_store is
  absent.
- **embedder** (<code>[Embedder](#agrag.embedding.base.Embedder)</code>) – Produces query vectors.
- **vector_store** (<code>[VectorStore](#agrag.vectordb.base.VectorStore) | None</code>) – Optional VectorStore for hybrid search.
- **settings** (<code>[RetrievalSettings](#agrag.retrieval.settings.RetrievalSettings) | None</code>) – Retrieval configuration; defaults from
  environment.
- **entity_labels** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\] | None</code>) – The schema entity labels native search runs
  against. None uses settings.entity_labels.

####### `agrag.retrieval.retrievers.entity.EntityRetriever.name`

```python
name = 'entity'
```

####### `agrag.retrieval.retrievers.entity.EntityRetriever.retrieve`

```python
retrieve(query:str, *, filters:SearchFilters | None = None, limit:int | None = None) -> list[SearchResult]
```

Run entity search and return hydrated results.

**Parameters:**

- **query** (<code>[str](#str)</code>) – The natural-language query text.
- **filters** (<code>[SearchFilters](#agrag.retrieval.filters.SearchFilters) | None</code>) – Constraints applied to the search.
- **limit** (<code>[int](#int) | None</code>) – Maximum results. None uses settings.entity_top_k.
  Zero or negative returns no results without searching.

**Returns:**

- <code>[list](#list)\[[SearchResult](#agrag.common.data_models.search_result.SearchResult)\]</code> – Ranked SearchResults with resolved entity ids.

**Raises:**

- <code>[ValueError](#ValueError)</code> – Native search was selected and neither the
  filter nor the configuration names an entity label.

##### `agrag.retrieval.retrievers.text2cypher`

Text2Cypher retriever: generate Cypher from natural language.

**Classes:**

- [**Text2CypherRetriever**](#agrag.retrieval.retrievers.text2cypher.Text2CypherRetriever) – Let the agent ask structured questions via generated Cypher.

**Attributes:**

- [**logger**](#agrag.retrieval.retrievers.text2cypher.logger) –

###### `agrag.retrieval.retrievers.text2cypher.Text2CypherRetriever`

```python
Text2CypherRetriever(*, graph_store:GraphStore, settings:RetrievalSettings | None = None) -> None
```

Bases: <code>[Retriever](#agrag.retrieval.retrievers.base.Retriever)</code>

Let the agent ask structured questions via generated Cypher.

Calls a BAML function to generate a read-only Cypher query,
runs reject_write_cypher as a safety pre-filter, then bounds the
query with a row limit and a server-side transaction timeout
before EXPLAIN and execution. Rows that carry an entity id are
resolved through resolve_entity before becoming a SearchResult;
relationship and chunk rows are parsed directly. Scalar rows (for
example counts or property values) cannot become a SearchResult
and are logged instead of being silently dropped.

**Functions:**

- [**retrieve**](#agrag.retrieval.retrievers.text2cypher.Text2CypherRetriever.retrieve) – Generate and execute a Cypher query for the question.

**Attributes:**

- [**name**](#agrag.retrieval.retrievers.text2cypher.Text2CypherRetriever.name) –

**Parameters:**

- **graph_store** (<code>[GraphStore](#agrag.graphdb.base.GraphStore)</code>) – Where the generated query runs.
- **settings** (<code>[RetrievalSettings](#agrag.retrieval.settings.RetrievalSettings) | None</code>) – Retrieval configuration; defaults from
  environment.

####### `agrag.retrieval.retrievers.text2cypher.Text2CypherRetriever.name`

```python
name = 'text2cypher'
```

####### `agrag.retrieval.retrievers.text2cypher.Text2CypherRetriever.retrieve`

```python
retrieve(query:str, *, filters:SearchFilters | None = None, limit:int = 10) -> list[SearchResult]
```

Generate and execute a Cypher query for the question.

**Parameters:**

- **query** (<code>[str](#str)</code>) – The natural-language question.
- **filters** (<code>[SearchFilters](#agrag.retrieval.filters.SearchFilters) | None</code>) – Ignored; text2cypher applies its own filters.
- **limit** (<code>[int](#int)</code>) – Maximum results to return.

**Returns:**

- <code>[list](#list)\[[SearchResult](#agrag.common.data_models.search_result.SearchResult)\]</code> – SearchResults from the generated query: entity results
  resolved through `resolve_entity`; relation and chunk
  rows parsed directly. Rows with no entity, relation, or
  chunk item are logged and skipped.

###### `agrag.retrieval.retrievers.text2cypher.logger`

```python
logger = logging.getLogger(__name__)
```

#### `agrag.retrieval.search_engine`

Retrieval's public entry point, independent of Graph.

**Classes:**

- [**SearchEngine**](#agrag.retrieval.search_engine.SearchEngine) – Retrieval's public entry point, independent of Graph.

**Attributes:**

- [**logger**](#agrag.retrieval.search_engine.logger) –

##### `agrag.retrieval.search_engine.SearchEngine`

```python
SearchEngine(*, graph_store:GraphStore, embedder:Embedder, vector_store:VectorStore | None = None, settings:RetrievalSettings | None = None, entity_labels:Sequence[str] | None = None) -> None
```

Retrieval's public entry point, independent of Graph.

Fans a query out to every method a Recipe names, fuses the
results, and optionally reranks them. Constructed from its own
stores; does not depend on a Graph instance existing.

**Functions:**

- [**search**](#agrag.retrieval.search_engine.SearchEngine.search) – Run recipe's methods, fuse, expand, and optionally rerank.

**Parameters:**

- **graph_store** (<code>[GraphStore](#agrag.graphdb.base.GraphStore)</code>) – Always required; backs entity/chunk search
  when vector_store is absent, and always backs BFS.
- **embedder** (<code>[Embedder](#agrag.embedding.base.Embedder)</code>) – Produces query vectors for dense and hybrid
  search.
- **vector_store** (<code>[VectorStore](#agrag.vectordb.base.VectorStore) | None</code>) – Optional. When set, entity, chunk, and
  community search run hybrid_search there instead of
  GraphStore's native search. `Graph.open(vector_store=...)`
  provisions the collections and dual-writes every embedding
  this package ingests, so the two paths see the same data;
  pointing SearchEngine at a store no Graph writes to gets an
  empty result set, not an error.
- **settings** (<code>[RetrievalSettings](#agrag.retrieval.settings.RetrievalSettings) | None</code>) – Retrieval configuration; defaults from
  environment.
- **entity_labels** (<code>[Sequence](#collections.abc.Sequence)\[[str](#str)\] | None</code>) – The schema entity labels native entity
  search runs against, one vector index each, as
  provisioned by `Graph.open`. Pass
  `[entity.label for entity in schema.entities]`.
  None uses settings.entity_labels. Ignored when a
  vector_store is configured.

###### `agrag.retrieval.search_engine.SearchEngine.search`

```python
search(query:str, recipe:Recipe, *, filters:SearchFilters | None = None) -> list[SearchResult]
```

Run recipe's methods, fuse, expand, and optionally rerank.

Runs recipe.methods concurrently and fuses their output
first. When recipe.bfs is set, BFS runs as a second,
sequential step seeded from the fused entity results. BFS
results are fused into the same list a second time before
reranking.

**Parameters:**

- **query** (<code>[str](#str)</code>) – The natural-language query text.
- **recipe** (<code>[Recipe](#agrag.retrieval.recipes.Recipe)</code>) – Which methods to run, whether to expand via BFS
  afterward, and which reranker, if any, follows.
- **filters** (<code>[SearchFilters](#agrag.retrieval.filters.SearchFilters) | None</code>) – Constraints applied identically to every method.

**Returns:**

- <code>[list](#list)\[[SearchResult](#agrag.common.data_models.search_result.SearchResult)\]</code> – Up to recipe.limit results, ranked highest-relevance
- <code>[list](#list)\[[SearchResult](#agrag.common.data_models.search_result.SearchResult)\]</code> – first.

**Raises:**

- <code>[AllRetrievalMethodsFailedError](#agrag.retrieval.errors.AllRetrievalMethodsFailedError)</code> – Every method the recipe
  names failed. A method failing while others succeed
  is logged and its results are simply absent.
- <code>[UnknownRecipeMethodError](#agrag.retrieval.errors.UnknownRecipeMethodError)</code> – The recipe names one or more
  methods that are not in the retriever registry. A
  misspelled method name is a configuration error and
  is reported instead of silently returning no
  results.

##### `agrag.retrieval.search_engine.logger`

```python
logger = logging.getLogger(__name__)
```

#### `agrag.retrieval.settings`

Env-backed configuration for retrieval methods and fusion.

**Classes:**

- [**RetrievalSettings**](#agrag.retrieval.settings.RetrievalSettings) – Configuration for retrieval methods and fusion.

##### `agrag.retrieval.settings.RetrievalSettings`

Bases: <code>[BaseSettings](#pydantic_settings.BaseSettings)</code>

Configuration for retrieval methods and fusion.

**Attributes:**

- [**entity_collection**](#agrag.retrieval.settings.RetrievalSettings.entity_collection) (<code>[str](#str)</code>) – The VectorStore collection name for entity
  search. Only read when a VectorStore is configured on
  SearchEngine; ignored on the GraphStore-native path.
- [**chunk_collection**](#agrag.retrieval.settings.RetrievalSettings.chunk_collection) (<code>[str](#str)</code>) – The VectorStore collection name for chunk
  search. Same condition as entity_collection.
- [**entity_labels**](#agrag.retrieval.settings.RetrievalSettings.entity_labels) (<code>[list](#list)\[[str](#str)\]</code>) – The graph labels native entity search runs
  against, one vector index each. These are the schema's
  entity labels, never a VectorStore collection name. Only
  read when no VectorStore is configured and the caller
  passes no label filter.
- [**node_distance_seed_top_k**](#agrag.retrieval.settings.RetrievalSettings.node_distance_seed_top_k) (<code>[int](#int)</code>) – How many of the highest-ranked
  entity hits seed the node-distance reranker. Candidates
  are ordered by graph distance to those seeds.
- [**entity_top_k**](#agrag.retrieval.settings.RetrievalSettings.entity_top_k) (<code>[int](#int)</code>) – Results requested per entity search call.
- [**chunk_top_k**](#agrag.retrieval.settings.RetrievalSettings.chunk_top_k) (<code>[int](#int)</code>) – Results requested per chunk search call.
- [**hybrid_alpha**](#agrag.retrieval.settings.RetrievalSettings.hybrid_alpha) (<code>[float](#float)</code>) – Dense-versus-keyword blend for hybrid search,
  0 to 1. Only meaningful on the VectorStore path;
  GraphStore-native search is dense-only and ignores this.
- [**traversal_depth**](#agrag.retrieval.settings.RetrievalSettings.traversal_depth) (<code>[int](#int)</code>) – Maximum BFS hops from a seed entity.
- [**traversal_limit**](#agrag.retrieval.settings.RetrievalSettings.traversal_limit) (<code>[int](#int)</code>) – Maximum nodes a BFS expansion can return.
- [**rrf_k**](#agrag.retrieval.settings.RetrievalSettings.rrf_k) (<code>[int](#int)</code>) – The RRF constant controlling how much rank position
  matters.
- [**reranker_min_score**](#agrag.retrieval.settings.RetrievalSettings.reranker_min_score) (<code>[float](#float) | None</code>) – Results scoring below this after rerank
  are dropped. None disables the threshold.
- [**text2cypher_max_retries**](#agrag.retrieval.settings.RetrievalSettings.text2cypher_max_retries) (<code>[int](#int)</code>) – Maximum retry attempts for a
  text2cypher generation that produces invalid Cypher.
- [**text2cypher_timeout_seconds**](#agrag.retrieval.settings.RetrievalSettings.text2cypher_timeout_seconds) (<code>[float](#float) | None</code>) – Server-side transaction timeout
  applied to generated read queries. The database terminates
  a generated query that runs longer, so a pathological
  query cannot hold server resources indefinitely. None
  uses the server's default timeout.
- [**text2cypher_max_rows**](#agrag.retrieval.settings.RetrievalSettings.text2cypher_max_rows) (<code>[int](#int)</code>) – Maximum rows a generated read query may
  return. Appended as a LIMIT clause when the generated
  query declares none of its own.
- [**cross_encoder_model**](#agrag.retrieval.settings.RetrievalSettings.cross_encoder_model) (<code>[str](#str)</code>) – The sentence-transformers CrossEncoder model
  used for cross_encoder reranking. Env:
  RETRIEVAL_CROSS_ENCODER_MODEL.
- [**community_collection**](#agrag.retrieval.settings.RetrievalSettings.community_collection) (<code>[str](#str)</code>) – The VectorStore collection name for community
  search. Same condition as entity_collection/chunk_collection:
  only read when a VectorStore is configured.
- [**community_top_k**](#agrag.retrieval.settings.RetrievalSettings.community_top_k) (<code>[int](#int)</code>) – Results requested per community search call when
  the caller passes no explicit limit -- the same role
  entity_top_k/chunk_top_k play for their retrievers. Distinct
  from Recipe.community_top_k (enrichment-budget/reserved-slice
  size): same name, different class, different job.

Env prefix: `RETRIEVAL_`.

###### `agrag.retrieval.settings.RetrievalSettings.chunk_collection`

```python
chunk_collection: str = 'agrag_chunks'
```

###### `agrag.retrieval.settings.RetrievalSettings.chunk_top_k`

```python
chunk_top_k: int = 10
```

###### `agrag.retrieval.settings.RetrievalSettings.community_collection`

```python
community_collection: str = 'agrag_communities'
```

###### `agrag.retrieval.settings.RetrievalSettings.community_top_k`

```python
community_top_k: int = 5
```

###### `agrag.retrieval.settings.RetrievalSettings.cross_encoder_model`

```python
cross_encoder_model: str = 'cross-encoder/ms-marco-MiniLM-L-6-v2'
```

###### `agrag.retrieval.settings.RetrievalSettings.entity_collection`

```python
entity_collection: str = 'agrag_entities'
```

###### `agrag.retrieval.settings.RetrievalSettings.entity_labels`

```python
entity_labels: list[str] = []
```

###### `agrag.retrieval.settings.RetrievalSettings.entity_top_k`

```python
entity_top_k: int = 10
```

###### `agrag.retrieval.settings.RetrievalSettings.hybrid_alpha`

```python
hybrid_alpha: float = 0.5
```

###### `agrag.retrieval.settings.RetrievalSettings.model_config`

```python
model_config = SettingsConfigDict(env_prefix='RETRIEVAL_', env_file='.env', extra='ignore')
```

###### `agrag.retrieval.settings.RetrievalSettings.node_distance_seed_top_k`

```python
node_distance_seed_top_k: int = 3
```

###### `agrag.retrieval.settings.RetrievalSettings.reranker_min_score`

```python
reranker_min_score: float | None = None
```

###### `agrag.retrieval.settings.RetrievalSettings.rrf_k`

```python
rrf_k: int = 60
```

###### `agrag.retrieval.settings.RetrievalSettings.text2cypher_max_retries`

```python
text2cypher_max_retries: int = 3
```

###### `agrag.retrieval.settings.RetrievalSettings.text2cypher_max_rows`

```python
text2cypher_max_rows: int = 1000
```

###### `agrag.retrieval.settings.RetrievalSettings.text2cypher_timeout_seconds`

```python
text2cypher_timeout_seconds: float | None = 10.0
```

###### `agrag.retrieval.settings.RetrievalSettings.traversal_depth`

```python
traversal_depth: int = 2
```

###### `agrag.retrieval.settings.RetrievalSettings.traversal_limit`

```python
traversal_limit: int = 50
```

### `agrag.vectordb`

Vector storage backends and the build shortcut.

**Modules:**

- [**base**](#agrag.vectordb.base) – The VectorStore abstraction and its build shortcut.
- [**errors**](#agrag.vectordb.errors) – Errors that the vector-store layer raises.
- [**milvus**](#agrag.vectordb.milvus) – Milvus vector-store backend.
- [**qdrant**](#agrag.vectordb.qdrant) – Qdrant vector-store backend.
- [**settings**](#agrag.vectordb.settings) – Settings for vector-store backends.
- [**weaviate**](#agrag.vectordb.weaviate) – Weaviate vector-store backend.

**Classes:**

- [**CollectionDimensionMismatchError**](#agrag.vectordb.CollectionDimensionMismatchError) – A collection already exists with a different embedding dimension.
- [**MilvusSettings**](#agrag.vectordb.MilvusSettings) – Milvus connection configuration.
- [**MilvusVectorStore**](#agrag.vectordb.MilvusVectorStore) – A `VectorStore` backed by Milvus, including native hybrid search.
- [**QdrantSettings**](#agrag.vectordb.QdrantSettings) – Qdrant connection configuration.
- [**QdrantVectorStore**](#agrag.vectordb.QdrantVectorStore) – A `VectorStore` backed by Qdrant, including native hybrid search.
- [**VectorStore**](#agrag.vectordb.VectorStore) – A vector database backend: collection lifecycle, writes, and search.
- [**VectorStoreError**](#agrag.vectordb.VectorStoreError) – The base class for every vector-store error.
- [**VectorStoreMissingExtraError**](#agrag.vectordb.VectorStoreMissingExtraError) – A vector store exists, but its package extra is not installed.
- [**WeaviateSettings**](#agrag.vectordb.WeaviateSettings) – Weaviate connection configuration.
- [**WeaviateVectorStore**](#agrag.vectordb.WeaviateVectorStore) – A `VectorStore` backed by Weaviate, including native hybrid search.

**Functions:**

- [**build_vector_store**](#agrag.vectordb.build_vector_store) – Build a vector store from a backend name, or return one unchanged.

#### `agrag.vectordb.CollectionDimensionMismatchError`

```python
CollectionDimensionMismatchError(*, expected:int, actual:int) -> None
```

Bases: <code>[VectorStoreError](#agrag.vectordb.errors.VectorStoreError)</code>

A collection already exists with a different embedding dimension.

**Attributes:**

- [**expected**](#agrag.vectordb.CollectionDimensionMismatchError.expected) – The dimension the collection was created with.
- [**actual**](#agrag.vectordb.CollectionDimensionMismatchError.actual) – The dimension the caller requested.

##### `agrag.vectordb.CollectionDimensionMismatchError.actual`

```python
actual = actual
```

##### `agrag.vectordb.CollectionDimensionMismatchError.expected`

```python
expected = expected
```

#### `agrag.vectordb.MilvusSettings`

Bases: <code>[BaseSettings](#pydantic_settings.BaseSettings)</code>

Milvus connection configuration.

**Attributes:**

- [**uri**](#agrag.vectordb.MilvusSettings.uri) (<code>[str](#str)</code>) – The Milvus endpoint URI. Env: `MILVUS_URI`.
- [**token**](#agrag.vectordb.MilvusSettings.token) (<code>[str](#str)</code>) – The Milvus auth token. Empty string for an unauthenticated
  instance. Env: `MILVUS_TOKEN`.
- [**require_tls**](#agrag.vectordb.MilvusSettings.require_tls) (<code>[bool](#bool)</code>) – When `True`, reject a plaintext `uri` to a
  non-local host even with no `token` configured. Off by default
  since many deployments run an unauthenticated Milvus on a
  private network and rely on network segmentation rather than
  transport encryption. Env: `MILVUS_REQUIRE_TLS`.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `uri` is plaintext (`http`), points at a non-local
  host, and either `token` is set or `require_tls` is
  `True`. Use `https` for a remote Milvus instance.

##### `agrag.vectordb.MilvusSettings.model_config`

```python
model_config = SettingsConfigDict(env_prefix='MILVUS_', env_file='.env', extra='ignore')
```

##### `agrag.vectordb.MilvusSettings.require_tls`

```python
require_tls: bool = False
```

##### `agrag.vectordb.MilvusSettings.token`

```python
token: str = ''
```

##### `agrag.vectordb.MilvusSettings.uri`

```python
uri: str = 'http://localhost:19530'
```

#### `agrag.vectordb.MilvusVectorStore`

```python
MilvusVectorStore(*, settings:MilvusSettings | None = None, client:Any | None = None) -> None
```

Bases: <code>[VectorStore](#agrag.vectordb.base.VectorStore)</code>

A `VectorStore` backed by Milvus, including native hybrid search.

The client connects lazily on first use, so constructing the store does not
open a network connection. Milvus performs BM25 server-side, so hybrid
search needs no client-side sparse embedder; the sparse vector is computed
by a Milvus `Function` from the `text` field on write and at query time.

**Functions:**

- [**close**](#agrag.vectordb.MilvusVectorStore.close) – Release the backend connection.
- [**collection_exists**](#agrag.vectordb.MilvusVectorStore.collection_exists) – Report whether a collection exists.
- [**count**](#agrag.vectordb.MilvusVectorStore.count) – Count records in a collection.
- [**delete**](#agrag.vectordb.MilvusVectorStore.delete) – Delete records by id.
- [**delete_collection**](#agrag.vectordb.MilvusVectorStore.delete_collection) – Delete a collection and all its entities.
- [**ensure_collection**](#agrag.vectordb.MilvusVectorStore.ensure_collection) – Create the collection if it does not exist.
- [**hybrid_search**](#agrag.vectordb.MilvusVectorStore.hybrid_search) – Search by dense vector and keyword text in one fused call.
- [**initialize**](#agrag.vectordb.MilvusVectorStore.initialize) – Check connectivity and authentication.
- [**invalidate_collection**](#agrag.vectordb.MilvusVectorStore.invalidate_collection) – Drop cached distance-metric knowledge of a collection.
- [**retrieve**](#agrag.vectordb.MilvusVectorStore.retrieve) – Fetch records by id.
- [**scroll**](#agrag.vectordb.MilvusVectorStore.scroll) – Iterate records in a collection, in batches.
- [**search**](#agrag.vectordb.MilvusVectorStore.search) – Search by dense vector only.
- [**upsert**](#agrag.vectordb.MilvusVectorStore.upsert) – Write or overwrite records in a collection.

**Parameters:**

- **settings** (<code>[MilvusSettings](#agrag.vectordb.settings.MilvusSettings) | None</code>) – Milvus connection settings. Defaults to
  `MilvusSettings()`.
- **client** (<code>[Any](#typing.Any) | None</code>) – A pre-built `AsyncMilvusClient`, for tests. When set,
  `__init__` imports nothing and the store calls this object
  directly instead of building one.

##### `agrag.vectordb.MilvusVectorStore.close`

```python
close() -> None
```

Release the backend connection.

##### `agrag.vectordb.MilvusVectorStore.collection_exists`

```python
collection_exists(name:str) -> bool
```

Report whether a collection exists.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

**Returns:**

- <code>[bool](#bool)</code> – `True` if the collection exists.

##### `agrag.vectordb.MilvusVectorStore.count`

```python
count(collection:str, *, filters:dict[str, Any] | None = None) -> int
```

Count records in a collection.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to count.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on scalar fields.

**Returns:**

- <code>[int](#int)</code> – The number of matching records.

##### `agrag.vectordb.MilvusVectorStore.delete`

```python
delete(collection:str, ids:Sequence[UUID]) -> None
```

Delete records by id.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to delete from.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to delete.

##### `agrag.vectordb.MilvusVectorStore.delete_collection`

```python
delete_collection(name:str) -> None
```

Delete a collection and all its entities.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

##### `agrag.vectordb.MilvusVectorStore.ensure_collection`

```python
ensure_collection(name:str, *, dimensions:int, distance:Distance, hybrid:bool = False) -> None
```

Create the collection if it does not exist.

Milvus performs BM25 server-side, so the sparse field and its `Function`
are always provisioned; the `hybrid` flag is accepted for interface
parity but is a no-op here. An existing collection must already carry
this same fixed schema, since `upsert` and `hybrid_search` always
read and write every field regardless of `hybrid`.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.
- **dimensions** (<code>[int](#int)</code>) – The embedding dimension.
- **distance** (<code>[Distance](#agrag.common.data_models.vector_record.Distance)</code>) – The distance metric new collections use.
- **hybrid** (<code>[bool](#bool)</code>) – Accepted for interface parity; ignored by Milvus.

**Raises:**

- <code>[CollectionDimensionMismatchError](#agrag.vectordb.errors.CollectionDimensionMismatchError)</code> – The collection exists with a
  different dimension than `dimensions`.
- <code>[VectorStoreError](#agrag.vectordb.errors.VectorStoreError)</code> – The collection exists but is missing a field or
  index this adapter requires.

##### `agrag.vectordb.MilvusVectorStore.hybrid_search`

```python
hybrid_search(collection:str, query_vector:Sequence[float], query_text:str, *, limit:int = 10, filters:dict[str, Any] | None = None, alpha:float = 0.5) -> list[VectorHit]
```

Search by dense vector and keyword text in one fused call.

Fusion uses Milvus's native weighted reranker, which normalizes each
request's scores before applying `alpha`.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **query_text** (<code>[str](#str)</code>) – The query text, matched by BM25.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on scalar fields.
- **alpha** (<code>[float](#float)</code>) – The dense/keyword balance. `1.0` is pure dense, `0.0` is
  pure keyword.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The fused hits, highest score first.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`, or `alpha` is outside `[0.0, 1.0]`.

##### `agrag.vectordb.MilvusVectorStore.initialize`

```python
initialize() -> None
```

Check connectivity and authentication.

##### `agrag.vectordb.MilvusVectorStore.invalidate_collection`

```python
invalidate_collection(name:str) -> None
```

Drop cached distance-metric knowledge of a collection.

This store caches a collection's distance metric after the first
call that resolves it, on the assumption that it alone (via
`ensure_collection`/`delete_collection`) owns the collection's
lifecycle for as long as this instance is in use. If something
outside this instance deletes and recreates a collection under the
same name with a different metric, call this first so the next call
re-resolves that collection's metric from the backend instead of
trusting the stale cache.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

##### `agrag.vectordb.MilvusVectorStore.retrieve`

```python
retrieve(collection:str, ids:Sequence[UUID]) -> list[VectorRecord]
```

Fetch records by id.

Requests at most `MAX_RESPONSE_LIMIT` ids per call, so a large
`ids` list cannot exceed Milvus's response-size ceiling in one
request the way sending every id at once would.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to fetch.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The records that exist, in the requested order, omitting missing
- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – ids.

##### `agrag.vectordb.MilvusVectorStore.scroll`

```python
scroll(collection:str, *, limit:int = 100, page_offset:str | None = None, filters:dict[str, Any] | None = None, with_vectors:bool = False) -> tuple[list[VectorRecord], str | None]
```

Iterate records in a collection, in batches.

Milvus rejects a query whose `offset + limit` exceeds
`MAX_RESPONSE_LIMIT`, so a numeric offset cannot page past that
many total records. Pages instead cursor on the `id` primary key:
each page filters on `id > page_offset` and orders by `id`
ascending, which needs no offset at all and so never hits that
window regardless of collection size. The explicit order is load
bearing: without it, an unordered query result could omit rows at or
below the next cursor, permanently skipping them on the next page.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **limit** (<code>[int](#int)</code>) – The maximum number of records per page.
- **page_offset** (<code>[str](#str) | None</code>) – The id cursor from a previous `scroll` call.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on scalar fields.
- **with_vectors** (<code>[bool](#bool)</code>) – Whether to return each record's vector.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The page of records and the next page cursor, or `None` at the
- <code>[str](#str) | None</code> – end.

##### `agrag.vectordb.MilvusVectorStore.search`

```python
search(collection:str, query_vector:Sequence[float], *, limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search by dense vector only.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on scalar fields.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The matched hits, highest score first.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`.

##### `agrag.vectordb.MilvusVectorStore.upsert`

```python
upsert(collection:str, records:Sequence[VectorRecord], *, batch_size:int = 256) -> None
```

Write or overwrite records in a collection.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to write to.
- **records** (<code>[Sequence](#collections.abc.Sequence)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code>) – The records to upsert, in order.
- **batch_size** (<code>[int](#int)</code>) – The number of records per backend write call. Must be
  positive.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `batch_size` is not positive.

#### `agrag.vectordb.QdrantSettings`

Bases: <code>[BaseSettings](#pydantic_settings.BaseSettings)</code>

Qdrant connection configuration.

**Attributes:**

- [**url**](#agrag.vectordb.QdrantSettings.url) (<code>[str](#str)</code>) – The Qdrant endpoint URL. Env: `QDRANT_URL`.
- [**api_key**](#agrag.vectordb.QdrantSettings.api_key) (<code>[str](#str)</code>) – The Qdrant API key. Env: `QDRANT_API_KEY`.
- [**require_tls**](#agrag.vectordb.QdrantSettings.require_tls) (<code>[bool](#bool)</code>) – When `True`, reject a plaintext `url` to a non-local
  host even with no `api_key` configured. Off by default since
  many deployments run an unauthenticated Qdrant on a private
  network and rely on network segmentation rather than transport
  encryption. Env: `QDRANT_REQUIRE_TLS`.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `url` is plaintext (`http`), points at a non-local
  host, and either `api_key` is set or `require_tls` is
  `True`. Use `https` for a remote Qdrant instance.

##### `agrag.vectordb.QdrantSettings.api_key`

```python
api_key: str = ''
```

##### `agrag.vectordb.QdrantSettings.model_config`

```python
model_config = SettingsConfigDict(env_prefix='QDRANT_', env_file='.env', extra='ignore')
```

##### `agrag.vectordb.QdrantSettings.require_tls`

```python
require_tls: bool = False
```

##### `agrag.vectordb.QdrantSettings.url`

```python
url: str = 'http://localhost:6333'
```

#### `agrag.vectordb.QdrantVectorStore`

```python
QdrantVectorStore(*, settings:QdrantSettings | None = None, sparse_embedder:SparseEmbedder | None = None, client:Any | None = None, models:Any | None = None) -> None
```

Bases: <code>[VectorStore](#agrag.vectordb.base.VectorStore)</code>

A `VectorStore` backed by Qdrant, including native hybrid search.

The client connects lazily on first use, so constructing the store does not
open a network connection. Hybrid search builds its sparse query with a
`SparseEmbedder` that defaults to FastEmbed BM25 and loads only when a
hybrid call first runs, not at construction.

**Functions:**

- [**close**](#agrag.vectordb.QdrantVectorStore.close) – Release the backend connection.
- [**collection_exists**](#agrag.vectordb.QdrantVectorStore.collection_exists) – Report whether a collection exists.
- [**count**](#agrag.vectordb.QdrantVectorStore.count) – Count records in a collection.
- [**delete**](#agrag.vectordb.QdrantVectorStore.delete) – Delete records by id.
- [**delete_collection**](#agrag.vectordb.QdrantVectorStore.delete_collection) – Delete a collection and all its points.
- [**ensure_collection**](#agrag.vectordb.QdrantVectorStore.ensure_collection) – Create the collection if it does not exist.
- [**hybrid_search**](#agrag.vectordb.QdrantVectorStore.hybrid_search) – Search by dense vector and keyword text, fused by a weighted blend.
- [**initialize**](#agrag.vectordb.QdrantVectorStore.initialize) – Check connectivity and authentication.
- [**invalidate_collection**](#agrag.vectordb.QdrantVectorStore.invalidate_collection) – Drop cached hybrid-state and distance-metric knowledge of a collection.
- [**retrieve**](#agrag.vectordb.QdrantVectorStore.retrieve) – Fetch records by id.
- [**scroll**](#agrag.vectordb.QdrantVectorStore.scroll) – Iterate records in a collection, in batches.
- [**search**](#agrag.vectordb.QdrantVectorStore.search) – Search by dense vector only.
- [**upsert**](#agrag.vectordb.QdrantVectorStore.upsert) – Write or overwrite records in a collection.

**Parameters:**

- **settings** (<code>[QdrantSettings](#agrag.vectordb.settings.QdrantSettings) | None</code>) – Qdrant connection settings. Defaults to
  `QdrantSettings()`.
- **sparse_embedder** (<code>[SparseEmbedder](#agrag.embedding.sparse_base.SparseEmbedder) | None</code>) – The sparse embedder hybrid search uses. Defaults to
  a lazily-built `FastEmbedBM25Embedder`.
- **client** (<code>[Any](#typing.Any) | None</code>) – A pre-built `AsyncQdrantClient`, for tests. When set,
  `__init__` imports nothing and the store calls this object
  directly instead of building one.
- **models** (<code>[Any](#typing.Any) | None</code>) – The `qdrant_client.models` module, for tests. Pair with
  `client` so filter/payload helpers work without needing the
  real `qdrant_client` package installed at all.

##### `agrag.vectordb.QdrantVectorStore.close`

```python
close() -> None
```

Release the backend connection.

##### `agrag.vectordb.QdrantVectorStore.collection_exists`

```python
collection_exists(name:str) -> bool
```

Report whether a collection exists.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

**Returns:**

- <code>[bool](#bool)</code> – `True` if the collection exists.

##### `agrag.vectordb.QdrantVectorStore.count`

```python
count(collection:str, *, filters:dict[str, Any] | None = None) -> int
```

Count records in a collection.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to count.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.

**Returns:**

- <code>[int](#int)</code> – The number of matching records.

##### `agrag.vectordb.QdrantVectorStore.delete`

```python
delete(collection:str, ids:Sequence[UUID]) -> None
```

Delete records by id.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to delete from.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to delete.

##### `agrag.vectordb.QdrantVectorStore.delete_collection`

```python
delete_collection(name:str) -> None
```

Delete a collection and all its points.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

##### `agrag.vectordb.QdrantVectorStore.ensure_collection`

```python
ensure_collection(name:str, *, dimensions:int, distance:Distance, hybrid:bool = False) -> None
```

Create the collection if it does not exist.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.
- **dimensions** (<code>[int](#int)</code>) – The embedding dimension.
- **distance** (<code>[Distance](#agrag.common.data_models.vector_record.Distance)</code>) – The distance metric new collections use.
- **hybrid** (<code>[bool](#bool)</code>) – Whether to provision the named sparse vector hybrid search
  needs.

**Raises:**

- <code>[CollectionDimensionMismatchError](#agrag.vectordb.errors.CollectionDimensionMismatchError)</code> – The collection exists with a
  different dimension than `dimensions`.
- <code>[VectorStoreError](#agrag.vectordb.errors.VectorStoreError)</code> – The collection exists without hybrid search
  support and `hybrid=True` was requested.

##### `agrag.vectordb.QdrantVectorStore.hybrid_search`

```python
hybrid_search(collection:str, query_vector:Sequence[float], query_text:str, *, limit:int = 10, filters:dict[str, Any] | None = None, alpha:float = 0.5) -> list[VectorHit]
```

Search by dense vector and keyword text, fused by a weighted blend.

Qdrant's native fusion methods (RRF, DBSF) have no continuous
dense/keyword weight, so this runs the dense and sparse (BM25)
searches independently, min-max normalizes each result set's scores
to `[0, 1]`, then combines them per id as
`alpha * dense + (1 - alpha) * sparse`. Each side fetches a wider
candidate pool than `limit` so a document strong on only one signal
still has a chance to reach the blended top results.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **query_text** (<code>[str](#str)</code>) – The query text, matched by BM25.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.
- **alpha** (<code>[float](#float)</code>) – The dense/keyword balance. `1.0` is pure dense, `0.0` is
  pure keyword.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The blended hits, highest combined score first.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`, or `alpha` is outside `[0.0, 1.0]`.

##### `agrag.vectordb.QdrantVectorStore.initialize`

```python
initialize() -> None
```

Check connectivity and authentication.

##### `agrag.vectordb.QdrantVectorStore.invalidate_collection`

```python
invalidate_collection(name:str) -> None
```

Drop cached hybrid-state and distance-metric knowledge of a collection.

This store caches a collection's hybrid support and distance metric
after the first call that resolves them, on the assumption that it
alone (via `ensure_collection`/`delete_collection`) owns the
collection's lifecycle for as long as this instance is in use. If
something outside this instance deletes and recreates a collection
under the same name with different config, call this first so the
next call re-resolves that collection's state from the backend
instead of trusting the stale cache.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

##### `agrag.vectordb.QdrantVectorStore.retrieve`

```python
retrieve(collection:str, ids:Sequence[UUID]) -> list[VectorRecord]
```

Fetch records by id.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to fetch.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The records that exist, in the requested order, omitting missing
- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – ids.

##### `agrag.vectordb.QdrantVectorStore.scroll`

```python
scroll(collection:str, *, limit:int = 100, page_offset:str | None = None, filters:dict[str, Any] | None = None, with_vectors:bool = False) -> tuple[list[VectorRecord], str | None]
```

Iterate records in a collection, in batches.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **limit** (<code>[int](#int)</code>) – The maximum number of records per page.
- **page_offset** (<code>[str](#str) | None</code>) – The offset from a previous `scroll` call.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.
- **with_vectors** (<code>[bool](#bool)</code>) – Whether to return each record's vector.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The page of records and the next page offset, or `None` at the
- <code>[str](#str) | None</code> – end.

##### `agrag.vectordb.QdrantVectorStore.search`

```python
search(collection:str, query_vector:Sequence[float], *, limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search by dense vector only.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The matched hits, highest score first.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`.

##### `agrag.vectordb.QdrantVectorStore.upsert`

```python
upsert(collection:str, records:Sequence[VectorRecord], *, batch_size:int = 256) -> None
```

Write or overwrite records in a collection.

When `collection` has sparse-vector support (created or previously
seen with `ensure_collection(..., hybrid=True)`), each record's
`payload["text"]` is also sparse-embedded and stored under the named
sparse vector, so `hybrid_search`'s keyword arm has real vectors to
match. A record with no `text` payload key gets an empty sparse
vector and only ever surfaces through the dense side of a hybrid
search.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to write to.
- **records** (<code>[Sequence](#collections.abc.Sequence)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code>) – The records to upsert, in order.
- **batch_size** (<code>[int](#int)</code>) – The number of records per backend write call. Must be
  positive.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `batch_size` is not positive.

#### `agrag.vectordb.VectorStore`

Bases: <code>[ABC](#abc.ABC)</code>

A vector database backend: collection lifecycle, writes, and search.

**Functions:**

- [**close**](#agrag.vectordb.VectorStore.close) – Release the backend connection.
- [**collection_exists**](#agrag.vectordb.VectorStore.collection_exists) – Report whether a collection exists.
- [**count**](#agrag.vectordb.VectorStore.count) – Count records in a collection.
- [**delete**](#agrag.vectordb.VectorStore.delete) – Delete records by id.
- [**delete_collection**](#agrag.vectordb.VectorStore.delete_collection) – Delete a collection and all its points.
- [**ensure_collection**](#agrag.vectordb.VectorStore.ensure_collection) – Create the collection if it does not exist.
- [**hybrid_search**](#agrag.vectordb.VectorStore.hybrid_search) – Search by dense vector and keyword text in one fused call.
- [**initialize**](#agrag.vectordb.VectorStore.initialize) – Check connectivity and authentication.
- [**retrieve**](#agrag.vectordb.VectorStore.retrieve) – Fetch records by id.
- [**scroll**](#agrag.vectordb.VectorStore.scroll) – Iterate records in a collection, in batches.
- [**search**](#agrag.vectordb.VectorStore.search) – Search by dense vector only.
- [**upsert**](#agrag.vectordb.VectorStore.upsert) – Write or overwrite records in a collection.

##### `agrag.vectordb.VectorStore.close`

```python
close() -> None
```

Release the backend connection.

##### `agrag.vectordb.VectorStore.collection_exists`

```python
collection_exists(name:str) -> bool
```

Report whether a collection exists.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

**Returns:**

- <code>[bool](#bool)</code> – `True` if the collection exists.

##### `agrag.vectordb.VectorStore.count`

```python
count(collection:str, *, filters:dict[str, Any] | None = None) -> int
```

Count records in a collection.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to count.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter: a scalar value means exact match, a
  list value means any of, and all keys are AND-ed together.
  Keys must be valid identifiers (letters, digits, underscore,
  not starting with a digit) to stay portable: Milvus compiles
  them into a filter expression and Neo4j's `GraphStore`
  counterpart compiles them into Cypher, so both reject other
  characters, while Qdrant and Weaviate accept arbitrary payload
  keys.

**Returns:**

- <code>[int](#int)</code> – The number of matching records.

##### `agrag.vectordb.VectorStore.delete`

```python
delete(collection:str, ids:Sequence[UUID]) -> None
```

Delete records by id.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to delete from.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to delete.

##### `agrag.vectordb.VectorStore.delete_collection`

```python
delete_collection(name:str) -> None
```

Delete a collection and all its points.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

##### `agrag.vectordb.VectorStore.ensure_collection`

```python
ensure_collection(name:str, *, dimensions:int, distance:Distance, hybrid:bool = False) -> None
```

Create the collection if it does not exist.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.
- **dimensions** (<code>[int](#int)</code>) – The embedding dimension. If the collection already
  exists with a different dimension, this raises.
- **distance** (<code>[Distance](#agrag.common.data_models.vector_record.Distance)</code>) – The distance metric new collections use.
- **hybrid** (<code>[bool](#bool)</code>) – Whether to additionally provision the sparse-vector
  configuration hybrid search needs. Ignored by backends that
  need no such provisioning.

**Raises:**

- <code>[CollectionDimensionMismatchError](#agrag.vectordb.errors.CollectionDimensionMismatchError)</code> – The collection exists with a
  different dimension than `dimensions`.

##### `agrag.vectordb.VectorStore.hybrid_search`

```python
hybrid_search(collection:str, query_vector:Sequence[float], query_text:str, *, limit:int = 10, filters:dict[str, Any] | None = None, alpha:float = 0.5) -> list[VectorHit]
```

Search by dense vector and keyword text in one fused call.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search. Must have been created with
  `ensure_collection(..., hybrid=True)`.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **query_text** (<code>[str](#str)</code>) – The query text, matched by keyword/BM25.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter: a scalar value means exact match, a
  list value means any of, and all keys are AND-ed together.
  Keys must be valid identifiers (letters, digits, underscore,
  not starting with a digit) to stay portable: Milvus compiles
  them into a filter expression and Neo4j's `GraphStore`
  counterpart compiles them into Cypher, so both reject other
  characters, while Qdrant and Weaviate accept arbitrary payload
  keys.
- **alpha** (<code>[float](#float)</code>) – The dense/keyword balance. `1.0` is pure dense, `0.0` is
  pure keyword. Weaviate and Milvus apply this weight natively.
  Qdrant's native fusion (Reciprocal Rank Fusion) has no
  continuous weight, so it applies `alpha` by blending two
  independently-scored, min-max normalized result sets instead
  of a single native fused call.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The fused hits, highest score first.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `limit` is not positive, or exceeds
  `agrag.common.validation.MAX_SEARCH_LIMIT`, or `alpha` is
  outside `[0.0, 1.0]`. Enforced uniformly across backends
  since they otherwise fail differently outside that range.

##### `agrag.vectordb.VectorStore.initialize`

```python
initialize() -> None
```

Check connectivity and authentication.

**Raises:**

- <code>[VectorStoreError](#agrag.vectordb.errors.VectorStoreError)</code> – The backend is unreachable, or the credentials
  are rejected.

##### `agrag.vectordb.VectorStore.retrieve`

```python
retrieve(collection:str, ids:Sequence[UUID]) -> list[VectorRecord]
```

Fetch records by id.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to fetch.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The records that exist, in the requested order, omitting missing
- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – ids.

##### `agrag.vectordb.VectorStore.scroll`

```python
scroll(collection:str, *, limit:int = 100, page_offset:str | None = None, filters:dict[str, Any] | None = None, with_vectors:bool = False) -> tuple[list[VectorRecord], str | None]
```

Iterate records in a collection, in batches.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **limit** (<code>[int](#int)</code>) – The maximum number of records per page.
- **page_offset** (<code>[str](#str) | None</code>) – The offset from a previous `scroll` call, or
  `None` to start at the beginning.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter: a scalar value means exact match, a
  list value means any of, and all keys are AND-ed together.
  Keys must be valid identifiers (letters, digits, underscore,
  not starting with a digit) to stay portable: Milvus compiles
  them into a filter expression and Neo4j's `GraphStore`
  counterpart compiles them into Cypher, so both reject other
  characters, while Qdrant and Weaviate accept arbitrary payload
  keys.
- **with_vectors** (<code>[bool](#bool)</code>) – Whether to return each record's vector.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The page of records and the next page offset, or `None` at the
- <code>[str](#str) | None</code> – end.

##### `agrag.vectordb.VectorStore.search`

```python
search(collection:str, query_vector:Sequence[float], *, limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search by dense vector only.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter: a scalar value means exact match, a
  list value means any of, and all keys are AND-ed together.
  Keys must be valid identifiers (letters, digits, underscore,
  not starting with a digit) to stay portable: Milvus compiles
  them into a filter expression and Neo4j's `GraphStore`
  counterpart compiles them into Cypher, so both reject other
  characters, while Qdrant and Weaviate accept arbitrary payload
  keys.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The matched hits, highest score first.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `limit` is not positive, or exceeds
  `agrag.common.validation.MAX_SEARCH_LIMIT`. Enforced
  uniformly across backends since they otherwise fail
  differently outside that range.

##### `agrag.vectordb.VectorStore.upsert`

```python
upsert(collection:str, records:Sequence[VectorRecord], *, batch_size:int = 256) -> None
```

Write or overwrite records in a collection.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to write to.
- **records** (<code>[Sequence](#collections.abc.Sequence)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code>) – The records to upsert, in order.
- **batch_size** (<code>[int](#int)</code>) – The number of records per backend write call. Must be
  positive.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `batch_size` is not positive.

#### `agrag.vectordb.VectorStoreError`

Bases: <code>[Exception](#Exception)</code>

The base class for every vector-store error.

#### `agrag.vectordb.VectorStoreMissingExtraError`

```python
VectorStoreMissingExtraError(extra:str) -> None
```

Bases: <code>[VectorStoreError](#agrag.vectordb.errors.VectorStoreError)</code>

A vector store exists, but its package extra is not installed.

**Attributes:**

- [**extra**](#agrag.vectordb.VectorStoreMissingExtraError.extra) – The name of the package extra to install.

##### `agrag.vectordb.VectorStoreMissingExtraError.extra`

```python
extra = extra
```

#### `agrag.vectordb.WeaviateSettings`

Bases: <code>[BaseSettings](#pydantic_settings.BaseSettings)</code>

Weaviate connection configuration.

**Attributes:**

- [**mode**](#agrag.vectordb.WeaviateSettings.mode) (<code>[Literal](#typing.Literal)['cloud', 'custom']</code>) – `"cloud"` connects to Weaviate Cloud. `"custom"` connects to
  a self-hosted instance (used by integration tests against the local
  Docker Compose instance) — an explicit field, not inferred from the
  URL, since inference caused real connection bugs in surveyed
  reference implementations. Env: `WEAVIATE_MODE`.
- [**url**](#agrag.vectordb.WeaviateSettings.url) (<code>[str](#str)</code>) – The Weaviate endpoint URL. For `"cloud"`, the cluster URL. For
  `"custom"`, the full host URL. Env: `WEAVIATE_URL`.
- [**api_key**](#agrag.vectordb.WeaviateSettings.api_key) (<code>[str](#str)</code>) – The Weaviate API key. Env: `WEAVIATE_API_KEY`.
- [**grpc_port**](#agrag.vectordb.WeaviateSettings.grpc_port) (<code>[int](#int)</code>) – The gRPC port, used by `"custom"` mode only (`"cloud"`
  mode infers it). Env: `WEAVIATE_GRPC_PORT`.
- [**require_tls**](#agrag.vectordb.WeaviateSettings.require_tls) (<code>[bool](#bool)</code>) – When `True`, reject a plaintext `url` to a non-local
  host even with no `api_key` configured. Off by default since
  many deployments run an unauthenticated Weaviate on a private
  network and rely on network segmentation rather than transport
  encryption. Env: `WEAVIATE_REQUIRE_TLS`.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `url` is plaintext (`http`), points at a non-local
  host, and either `api_key` is set or `require_tls` is
  `True`. Use `https` for a remote Weaviate instance.

##### `agrag.vectordb.WeaviateSettings.api_key`

```python
api_key: str = ''
```

##### `agrag.vectordb.WeaviateSettings.grpc_port`

```python
grpc_port: int = 50051
```

##### `agrag.vectordb.WeaviateSettings.mode`

```python
mode: Literal['cloud', 'custom'] = 'custom'
```

##### `agrag.vectordb.WeaviateSettings.model_config`

```python
model_config = SettingsConfigDict(env_prefix='WEAVIATE_', env_file='.env', extra='ignore')
```

##### `agrag.vectordb.WeaviateSettings.require_tls`

```python
require_tls: bool = False
```

##### `agrag.vectordb.WeaviateSettings.url`

```python
url: str = 'http://localhost:8080'
```

#### `agrag.vectordb.WeaviateVectorStore`

```python
WeaviateVectorStore(*, settings:WeaviateSettings | None = None, client:Any | None = None) -> None
```

Bases: <code>[VectorStore](#agrag.vectordb.base.VectorStore)</code>

A `VectorStore` backed by Weaviate, including native hybrid search.

The client connects lazily on first use, so constructing the store does not
open a network connection. Weaviate does its own server-side BM25, so
hybrid search needs no client-side sparse embedder.

**Functions:**

- [**close**](#agrag.vectordb.WeaviateVectorStore.close) – Release the backend connection.
- [**collection_exists**](#agrag.vectordb.WeaviateVectorStore.collection_exists) – Report whether a collection exists.
- [**count**](#agrag.vectordb.WeaviateVectorStore.count) – Count records in a collection.
- [**delete**](#agrag.vectordb.WeaviateVectorStore.delete) – Delete records by id.
- [**delete_collection**](#agrag.vectordb.WeaviateVectorStore.delete_collection) – Delete a collection and all its objects.
- [**ensure_collection**](#agrag.vectordb.WeaviateVectorStore.ensure_collection) – Create the collection if it does not exist.
- [**hybrid_search**](#agrag.vectordb.WeaviateVectorStore.hybrid_search) – Search by dense vector and keyword text in one fused call.
- [**initialize**](#agrag.vectordb.WeaviateVectorStore.initialize) – Open the connection and check authentication.
- [**retrieve**](#agrag.vectordb.WeaviateVectorStore.retrieve) – Fetch records by id.
- [**scroll**](#agrag.vectordb.WeaviateVectorStore.scroll) – Iterate records in a collection, in batches.
- [**search**](#agrag.vectordb.WeaviateVectorStore.search) – Search by dense vector only.
- [**upsert**](#agrag.vectordb.WeaviateVectorStore.upsert) – Write or overwrite records in a collection.

**Parameters:**

- **settings** (<code>[WeaviateSettings](#agrag.vectordb.settings.WeaviateSettings) | None</code>) – Weaviate connection settings. Defaults to
  `WeaviateSettings()`.
- **client** (<code>[Any](#typing.Any) | None</code>) – A pre-built Weaviate async client, for tests. When set,
  `__init__` imports nothing and the store calls this object
  directly instead of building one.

##### `agrag.vectordb.WeaviateVectorStore.close`

```python
close() -> None
```

Release the backend connection.

##### `agrag.vectordb.WeaviateVectorStore.collection_exists`

```python
collection_exists(name:str) -> bool
```

Report whether a collection exists.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

**Returns:**

- <code>[bool](#bool)</code> – `True` if the collection exists.

##### `agrag.vectordb.WeaviateVectorStore.count`

```python
count(collection:str, *, filters:dict[str, Any] | None = None) -> int
```

Count records in a collection.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to count.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.

**Returns:**

- <code>[int](#int)</code> – The number of matching records.

##### `agrag.vectordb.WeaviateVectorStore.delete`

```python
delete(collection:str, ids:Sequence[UUID]) -> None
```

Delete records by id.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to delete from.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to delete.

##### `agrag.vectordb.WeaviateVectorStore.delete_collection`

```python
delete_collection(name:str) -> None
```

Delete a collection and all its objects.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

##### `agrag.vectordb.WeaviateVectorStore.ensure_collection`

```python
ensure_collection(name:str, *, dimensions:int, distance:Distance, hybrid:bool = False) -> None
```

Create the collection if it does not exist.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.
- **dimensions** (<code>[int](#int)</code>) – The embedding dimension.
- **distance** (<code>[Distance](#agrag.common.data_models.vector_record.Distance)</code>) – The distance metric new collections use.
- **hybrid** (<code>[bool](#bool)</code>) – No-op for Weaviate, which needs no sparse provisioning.

**Raises:**

- <code>[CollectionDimensionMismatchError](#agrag.vectordb.errors.CollectionDimensionMismatchError)</code> – An existing object in the
  collection carries a vector of a different dimension. Weaviate
  keeps no schema-level dimension for self-provided vectors, so
  an existing collection with no vector-bearing object cannot be
  checked this way.

##### `agrag.vectordb.WeaviateVectorStore.hybrid_search`

```python
hybrid_search(collection:str, query_vector:Sequence[float], query_text:str, *, limit:int = 10, filters:dict[str, Any] | None = None, alpha:float = 0.5) -> list[VectorHit]
```

Search by dense vector and keyword text in one fused call.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **query_text** (<code>[str](#str)</code>) – The query text, matched by keyword/BM25.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.
- **alpha** (<code>[float](#float)</code>) – The dense/keyword balance. `1.0` is pure dense, `0.0` is
  pure keyword.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The fused hits, highest score first.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`, or `alpha` is outside `[0.0, 1.0]`.

##### `agrag.vectordb.WeaviateVectorStore.initialize`

```python
initialize() -> None
```

Open the connection and check authentication.

##### `agrag.vectordb.WeaviateVectorStore.retrieve`

```python
retrieve(collection:str, ids:Sequence[UUID]) -> list[VectorRecord]
```

Fetch records by id.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to fetch.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The records that exist, in the requested order, omitting missing
- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – ids.

##### `agrag.vectordb.WeaviateVectorStore.scroll`

```python
scroll(collection:str, *, limit:int = 100, page_offset:str | None = None, filters:dict[str, Any] | None = None, with_vectors:bool = False) -> tuple[list[VectorRecord], str | None]
```

Iterate records in a collection, in batches.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **limit** (<code>[int](#int)</code>) – The maximum number of records per page.
- **page_offset** (<code>[str](#str) | None</code>) – The cursor id from a previous `scroll` call.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.
- **with_vectors** (<code>[bool](#bool)</code>) – Whether to return each record's vector.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The page of records and the next page cursor, or `None` at the
- <code>[str](#str) | None</code> – end.

##### `agrag.vectordb.WeaviateVectorStore.search`

```python
search(collection:str, query_vector:Sequence[float], *, limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search by dense vector only.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The matched hits, highest score first.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`.

##### `agrag.vectordb.WeaviateVectorStore.upsert`

```python
upsert(collection:str, records:Sequence[VectorRecord], *, batch_size:int = 256) -> None
```

Write or overwrite records in a collection.

Uses Weaviate's batch import, which replaces an existing object
sharing a written id instead of rejecting it, giving real
insert-or-replace semantics and per-call batching in one request.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to write to.
- **records** (<code>[Sequence](#collections.abc.Sequence)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code>) – The records to upsert, in order.
- **batch_size** (<code>[int](#int)</code>) – The number of records per backend write call. Must be
  positive.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `batch_size` is not positive.
- <code>[VectorStoreError](#agrag.vectordb.errors.VectorStoreError)</code> – At least one record in a batch failed to write.

#### `agrag.vectordb.base`

The VectorStore abstraction and its build shortcut.

**Classes:**

- [**VectorStore**](#agrag.vectordb.base.VectorStore) – A vector database backend: collection lifecycle, writes, and search.

##### `agrag.vectordb.base.VectorStore`

Bases: <code>[ABC](#abc.ABC)</code>

A vector database backend: collection lifecycle, writes, and search.

**Functions:**

- [**close**](#agrag.vectordb.base.VectorStore.close) – Release the backend connection.
- [**collection_exists**](#agrag.vectordb.base.VectorStore.collection_exists) – Report whether a collection exists.
- [**count**](#agrag.vectordb.base.VectorStore.count) – Count records in a collection.
- [**delete**](#agrag.vectordb.base.VectorStore.delete) – Delete records by id.
- [**delete_collection**](#agrag.vectordb.base.VectorStore.delete_collection) – Delete a collection and all its points.
- [**ensure_collection**](#agrag.vectordb.base.VectorStore.ensure_collection) – Create the collection if it does not exist.
- [**hybrid_search**](#agrag.vectordb.base.VectorStore.hybrid_search) – Search by dense vector and keyword text in one fused call.
- [**initialize**](#agrag.vectordb.base.VectorStore.initialize) – Check connectivity and authentication.
- [**retrieve**](#agrag.vectordb.base.VectorStore.retrieve) – Fetch records by id.
- [**scroll**](#agrag.vectordb.base.VectorStore.scroll) – Iterate records in a collection, in batches.
- [**search**](#agrag.vectordb.base.VectorStore.search) – Search by dense vector only.
- [**upsert**](#agrag.vectordb.base.VectorStore.upsert) – Write or overwrite records in a collection.

###### `agrag.vectordb.base.VectorStore.close`

```python
close() -> None
```

Release the backend connection.

###### `agrag.vectordb.base.VectorStore.collection_exists`

```python
collection_exists(name:str) -> bool
```

Report whether a collection exists.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

**Returns:**

- <code>[bool](#bool)</code> – `True` if the collection exists.

###### `agrag.vectordb.base.VectorStore.count`

```python
count(collection:str, *, filters:dict[str, Any] | None = None) -> int
```

Count records in a collection.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to count.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter: a scalar value means exact match, a
  list value means any of, and all keys are AND-ed together.
  Keys must be valid identifiers (letters, digits, underscore,
  not starting with a digit) to stay portable: Milvus compiles
  them into a filter expression and Neo4j's `GraphStore`
  counterpart compiles them into Cypher, so both reject other
  characters, while Qdrant and Weaviate accept arbitrary payload
  keys.

**Returns:**

- <code>[int](#int)</code> – The number of matching records.

###### `agrag.vectordb.base.VectorStore.delete`

```python
delete(collection:str, ids:Sequence[UUID]) -> None
```

Delete records by id.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to delete from.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to delete.

###### `agrag.vectordb.base.VectorStore.delete_collection`

```python
delete_collection(name:str) -> None
```

Delete a collection and all its points.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

###### `agrag.vectordb.base.VectorStore.ensure_collection`

```python
ensure_collection(name:str, *, dimensions:int, distance:Distance, hybrid:bool = False) -> None
```

Create the collection if it does not exist.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.
- **dimensions** (<code>[int](#int)</code>) – The embedding dimension. If the collection already
  exists with a different dimension, this raises.
- **distance** (<code>[Distance](#agrag.common.data_models.vector_record.Distance)</code>) – The distance metric new collections use.
- **hybrid** (<code>[bool](#bool)</code>) – Whether to additionally provision the sparse-vector
  configuration hybrid search needs. Ignored by backends that
  need no such provisioning.

**Raises:**

- <code>[CollectionDimensionMismatchError](#agrag.vectordb.errors.CollectionDimensionMismatchError)</code> – The collection exists with a
  different dimension than `dimensions`.

###### `agrag.vectordb.base.VectorStore.hybrid_search`

```python
hybrid_search(collection:str, query_vector:Sequence[float], query_text:str, *, limit:int = 10, filters:dict[str, Any] | None = None, alpha:float = 0.5) -> list[VectorHit]
```

Search by dense vector and keyword text in one fused call.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search. Must have been created with
  `ensure_collection(..., hybrid=True)`.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **query_text** (<code>[str](#str)</code>) – The query text, matched by keyword/BM25.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter: a scalar value means exact match, a
  list value means any of, and all keys are AND-ed together.
  Keys must be valid identifiers (letters, digits, underscore,
  not starting with a digit) to stay portable: Milvus compiles
  them into a filter expression and Neo4j's `GraphStore`
  counterpart compiles them into Cypher, so both reject other
  characters, while Qdrant and Weaviate accept arbitrary payload
  keys.
- **alpha** (<code>[float](#float)</code>) – The dense/keyword balance. `1.0` is pure dense, `0.0` is
  pure keyword. Weaviate and Milvus apply this weight natively.
  Qdrant's native fusion (Reciprocal Rank Fusion) has no
  continuous weight, so it applies `alpha` by blending two
  independently-scored, min-max normalized result sets instead
  of a single native fused call.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The fused hits, highest score first.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `limit` is not positive, or exceeds
  `agrag.common.validation.MAX_SEARCH_LIMIT`, or `alpha` is
  outside `[0.0, 1.0]`. Enforced uniformly across backends
  since they otherwise fail differently outside that range.

###### `agrag.vectordb.base.VectorStore.initialize`

```python
initialize() -> None
```

Check connectivity and authentication.

**Raises:**

- <code>[VectorStoreError](#agrag.vectordb.errors.VectorStoreError)</code> – The backend is unreachable, or the credentials
  are rejected.

###### `agrag.vectordb.base.VectorStore.retrieve`

```python
retrieve(collection:str, ids:Sequence[UUID]) -> list[VectorRecord]
```

Fetch records by id.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to fetch.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The records that exist, in the requested order, omitting missing
- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – ids.

###### `agrag.vectordb.base.VectorStore.scroll`

```python
scroll(collection:str, *, limit:int = 100, page_offset:str | None = None, filters:dict[str, Any] | None = None, with_vectors:bool = False) -> tuple[list[VectorRecord], str | None]
```

Iterate records in a collection, in batches.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **limit** (<code>[int](#int)</code>) – The maximum number of records per page.
- **page_offset** (<code>[str](#str) | None</code>) – The offset from a previous `scroll` call, or
  `None` to start at the beginning.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter: a scalar value means exact match, a
  list value means any of, and all keys are AND-ed together.
  Keys must be valid identifiers (letters, digits, underscore,
  not starting with a digit) to stay portable: Milvus compiles
  them into a filter expression and Neo4j's `GraphStore`
  counterpart compiles them into Cypher, so both reject other
  characters, while Qdrant and Weaviate accept arbitrary payload
  keys.
- **with_vectors** (<code>[bool](#bool)</code>) – Whether to return each record's vector.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The page of records and the next page offset, or `None` at the
- <code>[str](#str) | None</code> – end.

###### `agrag.vectordb.base.VectorStore.search`

```python
search(collection:str, query_vector:Sequence[float], *, limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search by dense vector only.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter: a scalar value means exact match, a
  list value means any of, and all keys are AND-ed together.
  Keys must be valid identifiers (letters, digits, underscore,
  not starting with a digit) to stay portable: Milvus compiles
  them into a filter expression and Neo4j's `GraphStore`
  counterpart compiles them into Cypher, so both reject other
  characters, while Qdrant and Weaviate accept arbitrary payload
  keys.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The matched hits, highest score first.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `limit` is not positive, or exceeds
  `agrag.common.validation.MAX_SEARCH_LIMIT`. Enforced
  uniformly across backends since they otherwise fail
  differently outside that range.

###### `agrag.vectordb.base.VectorStore.upsert`

```python
upsert(collection:str, records:Sequence[VectorRecord], *, batch_size:int = 256) -> None
```

Write or overwrite records in a collection.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to write to.
- **records** (<code>[Sequence](#collections.abc.Sequence)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code>) – The records to upsert, in order.
- **batch_size** (<code>[int](#int)</code>) – The number of records per backend write call. Must be
  positive.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `batch_size` is not positive.

#### `agrag.vectordb.build_vector_store`

```python
build_vector_store(value:VectorStoreName | VectorStore) -> VectorStore
```

Build a vector store from a backend name, or return one unchanged.

**Parameters:**

- **value** (<code>[VectorStoreName](#agrag.vectordb.VectorStoreName) | [VectorStore](#agrag.vectordb.base.VectorStore)</code>) – `"qdrant"` or `"weaviate"`, or an already-constructed
  `VectorStore` for full control over settings.

**Returns:**

- <code>[VectorStore](#agrag.vectordb.base.VectorStore)</code> – A ready-to-use vector store.

#### `agrag.vectordb.errors`

Errors that the vector-store layer raises.

**Classes:**

- [**CollectionDimensionMismatchError**](#agrag.vectordb.errors.CollectionDimensionMismatchError) – A collection already exists with a different embedding dimension.
- [**VectorStoreError**](#agrag.vectordb.errors.VectorStoreError) – The base class for every vector-store error.
- [**VectorStoreMissingExtraError**](#agrag.vectordb.errors.VectorStoreMissingExtraError) – A vector store exists, but its package extra is not installed.

##### `agrag.vectordb.errors.CollectionDimensionMismatchError`

```python
CollectionDimensionMismatchError(*, expected:int, actual:int) -> None
```

Bases: <code>[VectorStoreError](#agrag.vectordb.errors.VectorStoreError)</code>

A collection already exists with a different embedding dimension.

**Attributes:**

- [**expected**](#agrag.vectordb.errors.CollectionDimensionMismatchError.expected) – The dimension the collection was created with.
- [**actual**](#agrag.vectordb.errors.CollectionDimensionMismatchError.actual) – The dimension the caller requested.

###### `agrag.vectordb.errors.CollectionDimensionMismatchError.actual`

```python
actual = actual
```

###### `agrag.vectordb.errors.CollectionDimensionMismatchError.expected`

```python
expected = expected
```

##### `agrag.vectordb.errors.VectorStoreError`

Bases: <code>[Exception](#Exception)</code>

The base class for every vector-store error.

##### `agrag.vectordb.errors.VectorStoreMissingExtraError`

```python
VectorStoreMissingExtraError(extra:str) -> None
```

Bases: <code>[VectorStoreError](#agrag.vectordb.errors.VectorStoreError)</code>

A vector store exists, but its package extra is not installed.

**Attributes:**

- [**extra**](#agrag.vectordb.errors.VectorStoreMissingExtraError.extra) – The name of the package extra to install.

###### `agrag.vectordb.errors.VectorStoreMissingExtraError.extra`

```python
extra = extra
```

#### `agrag.vectordb.milvus`

Milvus vector-store backend.

**Classes:**

- [**MilvusVectorStore**](#agrag.vectordb.milvus.MilvusVectorStore) – A `VectorStore` backed by Milvus, including native hybrid search.

**Attributes:**

- [**MAX_RESPONSE_LIMIT**](#agrag.vectordb.milvus.MAX_RESPONSE_LIMIT) –

##### `agrag.vectordb.milvus.MAX_RESPONSE_LIMIT`

```python
MAX_RESPONSE_LIMIT = 16384
```

##### `agrag.vectordb.milvus.MilvusVectorStore`

```python
MilvusVectorStore(*, settings:MilvusSettings | None = None, client:Any | None = None) -> None
```

Bases: <code>[VectorStore](#agrag.vectordb.base.VectorStore)</code>

A `VectorStore` backed by Milvus, including native hybrid search.

The client connects lazily on first use, so constructing the store does not
open a network connection. Milvus performs BM25 server-side, so hybrid
search needs no client-side sparse embedder; the sparse vector is computed
by a Milvus `Function` from the `text` field on write and at query time.

**Functions:**

- [**close**](#agrag.vectordb.milvus.MilvusVectorStore.close) – Release the backend connection.
- [**collection_exists**](#agrag.vectordb.milvus.MilvusVectorStore.collection_exists) – Report whether a collection exists.
- [**count**](#agrag.vectordb.milvus.MilvusVectorStore.count) – Count records in a collection.
- [**delete**](#agrag.vectordb.milvus.MilvusVectorStore.delete) – Delete records by id.
- [**delete_collection**](#agrag.vectordb.milvus.MilvusVectorStore.delete_collection) – Delete a collection and all its entities.
- [**ensure_collection**](#agrag.vectordb.milvus.MilvusVectorStore.ensure_collection) – Create the collection if it does not exist.
- [**hybrid_search**](#agrag.vectordb.milvus.MilvusVectorStore.hybrid_search) – Search by dense vector and keyword text in one fused call.
- [**initialize**](#agrag.vectordb.milvus.MilvusVectorStore.initialize) – Check connectivity and authentication.
- [**invalidate_collection**](#agrag.vectordb.milvus.MilvusVectorStore.invalidate_collection) – Drop cached distance-metric knowledge of a collection.
- [**retrieve**](#agrag.vectordb.milvus.MilvusVectorStore.retrieve) – Fetch records by id.
- [**scroll**](#agrag.vectordb.milvus.MilvusVectorStore.scroll) – Iterate records in a collection, in batches.
- [**search**](#agrag.vectordb.milvus.MilvusVectorStore.search) – Search by dense vector only.
- [**upsert**](#agrag.vectordb.milvus.MilvusVectorStore.upsert) – Write or overwrite records in a collection.

**Parameters:**

- **settings** (<code>[MilvusSettings](#agrag.vectordb.settings.MilvusSettings) | None</code>) – Milvus connection settings. Defaults to
  `MilvusSettings()`.
- **client** (<code>[Any](#typing.Any) | None</code>) – A pre-built `AsyncMilvusClient`, for tests. When set,
  `__init__` imports nothing and the store calls this object
  directly instead of building one.

###### `agrag.vectordb.milvus.MilvusVectorStore.close`

```python
close() -> None
```

Release the backend connection.

###### `agrag.vectordb.milvus.MilvusVectorStore.collection_exists`

```python
collection_exists(name:str) -> bool
```

Report whether a collection exists.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

**Returns:**

- <code>[bool](#bool)</code> – `True` if the collection exists.

###### `agrag.vectordb.milvus.MilvusVectorStore.count`

```python
count(collection:str, *, filters:dict[str, Any] | None = None) -> int
```

Count records in a collection.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to count.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on scalar fields.

**Returns:**

- <code>[int](#int)</code> – The number of matching records.

###### `agrag.vectordb.milvus.MilvusVectorStore.delete`

```python
delete(collection:str, ids:Sequence[UUID]) -> None
```

Delete records by id.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to delete from.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to delete.

###### `agrag.vectordb.milvus.MilvusVectorStore.delete_collection`

```python
delete_collection(name:str) -> None
```

Delete a collection and all its entities.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

###### `agrag.vectordb.milvus.MilvusVectorStore.ensure_collection`

```python
ensure_collection(name:str, *, dimensions:int, distance:Distance, hybrid:bool = False) -> None
```

Create the collection if it does not exist.

Milvus performs BM25 server-side, so the sparse field and its `Function`
are always provisioned; the `hybrid` flag is accepted for interface
parity but is a no-op here. An existing collection must already carry
this same fixed schema, since `upsert` and `hybrid_search` always
read and write every field regardless of `hybrid`.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.
- **dimensions** (<code>[int](#int)</code>) – The embedding dimension.
- **distance** (<code>[Distance](#agrag.common.data_models.vector_record.Distance)</code>) – The distance metric new collections use.
- **hybrid** (<code>[bool](#bool)</code>) – Accepted for interface parity; ignored by Milvus.

**Raises:**

- <code>[CollectionDimensionMismatchError](#agrag.vectordb.errors.CollectionDimensionMismatchError)</code> – The collection exists with a
  different dimension than `dimensions`.
- <code>[VectorStoreError](#agrag.vectordb.errors.VectorStoreError)</code> – The collection exists but is missing a field or
  index this adapter requires.

###### `agrag.vectordb.milvus.MilvusVectorStore.hybrid_search`

```python
hybrid_search(collection:str, query_vector:Sequence[float], query_text:str, *, limit:int = 10, filters:dict[str, Any] | None = None, alpha:float = 0.5) -> list[VectorHit]
```

Search by dense vector and keyword text in one fused call.

Fusion uses Milvus's native weighted reranker, which normalizes each
request's scores before applying `alpha`.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **query_text** (<code>[str](#str)</code>) – The query text, matched by BM25.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on scalar fields.
- **alpha** (<code>[float](#float)</code>) – The dense/keyword balance. `1.0` is pure dense, `0.0` is
  pure keyword.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The fused hits, highest score first.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`, or `alpha` is outside `[0.0, 1.0]`.

###### `agrag.vectordb.milvus.MilvusVectorStore.initialize`

```python
initialize() -> None
```

Check connectivity and authentication.

###### `agrag.vectordb.milvus.MilvusVectorStore.invalidate_collection`

```python
invalidate_collection(name:str) -> None
```

Drop cached distance-metric knowledge of a collection.

This store caches a collection's distance metric after the first
call that resolves it, on the assumption that it alone (via
`ensure_collection`/`delete_collection`) owns the collection's
lifecycle for as long as this instance is in use. If something
outside this instance deletes and recreates a collection under the
same name with a different metric, call this first so the next call
re-resolves that collection's metric from the backend instead of
trusting the stale cache.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

###### `agrag.vectordb.milvus.MilvusVectorStore.retrieve`

```python
retrieve(collection:str, ids:Sequence[UUID]) -> list[VectorRecord]
```

Fetch records by id.

Requests at most `MAX_RESPONSE_LIMIT` ids per call, so a large
`ids` list cannot exceed Milvus's response-size ceiling in one
request the way sending every id at once would.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to fetch.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The records that exist, in the requested order, omitting missing
- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – ids.

###### `agrag.vectordb.milvus.MilvusVectorStore.scroll`

```python
scroll(collection:str, *, limit:int = 100, page_offset:str | None = None, filters:dict[str, Any] | None = None, with_vectors:bool = False) -> tuple[list[VectorRecord], str | None]
```

Iterate records in a collection, in batches.

Milvus rejects a query whose `offset + limit` exceeds
`MAX_RESPONSE_LIMIT`, so a numeric offset cannot page past that
many total records. Pages instead cursor on the `id` primary key:
each page filters on `id > page_offset` and orders by `id`
ascending, which needs no offset at all and so never hits that
window regardless of collection size. The explicit order is load
bearing: without it, an unordered query result could omit rows at or
below the next cursor, permanently skipping them on the next page.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **limit** (<code>[int](#int)</code>) – The maximum number of records per page.
- **page_offset** (<code>[str](#str) | None</code>) – The id cursor from a previous `scroll` call.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on scalar fields.
- **with_vectors** (<code>[bool](#bool)</code>) – Whether to return each record's vector.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The page of records and the next page cursor, or `None` at the
- <code>[str](#str) | None</code> – end.

###### `agrag.vectordb.milvus.MilvusVectorStore.search`

```python
search(collection:str, query_vector:Sequence[float], *, limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search by dense vector only.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on scalar fields.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The matched hits, highest score first.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`.

###### `agrag.vectordb.milvus.MilvusVectorStore.upsert`

```python
upsert(collection:str, records:Sequence[VectorRecord], *, batch_size:int = 256) -> None
```

Write or overwrite records in a collection.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to write to.
- **records** (<code>[Sequence](#collections.abc.Sequence)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code>) – The records to upsert, in order.
- **batch_size** (<code>[int](#int)</code>) – The number of records per backend write call. Must be
  positive.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `batch_size` is not positive.

#### `agrag.vectordb.qdrant`

Qdrant vector-store backend.

**Classes:**

- [**QdrantVectorStore**](#agrag.vectordb.qdrant.QdrantVectorStore) – A `VectorStore` backed by Qdrant, including native hybrid search.

##### `agrag.vectordb.qdrant.QdrantVectorStore`

```python
QdrantVectorStore(*, settings:QdrantSettings | None = None, sparse_embedder:SparseEmbedder | None = None, client:Any | None = None, models:Any | None = None) -> None
```

Bases: <code>[VectorStore](#agrag.vectordb.base.VectorStore)</code>

A `VectorStore` backed by Qdrant, including native hybrid search.

The client connects lazily on first use, so constructing the store does not
open a network connection. Hybrid search builds its sparse query with a
`SparseEmbedder` that defaults to FastEmbed BM25 and loads only when a
hybrid call first runs, not at construction.

**Functions:**

- [**close**](#agrag.vectordb.qdrant.QdrantVectorStore.close) – Release the backend connection.
- [**collection_exists**](#agrag.vectordb.qdrant.QdrantVectorStore.collection_exists) – Report whether a collection exists.
- [**count**](#agrag.vectordb.qdrant.QdrantVectorStore.count) – Count records in a collection.
- [**delete**](#agrag.vectordb.qdrant.QdrantVectorStore.delete) – Delete records by id.
- [**delete_collection**](#agrag.vectordb.qdrant.QdrantVectorStore.delete_collection) – Delete a collection and all its points.
- [**ensure_collection**](#agrag.vectordb.qdrant.QdrantVectorStore.ensure_collection) – Create the collection if it does not exist.
- [**hybrid_search**](#agrag.vectordb.qdrant.QdrantVectorStore.hybrid_search) – Search by dense vector and keyword text, fused by a weighted blend.
- [**initialize**](#agrag.vectordb.qdrant.QdrantVectorStore.initialize) – Check connectivity and authentication.
- [**invalidate_collection**](#agrag.vectordb.qdrant.QdrantVectorStore.invalidate_collection) – Drop cached hybrid-state and distance-metric knowledge of a collection.
- [**retrieve**](#agrag.vectordb.qdrant.QdrantVectorStore.retrieve) – Fetch records by id.
- [**scroll**](#agrag.vectordb.qdrant.QdrantVectorStore.scroll) – Iterate records in a collection, in batches.
- [**search**](#agrag.vectordb.qdrant.QdrantVectorStore.search) – Search by dense vector only.
- [**upsert**](#agrag.vectordb.qdrant.QdrantVectorStore.upsert) – Write or overwrite records in a collection.

**Parameters:**

- **settings** (<code>[QdrantSettings](#agrag.vectordb.settings.QdrantSettings) | None</code>) – Qdrant connection settings. Defaults to
  `QdrantSettings()`.
- **sparse_embedder** (<code>[SparseEmbedder](#agrag.embedding.sparse_base.SparseEmbedder) | None</code>) – The sparse embedder hybrid search uses. Defaults to
  a lazily-built `FastEmbedBM25Embedder`.
- **client** (<code>[Any](#typing.Any) | None</code>) – A pre-built `AsyncQdrantClient`, for tests. When set,
  `__init__` imports nothing and the store calls this object
  directly instead of building one.
- **models** (<code>[Any](#typing.Any) | None</code>) – The `qdrant_client.models` module, for tests. Pair with
  `client` so filter/payload helpers work without needing the
  real `qdrant_client` package installed at all.

###### `agrag.vectordb.qdrant.QdrantVectorStore.close`

```python
close() -> None
```

Release the backend connection.

###### `agrag.vectordb.qdrant.QdrantVectorStore.collection_exists`

```python
collection_exists(name:str) -> bool
```

Report whether a collection exists.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

**Returns:**

- <code>[bool](#bool)</code> – `True` if the collection exists.

###### `agrag.vectordb.qdrant.QdrantVectorStore.count`

```python
count(collection:str, *, filters:dict[str, Any] | None = None) -> int
```

Count records in a collection.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to count.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.

**Returns:**

- <code>[int](#int)</code> – The number of matching records.

###### `agrag.vectordb.qdrant.QdrantVectorStore.delete`

```python
delete(collection:str, ids:Sequence[UUID]) -> None
```

Delete records by id.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to delete from.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to delete.

###### `agrag.vectordb.qdrant.QdrantVectorStore.delete_collection`

```python
delete_collection(name:str) -> None
```

Delete a collection and all its points.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

###### `agrag.vectordb.qdrant.QdrantVectorStore.ensure_collection`

```python
ensure_collection(name:str, *, dimensions:int, distance:Distance, hybrid:bool = False) -> None
```

Create the collection if it does not exist.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.
- **dimensions** (<code>[int](#int)</code>) – The embedding dimension.
- **distance** (<code>[Distance](#agrag.common.data_models.vector_record.Distance)</code>) – The distance metric new collections use.
- **hybrid** (<code>[bool](#bool)</code>) – Whether to provision the named sparse vector hybrid search
  needs.

**Raises:**

- <code>[CollectionDimensionMismatchError](#agrag.vectordb.errors.CollectionDimensionMismatchError)</code> – The collection exists with a
  different dimension than `dimensions`.
- <code>[VectorStoreError](#agrag.vectordb.errors.VectorStoreError)</code> – The collection exists without hybrid search
  support and `hybrid=True` was requested.

###### `agrag.vectordb.qdrant.QdrantVectorStore.hybrid_search`

```python
hybrid_search(collection:str, query_vector:Sequence[float], query_text:str, *, limit:int = 10, filters:dict[str, Any] | None = None, alpha:float = 0.5) -> list[VectorHit]
```

Search by dense vector and keyword text, fused by a weighted blend.

Qdrant's native fusion methods (RRF, DBSF) have no continuous
dense/keyword weight, so this runs the dense and sparse (BM25)
searches independently, min-max normalizes each result set's scores
to `[0, 1]`, then combines them per id as
`alpha * dense + (1 - alpha) * sparse`. Each side fetches a wider
candidate pool than `limit` so a document strong on only one signal
still has a chance to reach the blended top results.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **query_text** (<code>[str](#str)</code>) – The query text, matched by BM25.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.
- **alpha** (<code>[float](#float)</code>) – The dense/keyword balance. `1.0` is pure dense, `0.0` is
  pure keyword.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The blended hits, highest combined score first.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`, or `alpha` is outside `[0.0, 1.0]`.

###### `agrag.vectordb.qdrant.QdrantVectorStore.initialize`

```python
initialize() -> None
```

Check connectivity and authentication.

###### `agrag.vectordb.qdrant.QdrantVectorStore.invalidate_collection`

```python
invalidate_collection(name:str) -> None
```

Drop cached hybrid-state and distance-metric knowledge of a collection.

This store caches a collection's hybrid support and distance metric
after the first call that resolves them, on the assumption that it
alone (via `ensure_collection`/`delete_collection`) owns the
collection's lifecycle for as long as this instance is in use. If
something outside this instance deletes and recreates a collection
under the same name with different config, call this first so the
next call re-resolves that collection's state from the backend
instead of trusting the stale cache.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

###### `agrag.vectordb.qdrant.QdrantVectorStore.retrieve`

```python
retrieve(collection:str, ids:Sequence[UUID]) -> list[VectorRecord]
```

Fetch records by id.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to fetch.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The records that exist, in the requested order, omitting missing
- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – ids.

###### `agrag.vectordb.qdrant.QdrantVectorStore.scroll`

```python
scroll(collection:str, *, limit:int = 100, page_offset:str | None = None, filters:dict[str, Any] | None = None, with_vectors:bool = False) -> tuple[list[VectorRecord], str | None]
```

Iterate records in a collection, in batches.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **limit** (<code>[int](#int)</code>) – The maximum number of records per page.
- **page_offset** (<code>[str](#str) | None</code>) – The offset from a previous `scroll` call.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.
- **with_vectors** (<code>[bool](#bool)</code>) – Whether to return each record's vector.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The page of records and the next page offset, or `None` at the
- <code>[str](#str) | None</code> – end.

###### `agrag.vectordb.qdrant.QdrantVectorStore.search`

```python
search(collection:str, query_vector:Sequence[float], *, limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search by dense vector only.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The matched hits, highest score first.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`.

###### `agrag.vectordb.qdrant.QdrantVectorStore.upsert`

```python
upsert(collection:str, records:Sequence[VectorRecord], *, batch_size:int = 256) -> None
```

Write or overwrite records in a collection.

When `collection` has sparse-vector support (created or previously
seen with `ensure_collection(..., hybrid=True)`), each record's
`payload["text"]` is also sparse-embedded and stored under the named
sparse vector, so `hybrid_search`'s keyword arm has real vectors to
match. A record with no `text` payload key gets an empty sparse
vector and only ever surfaces through the dense side of a hybrid
search.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to write to.
- **records** (<code>[Sequence](#collections.abc.Sequence)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code>) – The records to upsert, in order.
- **batch_size** (<code>[int](#int)</code>) – The number of records per backend write call. Must be
  positive.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `batch_size` is not positive.

#### `agrag.vectordb.settings`

Settings for vector-store backends.

**Classes:**

- [**MilvusSettings**](#agrag.vectordb.settings.MilvusSettings) – Milvus connection configuration.
- [**QdrantSettings**](#agrag.vectordb.settings.QdrantSettings) – Qdrant connection configuration.
- [**WeaviateSettings**](#agrag.vectordb.settings.WeaviateSettings) – Weaviate connection configuration.

##### `agrag.vectordb.settings.MilvusSettings`

Bases: <code>[BaseSettings](#pydantic_settings.BaseSettings)</code>

Milvus connection configuration.

**Attributes:**

- [**uri**](#agrag.vectordb.settings.MilvusSettings.uri) (<code>[str](#str)</code>) – The Milvus endpoint URI. Env: `MILVUS_URI`.
- [**token**](#agrag.vectordb.settings.MilvusSettings.token) (<code>[str](#str)</code>) – The Milvus auth token. Empty string for an unauthenticated
  instance. Env: `MILVUS_TOKEN`.
- [**require_tls**](#agrag.vectordb.settings.MilvusSettings.require_tls) (<code>[bool](#bool)</code>) – When `True`, reject a plaintext `uri` to a
  non-local host even with no `token` configured. Off by default
  since many deployments run an unauthenticated Milvus on a
  private network and rely on network segmentation rather than
  transport encryption. Env: `MILVUS_REQUIRE_TLS`.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `uri` is plaintext (`http`), points at a non-local
  host, and either `token` is set or `require_tls` is
  `True`. Use `https` for a remote Milvus instance.

###### `agrag.vectordb.settings.MilvusSettings.model_config`

```python
model_config = SettingsConfigDict(env_prefix='MILVUS_', env_file='.env', extra='ignore')
```

###### `agrag.vectordb.settings.MilvusSettings.require_tls`

```python
require_tls: bool = False
```

###### `agrag.vectordb.settings.MilvusSettings.token`

```python
token: str = ''
```

###### `agrag.vectordb.settings.MilvusSettings.uri`

```python
uri: str = 'http://localhost:19530'
```

##### `agrag.vectordb.settings.QdrantSettings`

Bases: <code>[BaseSettings](#pydantic_settings.BaseSettings)</code>

Qdrant connection configuration.

**Attributes:**

- [**url**](#agrag.vectordb.settings.QdrantSettings.url) (<code>[str](#str)</code>) – The Qdrant endpoint URL. Env: `QDRANT_URL`.
- [**api_key**](#agrag.vectordb.settings.QdrantSettings.api_key) (<code>[str](#str)</code>) – The Qdrant API key. Env: `QDRANT_API_KEY`.
- [**require_tls**](#agrag.vectordb.settings.QdrantSettings.require_tls) (<code>[bool](#bool)</code>) – When `True`, reject a plaintext `url` to a non-local
  host even with no `api_key` configured. Off by default since
  many deployments run an unauthenticated Qdrant on a private
  network and rely on network segmentation rather than transport
  encryption. Env: `QDRANT_REQUIRE_TLS`.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `url` is plaintext (`http`), points at a non-local
  host, and either `api_key` is set or `require_tls` is
  `True`. Use `https` for a remote Qdrant instance.

###### `agrag.vectordb.settings.QdrantSettings.api_key`

```python
api_key: str = ''
```

###### `agrag.vectordb.settings.QdrantSettings.model_config`

```python
model_config = SettingsConfigDict(env_prefix='QDRANT_', env_file='.env', extra='ignore')
```

###### `agrag.vectordb.settings.QdrantSettings.require_tls`

```python
require_tls: bool = False
```

###### `agrag.vectordb.settings.QdrantSettings.url`

```python
url: str = 'http://localhost:6333'
```

##### `agrag.vectordb.settings.WeaviateSettings`

Bases: <code>[BaseSettings](#pydantic_settings.BaseSettings)</code>

Weaviate connection configuration.

**Attributes:**

- [**mode**](#agrag.vectordb.settings.WeaviateSettings.mode) (<code>[Literal](#typing.Literal)['cloud', 'custom']</code>) – `"cloud"` connects to Weaviate Cloud. `"custom"` connects to
  a self-hosted instance (used by integration tests against the local
  Docker Compose instance) — an explicit field, not inferred from the
  URL, since inference caused real connection bugs in surveyed
  reference implementations. Env: `WEAVIATE_MODE`.
- [**url**](#agrag.vectordb.settings.WeaviateSettings.url) (<code>[str](#str)</code>) – The Weaviate endpoint URL. For `"cloud"`, the cluster URL. For
  `"custom"`, the full host URL. Env: `WEAVIATE_URL`.
- [**api_key**](#agrag.vectordb.settings.WeaviateSettings.api_key) (<code>[str](#str)</code>) – The Weaviate API key. Env: `WEAVIATE_API_KEY`.
- [**grpc_port**](#agrag.vectordb.settings.WeaviateSettings.grpc_port) (<code>[int](#int)</code>) – The gRPC port, used by `"custom"` mode only (`"cloud"`
  mode infers it). Env: `WEAVIATE_GRPC_PORT`.
- [**require_tls**](#agrag.vectordb.settings.WeaviateSettings.require_tls) (<code>[bool](#bool)</code>) – When `True`, reject a plaintext `url` to a non-local
  host even with no `api_key` configured. Off by default since
  many deployments run an unauthenticated Weaviate on a private
  network and rely on network segmentation rather than transport
  encryption. Env: `WEAVIATE_REQUIRE_TLS`.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `url` is plaintext (`http`), points at a non-local
  host, and either `api_key` is set or `require_tls` is
  `True`. Use `https` for a remote Weaviate instance.

###### `agrag.vectordb.settings.WeaviateSettings.api_key`

```python
api_key: str = ''
```

###### `agrag.vectordb.settings.WeaviateSettings.grpc_port`

```python
grpc_port: int = 50051
```

###### `agrag.vectordb.settings.WeaviateSettings.mode`

```python
mode: Literal['cloud', 'custom'] = 'custom'
```

###### `agrag.vectordb.settings.WeaviateSettings.model_config`

```python
model_config = SettingsConfigDict(env_prefix='WEAVIATE_', env_file='.env', extra='ignore')
```

###### `agrag.vectordb.settings.WeaviateSettings.require_tls`

```python
require_tls: bool = False
```

###### `agrag.vectordb.settings.WeaviateSettings.url`

```python
url: str = 'http://localhost:8080'
```

#### `agrag.vectordb.weaviate`

Weaviate vector-store backend.

**Classes:**

- [**WeaviateVectorStore**](#agrag.vectordb.weaviate.WeaviateVectorStore) – A `VectorStore` backed by Weaviate, including native hybrid search.

##### `agrag.vectordb.weaviate.WeaviateVectorStore`

```python
WeaviateVectorStore(*, settings:WeaviateSettings | None = None, client:Any | None = None) -> None
```

Bases: <code>[VectorStore](#agrag.vectordb.base.VectorStore)</code>

A `VectorStore` backed by Weaviate, including native hybrid search.

The client connects lazily on first use, so constructing the store does not
open a network connection. Weaviate does its own server-side BM25, so
hybrid search needs no client-side sparse embedder.

**Functions:**

- [**close**](#agrag.vectordb.weaviate.WeaviateVectorStore.close) – Release the backend connection.
- [**collection_exists**](#agrag.vectordb.weaviate.WeaviateVectorStore.collection_exists) – Report whether a collection exists.
- [**count**](#agrag.vectordb.weaviate.WeaviateVectorStore.count) – Count records in a collection.
- [**delete**](#agrag.vectordb.weaviate.WeaviateVectorStore.delete) – Delete records by id.
- [**delete_collection**](#agrag.vectordb.weaviate.WeaviateVectorStore.delete_collection) – Delete a collection and all its objects.
- [**ensure_collection**](#agrag.vectordb.weaviate.WeaviateVectorStore.ensure_collection) – Create the collection if it does not exist.
- [**hybrid_search**](#agrag.vectordb.weaviate.WeaviateVectorStore.hybrid_search) – Search by dense vector and keyword text in one fused call.
- [**initialize**](#agrag.vectordb.weaviate.WeaviateVectorStore.initialize) – Open the connection and check authentication.
- [**retrieve**](#agrag.vectordb.weaviate.WeaviateVectorStore.retrieve) – Fetch records by id.
- [**scroll**](#agrag.vectordb.weaviate.WeaviateVectorStore.scroll) – Iterate records in a collection, in batches.
- [**search**](#agrag.vectordb.weaviate.WeaviateVectorStore.search) – Search by dense vector only.
- [**upsert**](#agrag.vectordb.weaviate.WeaviateVectorStore.upsert) – Write or overwrite records in a collection.

**Parameters:**

- **settings** (<code>[WeaviateSettings](#agrag.vectordb.settings.WeaviateSettings) | None</code>) – Weaviate connection settings. Defaults to
  `WeaviateSettings()`.
- **client** (<code>[Any](#typing.Any) | None</code>) – A pre-built Weaviate async client, for tests. When set,
  `__init__` imports nothing and the store calls this object
  directly instead of building one.

###### `agrag.vectordb.weaviate.WeaviateVectorStore.close`

```python
close() -> None
```

Release the backend connection.

###### `agrag.vectordb.weaviate.WeaviateVectorStore.collection_exists`

```python
collection_exists(name:str) -> bool
```

Report whether a collection exists.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

**Returns:**

- <code>[bool](#bool)</code> – `True` if the collection exists.

###### `agrag.vectordb.weaviate.WeaviateVectorStore.count`

```python
count(collection:str, *, filters:dict[str, Any] | None = None) -> int
```

Count records in a collection.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to count.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.

**Returns:**

- <code>[int](#int)</code> – The number of matching records.

###### `agrag.vectordb.weaviate.WeaviateVectorStore.delete`

```python
delete(collection:str, ids:Sequence[UUID]) -> None
```

Delete records by id.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to delete from.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to delete.

###### `agrag.vectordb.weaviate.WeaviateVectorStore.delete_collection`

```python
delete_collection(name:str) -> None
```

Delete a collection and all its objects.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.

###### `agrag.vectordb.weaviate.WeaviateVectorStore.ensure_collection`

```python
ensure_collection(name:str, *, dimensions:int, distance:Distance, hybrid:bool = False) -> None
```

Create the collection if it does not exist.

**Parameters:**

- **name** (<code>[str](#str)</code>) – The collection name.
- **dimensions** (<code>[int](#int)</code>) – The embedding dimension.
- **distance** (<code>[Distance](#agrag.common.data_models.vector_record.Distance)</code>) – The distance metric new collections use.
- **hybrid** (<code>[bool](#bool)</code>) – No-op for Weaviate, which needs no sparse provisioning.

**Raises:**

- <code>[CollectionDimensionMismatchError](#agrag.vectordb.errors.CollectionDimensionMismatchError)</code> – An existing object in the
  collection carries a vector of a different dimension. Weaviate
  keeps no schema-level dimension for self-provided vectors, so
  an existing collection with no vector-bearing object cannot be
  checked this way.

###### `agrag.vectordb.weaviate.WeaviateVectorStore.hybrid_search`

```python
hybrid_search(collection:str, query_vector:Sequence[float], query_text:str, *, limit:int = 10, filters:dict[str, Any] | None = None, alpha:float = 0.5) -> list[VectorHit]
```

Search by dense vector and keyword text in one fused call.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **query_text** (<code>[str](#str)</code>) – The query text, matched by keyword/BM25.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.
- **alpha** (<code>[float](#float)</code>) – The dense/keyword balance. `1.0` is pure dense, `0.0` is
  pure keyword.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The fused hits, highest score first.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`, or `alpha` is outside `[0.0, 1.0]`.

###### `agrag.vectordb.weaviate.WeaviateVectorStore.initialize`

```python
initialize() -> None
```

Open the connection and check authentication.

###### `agrag.vectordb.weaviate.WeaviateVectorStore.retrieve`

```python
retrieve(collection:str, ids:Sequence[UUID]) -> list[VectorRecord]
```

Fetch records by id.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **ids** (<code>[Sequence](#collections.abc.Sequence)\[[UUID](#uuid.UUID)\]</code>) – The ids to fetch.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The records that exist, in the requested order, omitting missing
- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – ids.

###### `agrag.vectordb.weaviate.WeaviateVectorStore.scroll`

```python
scroll(collection:str, *, limit:int = 100, page_offset:str | None = None, filters:dict[str, Any] | None = None, with_vectors:bool = False) -> tuple[list[VectorRecord], str | None]
```

Iterate records in a collection, in batches.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to read.
- **limit** (<code>[int](#int)</code>) – The maximum number of records per page.
- **page_offset** (<code>[str](#str) | None</code>) – The cursor id from a previous `scroll` call.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.
- **with_vectors** (<code>[bool](#bool)</code>) – Whether to return each record's vector.

**Returns:**

- <code>[list](#list)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code> – The page of records and the next page cursor, or `None` at the
- <code>[str](#str) | None</code> – end.

###### `agrag.vectordb.weaviate.WeaviateVectorStore.search`

```python
search(collection:str, query_vector:Sequence[float], *, limit:int = 10, filters:dict[str, Any] | None = None) -> list[VectorHit]
```

Search by dense vector only.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to search.
- **query_vector** (<code>[Sequence](#collections.abc.Sequence)\[[float](#float)\]</code>) – The dense query embedding.
- **limit** (<code>[int](#int)</code>) – The maximum number of hits to return.
- **filters** (<code>[dict](#dict)\[[str](#str), [Any](#typing.Any)\] | None</code>) – A flat-dict filter on payload fields.

**Returns:**

- <code>[list](#list)\[[VectorHit](#agrag.common.data_models.vector_record.VectorHit)\]</code> – The matched hits, highest score first.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `limit` is not positive, or exceeds
  `MAX_SEARCH_LIMIT`.

###### `agrag.vectordb.weaviate.WeaviateVectorStore.upsert`

```python
upsert(collection:str, records:Sequence[VectorRecord], *, batch_size:int = 256) -> None
```

Write or overwrite records in a collection.

Uses Weaviate's batch import, which replaces an existing object
sharing a written id instead of rejecting it, giving real
insert-or-replace semantics and per-call batching in one request.

**Parameters:**

- **collection** (<code>[str](#str)</code>) – The collection to write to.
- **records** (<code>[Sequence](#collections.abc.Sequence)\[[VectorRecord](#agrag.common.data_models.vector_record.VectorRecord)\]</code>) – The records to upsert, in order.
- **batch_size** (<code>[int](#int)</code>) – The number of records per backend write call. Must be
  positive.

**Raises:**

- <code>[ValueError](#ValueError)</code> – `batch_size` is not positive.
- <code>[VectorStoreError](#agrag.vectordb.errors.VectorStoreError)</code> – At least one record in a batch failed to write.
