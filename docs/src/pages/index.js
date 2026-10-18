import Layout from '@theme/Layout';
import Link from '@docusaurus/Link';
import CodeBlock from '@theme/CodeBlock';
import styles from './index.module.css';

const features = [
  {
    title: 'Loads your files',
    body: 'One Graph.add() call reads text, Markdown, HTML, CSV, JSON, Word, PowerPoint, and Excel files. PDF and images need the docling extra.',
  },
  {
    title: 'Builds a graph around your schema',
    body: 'You name the entity types, the relation types, and the valid patterns. A local GLiNER model runs first, and an LLM reads the chunks it is least sure about.',
  },
  {
    title: 'Merges duplicates without losing anything',
    body: 'Exact, fuzzy, embedding, and LLM-checked tiers compare mentions. Matches are stored as edges, so both entities stay in the graph.',
  },
  {
    title: 'Finds passages and cites a version',
    body: 'Search by keyword, meaning, or both, fetch the exact text behind a result, and cite the document version it came from.',
  },
  {
    title: 'Remembers tasks and decisions',
    body: 'A named task keeps its events and steps. A decision keeps its rationale and the passages it relies on, and it is flagged for review when a source changes.',
  },
  {
    title: 'Works from Python, the agent, or MCP',
    body: 'Use the library, the built-in task-scoped agent, or the agrag-mcp server with any MCP client. OpenTelemetry records the run.',
  },
];

const paths = [
  {
    title: 'Build your first graph',
    body: 'Add a document, ask the agent a question, and look at the graph.',
    to: '/latest/get-started/quickstart',
  },
  {
    title: 'Features',
    body: 'The full list of what Agentic GraphRAG does.',
    to: '/latest/get-started/features',
  },
  {
    title: 'Find and cite evidence',
    body: 'Search passages, fetch exact text, and check citations from Python.',
    to: '/latest/guides/find-and-cite-evidence',
  },
  {
    title: 'Connect an MCP client',
    body: 'Run agrag-mcp to search documents and keep task and decision memory.',
    to: '/latest/guides/run-the-mcp-server',
  },
];

const ingestSteps = ['Sources', 'Load and chunk', 'Extract', 'Resolve', 'Neo4j graph'];
const askSteps = ['Question', 'Discover', 'Fetch', 'Check citations', 'Cited answer'];

