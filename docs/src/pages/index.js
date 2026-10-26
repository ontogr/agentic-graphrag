import Layout from '@theme/Layout';
import Link from '@docusaurus/Link';
import useBaseUrl from '@docusaurus/useBaseUrl';
import ThemedImage from '@theme/ThemedImage';
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import CodeBlock from '@theme/CodeBlock';
import InstallCommand from '@site/src/components/InstallCommand';
import Diagram from '@site/src/components/Diagram';
import styles from './index.module.css';

const INSTALL = 'uv pip install agentic-graphrag --torch-backend=auto';

const pillars = [
  {
    tone: 'blue',
    title: 'Evidence you can cite',
    text: 'Documents become a graph shaped by your schema. Agents search it, read the exact passage behind each result, and cite it. A citation check flags any source the agent never read. Each passage keeps its source and location, a relation links to the passages that support it, and a citation to an older version of a document still leads to the text that was cited.',
  },
  {
    tone: 'green',
    title: 'Work that resumes',
    text: 'A task stores its goal, an ordered log of messages, tool calls, and tool results, and its named steps in the graph. A later run, even in another process, continues from the stored steps and reruns only the unfinished ones.',
  },
  {
    tone: 'amber',
    title: 'Decisions tied to their sources',
    text: 'A decision stores its conclusion, rationale, and assumptions with links to the passages, task events, and earlier decisions it relies on. When a cited document gets a new version, the decision is flagged for review, and the built-in agent leaves it out of its search for earlier decisions until a reviewer reaffirms, replaces, or rejects it.',
  },
  {
    tone: 'violet',
    title: 'Fits your stack',
    text: 'Use it from Python, run the built-in agent, or connect your own agent through MCP. It runs on Neo4j or FalkorDB, and vectors can live in the graph or in Qdrant, Milvus, or Weaviate.',
  },
];

const pythonCode = `graph = await Graph.open(
    schema="operations",
    graph_store=store,
    embedder=embedder,
    extraction_settings=ExtractionSettings(mode="gliner"),
    max_llm_pairs=0,
)
await graph.add(DOCUMENT)`;

const agentCode = `agent = build_agent(
    graph_store=store,
    embedder=embedder,
    scope=frozenset({str(DOCUMENT)}),
    project_id="my-project",
    agent_id="researcher",
    llm_settings=AgentLLMSettings.from_openai_compatible_env(),
)

result = await agent.ainvoke({
    "task_name": "first-question",
    "question": "What are the main points of this document? Cite your sources.",
})
print(result["answer"])`;

const mcpCode = `{
  "mcpServers": {
    "agrag": {
      "command": "agrag-mcp",
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": "your-neo4j-password",
        "MCP_SCOPE_DOCUMENT_KEYS": "/full/path/to/your-document.md",
        "MCP_PROJECT_ID": "my-project",
        "MCP_AGENT_ID": "researcher"
      }
    }
  }
}`;

const next = [
  {
    to: '/stable/guides/ingest-documents',
    title: 'Build the graph',
    text: 'Add documents, choose a schema, and extract and resolve entities.',
  },
  {
    to: '/stable/guides/find-and-cite-evidence',
    title: 'Search and cite',
    text: 'Search passages, read the exact text, and check the citations in an answer.',
  },
  {
    to: '/stable/concepts/conversation-history-and-decisions',
    title: 'History and decisions',
    text: 'Record tasks, events, steps, and decisions, and review decisions when a source changes.',
  },
  {
    to: '/stable/concepts/graph-storage',
    title: 'Choose storage',
    text: 'Compare Neo4j and FalkorDB, and decide where the vectors live.',
  },
];

