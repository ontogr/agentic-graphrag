import Layout from '@theme/Layout';
import Link from '@docusaurus/Link';
import CodeBlock from '@theme/CodeBlock';
import styles from './index.module.css';

const features = [
  {
    title: 'Loads your files',
    body: 'One Graph.add() call reads text, Markdown, HTML, CSV, JSON, and, with Docling, PDF, Word, PowerPoint, and images.',
  },
  {
    title: 'Extracts with a schema you define',
    body: 'You name the entity types, the relation types, and the valid patterns. A local GLiNER model runs first, and an LLM takes over only for weak chunks.',
  },
  {
    title: 'Merges duplicates with care',
    body: 'Exact, fuzzy, embedding, and LLM-checked tiers compare mentions. An uncertain or failed comparison never merges, and matches are stored as edges so both entities stay in the graph.',
  },
  {
    title: 'Retrieves across graph and vectors',
    body: 'Entity, chunk, community, text-to-Cypher, and graph-expansion search run together. Reciprocal rank fusion and reranking order the results.',
  },
  {
    title: 'Answers with citations',
    body: 'An agent plans sub-questions, researches them, and verifies the evidence. Each claim points to a source, and OpenTelemetry records the run.',
  },
  {
    title: 'Scores itself on your questions',
    body: 'Judged evals measure extraction, resolution, answers, and agent trajectories against your own gold sets, so regressions surface before your users see them.',
  },
];

// Each pull request that adds a section adds its card here, so every link resolves.
const paths = [
  {
    title: 'Build your first graph',
    body: 'Free Neo4j Aura, two models, about ten minutes to a working graph.',
    to: '/get-started/quickstart',
  },
  {
    title: 'Ingest your own corpus',
    body: 'Chunking, schema-guided extraction, and duplicate resolution over your files.',
    to: '/guides/ingest-documents',
  },
  {
    title: 'Run the citing agent',
    body: 'Plan, research, verify — an answer where every claim carries an evidence key.',
    to: '/guides/retrieve-and-answer',
  },
];

const ingestSteps = ['Sources', 'Load and chunk', 'Extract', 'Resolve', 'Graph and vector stores'];
const askSteps = ['Question', 'Plan', 'Retrieve', 'Verify', 'Cited answer'];

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
      title="Give your agents answers they can prove"
      description="Agentic GraphRAG builds a typed knowledge graph from your documents. An agent plans, researches, and verifies each answer, and cites its sources.">
      <header className={styles.hero}>
        <div className={`container ${styles.heroInner}`}>
          <h1 className={styles.title}>
            Give your agents answers they can <span className={styles.accent}>prove</span>.
          </h1>
          <p className={styles.pitch}>
            Build a knowledge graph from your documents. Then ask it questions.
            Agentic GraphRAG plans, researches, and verifies each answer, and cites its sources.
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
            <Link className="button button--primary button--lg" to="/get-started/introduction">
              Get started
            </Link>
            <Link
              className="button button--secondary button--lg"
              href="https://github.com/ontogr/agentic-graphrag">
              View on GitHub
            </Link>
          </div>
          <p className={styles.facts}>
            Python 3.11+ &nbsp;·&nbsp; Apache-2.0 &nbsp;·&nbsp; Works with Neo4j, Qdrant, and Weaviate
          </p>
        </div>
        <div className="container">
          <div className={styles.pipeline}>
            <Lane label="Ingest" steps={ingestSteps} />
            <Lane label="Ask" steps={askSteps} />
          </div>
          <p className={styles.pipelineNote}>
            Both flows read and write the same graph and vector indexes.
          </p>
        </div>
      </header>
      <main>
        <section className={styles.section}>
          <div className="container">
            <h2 className={`${styles.h2} ${styles.sectionTitle}`}>See it work</h2>
            <div className={styles.example}>
              <div className={styles.exampleCol}>
                <CodeBlock language="python" title="build_graph.py">{`schema = GraphSchema(...)  # you name the
# entities, relations, and patterns

graph = await Graph.open(
    schema=schema,
    graph_store=build_graph_store("neo4j"),
    embedder=build_embedder(
        "ibm-granite/granite-embedding-small-english-r2"),
    extractor=GlinerExtractor(),
)
result = await graph.add(text=(
    "Satya Nadella works at Microsoft. "
    "Bill Gates founded Microsoft. "
    "Microsoft is headquartered in Redmond."
))
print("entities extracted:",
      result.extraction.entities_extracted)`}</CodeBlock>
                <pre className={styles.output} aria-label="build_graph.py output">
                  {'entities extracted: 6\nrelations extracted: 3'}
                </pre>
                <p className={styles.exampleNote}>
                  The first run downloads two local models, about 385 MB.
                </p>
              </div>
              <div className={styles.exampleCol}>
                <CodeBlock language="python" title="ask.py">{`agent = build_agent(
    engine=engine,
    llm_settings=llm_settings,
    graph_schema=schema,
)
question = (
    "Who founded the company "
    "that Satya Nadella works at?"
)
result = await agent.ainvoke(
    {"messages": [{"role": "user",
                   "content": question}]}
)
print(answer.content)`}</CodeBlock>
                <pre className={styles.output} aria-label="ask.py example output">
                  {'Satya Nadella works at Microsoft (E1, E3), which was\nfounded by Bill Gates (E2, E3, C1).\nevidence keys: E1, E2, E3, E4, C1, V1'}
                </pre>
                <p className={styles.exampleNote}>
                  Example output; answers vary with your model. Every claim cites its
                  evidence: E keys are entities, C keys chunks, V keys graph-query values.
                </p>
              </div>
            </div>
            <p className={styles.exampleCta}>
              <Link to="/get-started/quickstart">Run the full Quickstart</Link> — a free
              Neo4j Aura instance, two models, and about ten minutes.
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
          <div className={`container ${styles.grid}`}>
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
              <Link className="button button--primary button--lg" to="/get-started/introduction">
                Get started
              </Link>
            </div>
          </div>
        </section>
      </main>
    </Layout>
  );
}
