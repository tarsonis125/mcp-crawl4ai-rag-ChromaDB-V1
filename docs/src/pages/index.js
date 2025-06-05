import React from 'react';
import clsx from 'clsx';
import Layout from '@theme/Layout';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import styles from './index.module.css';
import { 
  Database, 
  Zap, 
  Plug, 
  FileText, 
  Globe, 
  CheckSquare 
} from 'lucide-react';

function HomepageHeader() {
  const {siteConfig} = useDocusaurusContext();
  return (
    <header className={clsx('hero hero--primary', styles.heroBanner)}>
      <div className="container">
        <div className={styles.heroContent}>
          <h1 className="hero__title">{siteConfig.title}</h1>
          <p className="hero__subtitle">Supercharge your AI development workflow. Plug Cursor, Windsurf, or any AI IDE into Archon to unlock instant access to your business knowledge, technical docs, project requirements, and development tasks.</p>
          <div className={styles.buttons}>
            <Link
              className="button button--green-neon button--lg"
              to="/getting-started">
              Get Started - Quick Setup ⚡
            </Link>
          </div>
        </div>
      </div>
    </header>
  );
}

function HomepageContent() {
  const features = [
    {
      title: 'Knowledge Management',
      icon: Database,
      description: 'Intelligently crawl documentation sites, upload PDFs and documents, and organize knowledge by type (technical vs business). Advanced source filtering enables precise RAG queries across your entire knowledge base.'
    },
    {
      title: 'Advanced RAG Capabilities', 
      icon: Zap,
      description: 'Smart URL detection, contextual embeddings, hybrid search, and reranking deliver superior search results. Special handling for code snippets and technical documentation with AI-powered content understanding.'
    },
    {
      title: 'MCP Integration',
      icon: Plug,
      description: 'Universal compatibility with Cursor, Windsurf, Claude Desktop, and any MCP client. Dual transport support (SSE/stdio) with real-time access to your knowledge base directly from your AI coding assistants.'
    },
    {
      title: 'Document Processing',
      icon: FileText,
      description: 'Dual-engine PDF extraction, Word document support, markdown processing, and smart chunking. AI-generated metadata and automatic code example extraction for comprehensive document understanding.'
    },
    {
      title: 'Web Interface',
      icon: Globe,
      description: 'Complete web dashboard for MCP server management, document upload, crawling operations, and interactive knowledge chat. Real-time log streaming and progress tracking for all operations.'
    },
    {
      title: 'Task Management',
      icon: CheckSquare,
      description: 'Integrated project and task management with AI agent integration. Create, track, and organize development tasks with automatic linking to relevant documentation and code examples.'
    }
  ];

  return (
    <main>
      <section className={styles.architectureSection}>
        <div className="container">
          <div className="row">
            <div className="col col--12">
              <h2 className="text--center">🎯 How Archon Supercharges Your IDE</h2>
              <p className="text--center" style={{ fontSize: '1.2rem', marginBottom: '3rem', color: '#e5e7eb' }}>
                Connect any MCP-compatible IDE to unlock instant access to your entire knowledge ecosystem
              </p>
              
              <div className={styles.diagramContainer}>
                <div className={styles.archonDiagram}>
                  <div className="row">
                    <div className="col col--12 text--center">
                      <div className={styles.diagramNode} style={{ background: 'linear-gradient(135deg, #1a1a2e 0%, #16a085 100%)', marginBottom: '2rem' }}>
                        <h3>🎯 AI Development IDEs</h3>
                        <div className="row">
                          <div className="col col--3">
                            <div className={styles.ideBox}>🎯 Cursor<br/>AI-First IDE</div>
                          </div>
                          <div className="col col--3">
                            <div className={styles.ideBox}>🏄 Windsurf<br/>AI-Enhanced</div>
                          </div>
                          <div className="col col--3">
                            <div className={styles.ideBox}>📝 VS Code<br/>Extensions</div>
                          </div>
                          <div className="col col--3">
                            <div className={styles.ideBox}>🔌 Any MCP Client<br/>Compatible IDE</div>
                          </div>
                        </div>
                      </div>
                      
                      <div className={styles.connectionArrow}>⬇️ MCP Protocol ⬇️</div>
                      
                      <div className={styles.diagramNode} style={{ background: 'linear-gradient(135deg, #0f3460 0%, #a855f7 100%)', margin: '2rem 0' }}>
                        <h3>🏛️ ARCHON Knowledge Engine</h3>
                        <p>MCP Server • Knowledge Engine • Real-time Access</p>
                      </div>
                      
                      <div className={styles.connectionArrow}>⬇️ Powers Two Main Systems ⬇️</div>
                      
                      <div className="row" style={{ marginTop: '2rem' }}>
                        <div className="col col--6">
                          <div className={styles.diagramNode} style={{ background: 'linear-gradient(135deg, #16213e 0%, #3b82f6 100%)' }}>
                            <h3>📚 Knowledge Sources</h3>
                            <div className={styles.featureList}>
                              <div>🌐 Crawl Websites</div>
                              <div>📄 Upload Documents</div>
                              <div>⚡ Advanced RAG</div>
                              <div>🔍 Semantic Search</div>
                            </div>
                          </div>
                        </div>
                        <div className="col col--6">
                          <div className={styles.diagramNode} style={{ background: 'linear-gradient(135deg, #1a1a2e 0%, #ec4899 100%)' }}>
                            <h3>📋 Project Intelligence</h3>
                            <div className={styles.featureList}>
                              <div>📋 PRD Management</div>
                              <div>🎯 Feature Planning</div>
                              <div>📊 Data Architecture</div>
                              <div>✅ Task Management</div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              
              <div className="row" style={{ marginTop: '3rem' }}>
                <div className="col col--6">
                  <div className={styles.powerFeature}>
                    <h3>🚀 Instant Knowledge Access</h3>
                    <p>
                      Your AI assistant gets immediate access to crawled documentation, uploaded files, and semantic search across your entire knowledge base. No more context switching or manual file hunting.
                    </p>
                  </div>
                </div>
                <div className="col col--6">
                  <div className={styles.powerFeature}>
                    <h3>⚡ Project Intelligence</h3>
                    <p>
                      Automatically link development tasks to relevant documentation, PRDs, and feature plans. Your AI understands your project context and can make intelligent suggestions.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.features}>
        <div className="container">
          <h2 className="text--center margin-bottom--xl">✨ Key Features</h2>
          <div className="row">
            {features.map((feature, idx) => {
              const IconComponent = feature.icon;
              return (
                <div key={idx} className="col col--4">
                  <div className={styles.glassContainer}>
                    <div className="text--center">
                      <IconComponent 
                        size={48} 
                        className={styles.featureIcon}
                      />
                      <h3>{feature.title}</h3>
                      <p>{feature.description}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <section className={styles.quickStart}>
        <div className="container">
          <div className="row">
            <div className="col col--8 col--offset-2">
              <h2>🚀 Quick Start</h2>
              <p>Ready to get started? Follow our comprehensive setup guide:</p>
              <div className="text--center">
                <Link
                  className="button button--green-neon button--lg"
                  to="/getting-started">
                  👉 Getting Started Guide - Complete setup from installation to first knowledge base
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.nextSteps}>
        <div className="container">
          <div className="row">
            <div className="col col--8 col--offset-2">
              <h2>🎯 Next Steps</h2>
              <ol>
                <li><strong><Link to="/getting-started">Set up Archon</Link></strong> - Get your knowledge engine running</li>
                <li><strong><Link to="/mcp-reference">Connect your AI client</Link></strong> - Integrate with Cursor, Windsurf, or Claude Desktop</li>
                <li><strong><Link to="/getting-started#building-your-knowledge-base">Build your knowledge base</Link></strong> - Start crawling and uploading content</li>
                <li><strong><Link to="/rag">Optimize for your use case</Link></strong> - Configure RAG strategies</li>
                <li><strong><Link to="/deployment">Deploy to production</Link></strong> - Scale for team or enterprise use</li>
              </ol>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.callToAction}>
        <div className="container">
          <div className="row">
            <div className="col col--8 col--offset-2 text--center">
              <hr />
              <p><strong>Transform your AI coding experience with Archon</strong> - <em>Build once, query everywhere</em></p>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}

export default function Home() {
  const {siteConfig} = useDocusaurusContext();
  return (
    <Layout
      title={`${siteConfig.title} - Knowledge Engine`}
      description="MCP server for web crawling and document management with RAG capabilities for AI coding assistants">
      <HomepageHeader />
      <HomepageContent />
    </Layout>
  );
}
