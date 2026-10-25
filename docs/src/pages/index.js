import Layout from '@theme/Layout';
import Link from '@docusaurus/Link';
import InstallCommand from '@site/src/components/InstallCommand';
import Diagram from '@site/src/components/Diagram';
import styles from './index.module.css';

const features = [
  {tone: 'stone', title: 'One graph for enterprise knowledge, conversation history, and decision traces', lead: 'Source documents, agent activity, and decisions live in one graph, so readers can trace each decision to its evidence.'},
  {tone: 'blue', title: 'Build the graph around your own schema', lead: 'You decide which things matter, and the graph is built around them.'},
  {tone: 'green', title: 'Search your documents and read the evidence', lead: 'Agents find passages, read the exact text, and move around a document the way a person would.'},
  {tone: 'amber', title: 'Record conversation history and decisions', lead: 'Conversation history records task events and steps. Decision traces link conclusions to evidence and flag decisions for review when sources change.'},
  {tone: 'violet', title: 'Use the built-in agent or any MCP client', lead: 'Use the agent that ships with the library, or connect your own through MCP.'},
];

const intro = 'Turn documents into searchable knowledge shaped by your own schema. Give agents tools to follow relationships, read source passages, and cite what they use. Keep decisions linked to their evidence. Use the Python library, connect your agent through MCP, or start with the built-in agent.';

export default function Home() {
  return (
    <Layout
      title="Context graphs for enterprise knowledge, conversation history, and decision traces"
      description="Agentic GraphRAG connects enterprise knowledge, conversation history, and decision traces in one graph, so agents can find evidence, resume work, and review decisions when their sources change.">
      <header className={styles.hero}>
        <div className={`container ${styles.heroInner}`}>
          <h1 className={styles.title}>
            Context graphs that connect enterprise knowledge, conversation history, and decision traces.
          </h1>
          <p className={styles.pitch}>
            Agentic GraphRAG connects enterprise knowledge, conversation history, and decision traces in one graph.
            Agents can find evidence, resume work across sessions, and review decisions when their sources change.
          </p>
          <Diagram
            className={styles.flow}
            name="full-flow"
            alt="Documents are loaded, chunked, extracted, and resolved into a graph with enterprise knowledge, conversation history, and decision traces. A changed document flags the decisions that cite it. An agent searches and reads the graph, records its events and steps, and returns an answer with checked numbered sources."
          />
        </div>
      </header>
      <main>
        <section className={styles.section}>
          <div className={`container ${styles.intro}`}>
            <p>{intro}</p>
            <p>
              Store the graph, embeddings, and search indexes in Neo4j or FalkorDB.
              Both support ingestion, hybrid search, conversation history, and decision traces. Vectors can stay in the graph or move to one external store: Qdrant, Milvus, or Weaviate.
              {' '}<Link to="/stable/concepts/graph-storage">Compare backends</Link>
              {' '}or <Link to="/stable/guides/configure-storage-backends">configure a connection</Link>.
            </p>
          </div>
        </section>
        <section className={styles.section}>
          <div className={`container ${styles.tiles}`}>
            {features.map(({tone, title, lead}, i) => (
              <div
                key={title}
                className={`${styles.tile} ${styles[tone]} ${i === 0 ? styles.tileFeatured : ''}`}>
                <h3>{title}</h3>
                <p>{lead}</p>
              </div>
            ))}
          </div>
        </section>
        <section className={styles.section}>
          <div className={`container ${styles.closing}`}>
            <div className={styles.actions}>
              <InstallCommand command="uv pip install agentic-graphrag" />
              <Link className="button button--primary button--lg" to="/stable/get-started/introduction">
                Get started
              </Link>
              <Link
                className="button button--secondary button--lg"
                href="https://github.com/ontogr/agentic-graphrag">
                View on GitHub
              </Link>
            </div>
            <p className={styles.facts}>
              Python 3.11+ &nbsp;·&nbsp; Apache-2.0
            </p>
          </div>
        </section>
      </main>
    </Layout>
  );
}
