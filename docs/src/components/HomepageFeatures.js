import React from 'react';
import clsx from 'clsx';
import styles from './HomepageFeatures.module.css';

const FeatureList = [
  {
    title: 'Knowledge Management',
    Svg: require('../../static/img/knowledge-icon.svg').default,
    description: (
      <>
        Intelligently crawl documentation sites, upload PDFs and documents, and organize knowledge 
        by type (technical vs business). Advanced source filtering enables precise RAG queries 
        across your entire knowledge base.
      </>
    ),
  },
  {
    title: 'Advanced RAG Capabilities',
    Svg: require('../../static/img/rag-icon.svg').default,
    description: (
      <>
        Smart URL detection, contextual embeddings, hybrid search, and reranking deliver 
        superior search results. Special handling for code snippets and technical documentation 
        with AI-powered content understanding.
      </>
    ),
  },
  {
    title: 'MCP Integration',
    Svg: require('../../static/img/mcp-logo.svg').default,
    description: (
      <>
        Universal compatibility with Cursor, Windsurf, Claude Desktop, and any MCP client. 
        Dual transport support (SSE/stdio) with real-time access to your knowledge base 
        directly from your AI coding assistants.
      </>
    ),
  },
  {
    title: 'Document Processing',
    Svg: require('../../static/img/document-processing-icon.svg').default,
    description: (
      <>
        Dual-engine PDF extraction, Word document support, markdown processing, and 
        smart chunking. AI-generated metadata and automatic code example extraction 
        for comprehensive document understanding.
      </>
    ),
  },
  {
    title: 'Web Interface',
    Svg: require('../../static/img/web-interface-icon.svg').default,
    description: (
      <>
        Complete web dashboard for MCP server management, document upload, crawling operations, 
        and interactive knowledge chat. Real-time log streaming and progress tracking 
        for all operations.
      </>
    ),
  },
  {
    title: 'Task Management',
    Svg: require('../../static/img/task-management-icon.svg').default,
    description: (
      <>
        Integrated project and task management with AI assistant integration. 
        Create, track, and organize development tasks with automatic linking to 
        relevant documentation and code examples.
      </>
    ),
  },
];

function Feature({Svg, title, description}) {
  return (
    <div className={clsx('col col--4')}>
      <div className="text--center">
        <Svg className={styles.featureSvg} alt={title} />
      </div>
      <div className="text--center padding-horiz--md">
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
    </div>
  );
}

export default function HomepageFeatures() {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