function Lane({label, steps}) {
  return (
    <div className={styles.lane}>
      <span className={styles.laneLabel}>{label}</span>
      <ol className={styles.steps} aria-label={`${label} pipeline`}>
        {steps.map((step, i) => (
          <li
            key={step}
            className={`${styles.step} ${i === steps.length - 1 ? styles.stepEnd : ''}`}
            style={{'--i': i}}>
            <span className={styles.chip}>{step}</span>
            {i < steps.length - 1 && (
              <svg className={styles.arrow} viewBox="0 0 24 12" aria-hidden="true">
                <path d="M1 6h19" className={styles.arrowLine} />
                <path d="M15 1.5 20 6l-5 4.5" className={styles.arrowHead} />
              </svg>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}

export default function Home() {
  return (
    <Layout
      title="Build context graphs for AI agents"
      description="Agentic GraphRAG connects your documents, agent activity, and decisions in one graph, so agents can find evidence, continue work across sessions, and revisit decisions when their sources change.">
      <header className={styles.hero}>
        <div className={`container ${styles.heroInner}`}>
          <h1 className={styles.title}>
            Build context graphs for <span className={styles.accent}>AI agents</span>.
          </h1>
          <p className={styles.pitch}>
            Agentic GraphRAG connects your documents, agent activity, and decisions in one graph.
            Your agents can find evidence, continue work across sessions, and revisit decisions when their sources change.
          </p>
          <div className={styles.install}>
            <div className={styles.terminalBar} aria-hidden="true">
              <span className={`${styles.dot} ${styles.dotCyan}`} />
              <span className={`${styles.dot} ${styles.dotMid}`} />
              <span className={`${styles.dot} ${styles.dotBlue}`} />
            </div>
            <CodeBlock language="bash">uv pip install agentic-graphrag</CodeBlock>
          </div>
          <div className={styles.buttons}>
            <Link className="button button--primary button--lg" to="/latest/get-started/introduction">
              Get started
            </Link>
            <Link
              className="button button--secondary button--lg"
              href="https://github.com/ontogr/agentic-graphrag">
              View on GitHub
            </Link>
          </div>
          <p className={styles.facts}>
            Python 3.11+ &nbsp;·&nbsp; Apache-2.0 &nbsp;·&nbsp; Stores everything in Neo4j
          </p>
        </div>
        <div className="container">
          <div className={styles.pipeline}>
            <Lane label="Ingest" steps={ingestSteps} />
            <Lane label="Ask" steps={askSteps} />
          </div>
          <p className={styles.pipelineNote}>
            Both flows read and write the same Neo4j graph.
          </p>
        </div>
      </header>
      <main>
        <section className={styles.section}>
          <div className="container">
            <h2 className={`${styles.h2} ${styles.sectionTitle}`}>See it work</h2>
            <div className={styles.example}>
              <div className={styles.exampleCol}>
                <CodeBlock language="python" title="build_graph.py">{`document = Path("policy.md").resolve()

graph = await Graph.open(
    schema="operations",
    graph_store=build_graph_store("neo4j"),
    embedder=build_embedder(
        "ibm-granite/granite-embedding-small-english-r2"),
    extraction_settings=ExtractionSettings(mode="gliner"),
    max_llm_pairs=0,
)
result = await graph.add(document)
print("entities extracted:",
      result.extraction.entities_extracted)`}</CodeBlock>
                <p className={styles.exampleNote}>
                  Embeddings and extraction run on your machine.
                </p>
              </div>
              <div className={styles.exampleCol}>
                <CodeBlock language="python" title="ask.py">{`agent = build_agent(
    graph_store=build_graph_store("neo4j"),
    embedder=build_embedder(
        "ibm-granite/granite-embedding-small-english-r2"),
    scope=frozenset({str(document)}),
    project_id="ask",
    agent_id="researcher",
    llm_settings=AgentLLMSettings.from_openai_compatible_env(),
)
result = await agent.ainvoke({
    "task_name": "document-review",
    "question": "What does this document require?",
})
print(result["status"])
print(result["answer"])`}</CodeBlock>
                <p className={styles.exampleNote}>
                  The answer ends with a numbered Sources list. Wording varies with your model.
                </p>
              </div>
            </div>
            <p className={styles.exampleCta}>
              <Link to="/latest/get-started/quickstart">Run the full Quickstart</Link> to build
              a graph and ask a question in about ten minutes.
            </p>
          </div>
        </section>
        <section className={styles.section}>
          <div className="container">
            <h2 className={`${styles.h2} ${styles.sectionTitle}`}>What it does</h2>
            <div className={styles.grid}>
              {features.map(({title, body}) => (
                <div key={title}>
                  <h3 className={styles.featureTitle}>{title}</h3>
                  <p>{body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
        <section className={styles.section}>
          <div className={`container ${styles.grid} ${styles.pathGrid}`}>
            {paths.map(({title, body, to}) => (
              <Link key={title} className={styles.card} to={to}>
                <h3>{title}</h3>
                <p>{body}</p>
              </Link>
            ))}
          </div>
        </section>
        <section className={styles.section}>
          <div className="container">
            <div className={styles.ctaPanel}>
              <h2 className={styles.h2}>Ready to try it?</h2>
              <Link className="button button--primary button--lg" to="/latest/get-started/introduction">
                Get started
              </Link>
            </div>
          </div>
        </section>
      </main>
    </Layout>
  );
}
