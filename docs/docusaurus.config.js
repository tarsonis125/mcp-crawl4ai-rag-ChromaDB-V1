/** @type {import('@docusaurus/types').DocusaurusConfig} */
module.exports = {
  title: 'mcp-crawl4ai-rag',
  url: 'https://your-domain.com',
  baseUrl: '/',
  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'warn',
  favicon: 'img/favicon.ico',
  themeConfig: {
    navbar: {
      title: 'mcp-crawl4ai-rag',
      items: [
        {to: 'docs/getting-started', label: 'Getting Started', position: 'left'},
        {to: 'docs/server', label: 'Server', position: 'left'},
        {to: 'docs/api-reference', label: 'API', position: 'left'},
        {to: 'docs/mcp-reference', label: 'MCP', position: 'left'},
        {to: 'docs/tasks', label: 'Tasks', position: 'left'},
        {to: 'docs/rag', label: 'RAG', position: 'left'},
        {to: 'docs/ui', label: 'UI', position: 'left'},
        {to: 'docs/testing', label: 'Testing', position: 'left'},
        {to: 'docs/deployment', label: 'Deployment', position: 'left'}
      ],
    },
  },
  presets: [
    ['@docusaurus/preset-classic', {
      docs: {sidebarPath: require.resolve('./docs/sidebars.js')},
      theme: {customCss: require.resolve('./src/css/custom.css')}
    }]
  ],
};
