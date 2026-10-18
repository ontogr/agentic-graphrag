import Layout from '@theme/Layout';
import Link from '@docusaurus/Link';
import InstallCommand from '@site/src/components/InstallCommand';
import Diagram from '@site/src/components/Diagram';
import styles from './index.module.css';

const features = [
  {tone: 'stone', title: 'One graph for documents, tasks, and decisions', lead: 'Documents, agent work, and decisions live together, so every answer can be traced back to its source.'},
  {tone: 'blue', title: 'Build the graph around your own schema', lead: 'You decide which things matter, and the graph is built around them.'},
  {tone: 'green', title: 'Search your documents and read the evidence', lead: 'Agents find passages, read the exact text, and move around a document the way a person would.'},
  {tone: 'amber', title: 'Remember tasks and decisions', lead: 'The memory layer records an agent\'s work and decisions as it runs, keeps them current when sources change, and recalls them to inform later decisions.'},
  {tone: 'violet', title: 'Use the built-in agent or any MCP client', lead: 'Use the agent that ships with the library, or connect your own through MCP.'},
];

const intro = 'Turn documents into searchable knowledge shaped by your own schema. Give agents tools to follow relationships, read source passages, and cite what they use. Keep decisions linked to the evidence behind them. Use the Python library, connect your agent through MCP, or start with the built-in agent.';

export default function Home() {
  return (
    <Layout
      title="Context graphs that give AI agents memory they can trace to its sources"
      description="Agentic GraphRAG connects your documents, agent activity, and decisions in one graph, so agents can find evidence, continue work across sessions, and revisit decisions when their sources change.">
      <header className={styles.hero}>
        <div className={`container ${styles.heroInner}`}>
          <h1 className={styles.title}>
            Context graphs that give AI agents <span className={styles.accent}>memory</span> they can trace to its sources.
          </h1>
          <p className={styles.pitch}>
            Agentic GraphRAG connects your documents, agent activity, and decisions in one graph.
            Your agents can find evidence, continue work across sessions, and revisit decisions when their sources change.
          </p>
          <Diagram
            className={styles.flow}
            name="full-flow"
            alt="Documents are loaded, chunked, extracted, and resolved into a graph with three layers: knowledge, conversation history, and decision traces. A changed document flags the decisions that cite it. An agent searches and reads the graph and records its events, steps, and decisions. Its answer passes a citation check and returns with numbered sources."
          />
        </div>
      </header>
      <main>
        <section className={styles.section}>
          <div className={`container ${styles.intro}`}>
            <p>{intro}</p>
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
