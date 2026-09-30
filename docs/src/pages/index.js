import Layout from '@theme/Layout';
import Link from '@docusaurus/Link';
import useBaseUrl from '@docusaurus/useBaseUrl';
import CodeBlock from '@theme/CodeBlock';
import Mermaid from '@theme/Mermaid';
import styles from './index.module.css';

const valuePoints = [
  {
    title: 'Your schema, your graph',
    body: 'You define the entity types, relation types, and valid patterns. One schema guides extraction, validation, and storage.',
  },
  {
    title: 'Local first, LLM when needed',
    body: 'A local model runs the first extraction pass. A typed LLM call runs only when that result is weak.',
  },
  {
    title: 'Answers with evidence',
    body: 'An agent plans, retrieves in parallel, checks coverage, and returns an answer with citation keys.',
  },
];

// Each pull request that adds a section adds its card here, so every link resolves.
const paths = [
  {
    title: 'Get started',
    body: 'Learn what agrag does and how the parts fit together.',
    to: '/get-started/introduction',
  },
  {
    title: 'Guides',
    body: 'Follow a task from start to finish, such as ingesting documents.',
    to: '/guides/ingest-documents',
  },
  {
    title: 'API reference',
    body: 'Look up every public class and function.',
    to: '/api',
  },
];

const ingestFlow = `flowchart LR
    A[Documents] --> B[Chunks] --> C[Entities and relations] --> D[Resolved graph] --> E[Graph and vector indexes]`;

const queryFlow = `flowchart LR
    Q[Question] --> P[Plan] --> R[Retrieve in parallel] --> V[Verify] --> X[Cited answer]`;

export default function Home() {
  return (
    <Layout
      title="Build a knowledge graph from your documents"
      description="agrag builds a typed knowledge graph from your documents. An agent plans, researches, and verifies each answer, and cites its sources.">
      <header className={styles.hero}>
        <div className="container">
          <h1 className={styles.title}>
            Build a knowledge graph from your documents. Then ask it questions.
          </h1>
          <p className={styles.pitch}>
            agrag builds a typed knowledge graph from your files. An agent then
            plans, researches, and verifies each answer, and cites its sources.
          </p>
          <div className={styles.install}>
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
          <div className={styles.scroll}>
            <img
              className={styles.banner}
              src={useBaseUrl('/img/hero-banner.webp')}
              width="2400"
              height="1000"
              alt="Pipeline from sources through load and chunk, extract, and resolve into graph and vector stores, then retrieve, plan, research, verify, and a cited answer."
            />
          </div>
        </div>
      </header>
      <main>
        <section className={styles.section}>
          <div className={`container ${styles.grid}`}>
            {valuePoints.map(({title, body}) => (
              <div key={title}>
                <h2 className={styles.h2}>{title}</h2>
                <p>{body}</p>
              </div>
            ))}
          </div>
        </section>
        <section className={styles.section}>
          <div className="container">
            <h2 className={styles.h2}>How it works</h2>
            <p className={styles.lead}>
              Ingestion turns documents into a graph. A query reads that graph back.
            </p>
            <h3 className={styles.h3}>Ingest: documents to graph</h3>
            <div className={styles.scroll}>
              <Mermaid value={ingestFlow} />
            </div>
            <h3 className={styles.h3}>Query: question to answer</h3>
            <div className={styles.scroll}>
              <Mermaid value={queryFlow} />
            </div>
            <p className={styles.lead}>Both flows use the same graph and vector indexes.</p>
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
        <section className={`${styles.section} ${styles.cta}`}>
          <div className="container">
            <h2 className={styles.h2}>Ready to try it?</h2>
            <Link className="button button--primary button--lg" to="/get-started/introduction">
              Get started
            </Link>
          </div>
        </section>
      </main>
    </Layout>
  );
}
