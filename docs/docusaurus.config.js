// @ts-check

/** @type {import('@docusaurus/types').DocusaurusConfig} */
module.exports = {
  title: 'Archon',
  tagline: 'Knowledge Engine for AI Coding Assistants',
  url: 'https://your-domain.com',
  baseUrl: '/',
  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'warn',
  favicon: 'img/favicon.ico',
  organizationName: 'your-org',
  projectName: 'archon',
  presets: [
    [
      '@docusaurus/preset-classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          path: 'docs',
          routeBasePath: '/',
          sidebarPath: require.resolve('./sidebars.js'),
          editUrl: 'https://github.com/your-org/archon/edit/main/docs/',
        },
        blog: false,
        theme: {
          customCss: require.resolve('./src/css/custom.css'),
        },
      }),
    ],
  ],
  themeConfig: {
    colorMode: {
      defaultMode: 'dark',
      disableSwitch: true,
      respectPrefersColorScheme: false,
    },
    navbar: {
      title: 'Archon',
      logo: {
        alt: 'Archon Logo',
        src: 'img/logo-neon.svg',
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
          href: 'https://github.com/your-org/archon',
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
            { label: 'GitHub', href: 'https://github.com/your-org/archon' },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} Archon Project`,
    },
  },
};