export default function Home() {
  const graphImage = {
    light: useBaseUrl('/img/readme/context-graph.png'),
    dark: useBaseUrl('/img/readme/context-graph-dark.png'),
  };

  return (
    <Layout
      title="Context graphs for enterprise knowledge, conversation history, and decision traces"
      description="An open source framework that builds one graph connecting enterprise knowledge to agent conversations and decisions, so agents can find evidence, resume work, and review decisions when their sources change.">
      <header className={styles.hero}>
        <div className={`container ${styles.heroInner}`}>
          <div className={styles.heroText}>
            <h1 className={styles.title}>
              Context graphs that connect{' '}
              <span className={styles.blue}>enterprise knowledge</span>,{' '}
              <span className={styles.green}>conversation history</span>, and{' '}
              <span className={styles.amber}>decision traces</span>.
            </h1>
            <p className={styles.pitch}>
              Agentic GraphRAG is an open source framework that builds one graph connecting your enterprise knowledge to the conversations your agents have and the decisions they make.
            </p>
            <div className={`${styles.actions} ${styles.heroActions}`}>
              <InstallCommand command={INSTALL} />
              <div className={styles.buttons}>
                <Link className="button button--primary button--lg" to="/stable/get-started/quickstart">
                  Get started
                </Link>
                <Link
                  className="button button--secondary button--lg"
                  href="https://github.com/ontogr/agentic-graphrag">
                  View on GitHub
                </Link>
              </div>
            </div>
            <p className={styles.facts}>Python 3.11+ · Apache-2.0</p>
          </div>
          <div className={styles.heroImageWrap}>
            <ThemedImage
              className={styles.heroImage}
              sources={graphImage}
              alt="Three connected graph layers. Enterprise knowledge contains documents, sections, chunks, entities, and relations. Conversation history contains tasks, events, and steps. Decision traces link conclusions to document passages, task events, and other decisions."
            />
          </div>
        </div>
      </header>

      <main>
        <section className={styles.section}>
          <div className={`container ${styles.pillars}`}>
            {pillars.map(({tone, title, text}) => (
              <div key={title} className={`${styles.pillar} ${styles[`rule${tone}`]}`}>
                <h2>{title}</h2>
                <p>{text}</p>
              </div>
            ))}
          </div>
        </section>

        <section className={styles.section}>
          <div className="container">
            <div className={styles.sectionHead}>
              <h2>How it works</h2>
              <p>
                <Link to="/stable/concepts/ingestion">Ingestion</Link> loads, chunks, extracts, and resolves your documents into the graph. Agents and MCP clients search and read it, record their work, and return answers with checked sources.
              </p>
            </div>
            <Diagram
              className={styles.flow}
              name="full-flow"
              alt="Documents are loaded, chunked, extracted, and resolved into a graph with enterprise knowledge, conversation history, and decision traces. A changed document flags the decisions that cite it. An agent searches and reads the graph, records its events and steps, and returns an answer with checked numbered sources."
            />
          </div>
        </section>

        <section className={styles.section}>
          <div className="container">
            <div className={styles.sectionHead}>
              <h2>Three ways to use it</h2>
              <p>
                Use it from Python, run the built-in agent, or connect your own agent through MCP.
              </p>
            </div>
            <Tabs className={styles.tabs}>
              <TabItem value="python" label="Python library" default>
                <p className={styles.tabLead}>Read a document into the graph on your machine, with a schema you choose.</p>
                <CodeBlock language="python">{pythonCode}</CodeBlock>
              </TabItem>
              <TabItem value="agent" label="Built-in agent">
                <p className={styles.tabLead}>A task-scoped agent searches your documents, records its work, and answers with numbered sources.</p>
                <CodeBlock language="python">{agentCode}</CodeBlock>
              </TabItem>
              <TabItem value="mcp" label="MCP client">
                <p className={styles.tabLead}>Give an MCP client tools for search, citation, conversation history, and decision traces.</p>
                <CodeBlock language="json">{mcpCode}</CodeBlock>
              </TabItem>
            </Tabs>
          </div>
        </section>

        <section className={styles.section}>
          <div className="container">
            <div className={styles.sectionHead}>
              <h2>Where to go next</h2>
            </div>
            <ul className={styles.next}>
              {next.map(({to, title, text}) => (
                <li key={title}>
                  <Link to={to} className={styles.nextLink}>
                    <span className={styles.nextTitle}>{title}</span>
                    <span className={styles.nextText}>{text}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className={`${styles.section} ${styles.closing}`}>
          <div className="container">
            <h2>Install it and run the quickstart</h2>
            <div className={styles.actions}>
              <InstallCommand command={INSTALL} />
              <Link className="button button--primary button--lg" to="/stable/get-started/quickstart">
                Get started
              </Link>
            </div>
          </div>
        </section>
      </main>
    </Layout>
  );
}
