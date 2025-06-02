// @ts-check

module.exports = {
  title: 'Crawl4AI RAG Documentation',
  tagline: 'Comprehensive docs for MCP Crawl4AI RAG',
  url: 'https://your-domain.com',
  baseUrl: '/',
  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'warn',
  favicon: 'img/favicon.ico',
  organizationName: 'your-org',
  projectName: 'mcp-crawl4ai-rag',
  presets: [
    [
      '@docusaurus/preset-classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          path: 'docs',
          routeBasePath: '/',
          sidebarPath: require.resolve('./sidebars.js'),
          editUrl: 'https://github.com/your-org/mcp-crawl4ai-rag/edit/feature/docusauraus/',
        },
        blog: false,
        theme: {
          customCss: require.resolve('./src/css/custom.css'),
        },
      }),
    ],
  ],
  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      navbar: {
        title: 'Crawl4AI RAG Docs',
        logo: {
          alt: 'Logo',
          src: 'img/logo.svg',
        },
        items: [
          { to: '/', label: 'Getting Started', position: 'left' },
          { to: '/server', label: 'Server', position: 'left' },
          { to: '/api-reference', label: 'API', position: 'left' },
          { to: '/mcp-reference', label: 'MCP', position: 'left' },
          { to: '/tasks', label: 'Tasks', position: 'left' },
          { to: '/rag', label: 'RAG', position: 'left' },
          { to: '/ui', label: 'UI', position: 'left' },
          { to: '/testing', label: 'Testing', position: 'left' },
          { to: '/deployment', label: 'Deployment', position: 'left' },
          {
            href: 'https://github.com/your-org/mcp-crawl4ai-rag',
            label: 'GitHub',
            position: 'right',
          },
        ],
      },
      footer: {
        style: 'dark',
        links: [
          {
            title: 'Docs',
            items: [
              { label: 'Getting Started', to: '/' },
              { label: 'Server', to: '/server' },
              { label: 'API Reference', to: '/api-reference' },
            ],
          },
          {
            title: 'Community',
            items: [
              { label: 'GitHub', href: 'https://github.com/your-org/mcp-crawl4ai-rag' },
            ],
          },
        ],
        copyright: `Copyright © ${new Date().getFullYear()} Your Org`,
      },
    }),
};
