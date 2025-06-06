// @ts-check

/** @type {import('@docusaurus/types').Config} */
export default {
  title: 'Archon',
  tagline: 'Knowledge Engine for AI Coding Assistants',
  url: 'http://localhost:3838',
  baseUrl: '/',
  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'warn',
  favicon: 'img/favicon.svg',
  organizationName: 'archon',
  projectName: 'archon',
  
  markdown: {
    mermaid: true,
  },
  
  themes: ['@docusaurus/theme-mermaid'],
  
  presets: [
    [
      '@docusaurus/preset-classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          path: 'docs',
          routeBasePath: '/',
          sidebarPath: './sidebars.js', // Enable proper sidebar
          editUrl: 'https://github.com/coleam00/archon/edit/main/docs/',
          showLastUpdateTime: true,
          showLastUpdateAuthor: true,
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      }),
    ],
  ],
  
  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
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
          {
            href: 'https://github.com/coleam00/archon',
            label: 'GitHub',
            position: 'right',
          },
        ],
      },

      tableOfContents: {
        minHeadingLevel: 2,
        maxHeadingLevel: 4,
      },
      
      footer: {
        style: 'dark',
        links: [
          {
            title: 'Getting Started',
            items: [
              { label: 'Installation', to: '/getting-started' },
              { label: 'Quick Setup', to: '/getting-started#quick-start' },
              { label: 'Configuration', to: '/configuration' },
            ],
          },
          {
            title: 'API & Integration',
            items: [
              { label: 'API Reference', to: '/api-reference' },
              { label: 'MCP Integration', to: '/mcp-reference' },
              { label: 'Task Management', to: '/tasks' },
            ],
          },
          {
            title: 'User Interface',
            items: [
              { label: 'Web Interface', to: '/ui' },
              { label: 'Testing Guide', to: '/testing' },
              { label: 'Deployment', to: '/deployment' },
            ],
          },
          {
            title: 'Community',
            items: [
              { label: 'GitHub', href: 'https://github.com/coleam00/archon' },
              { label: 'Issues', href: 'https://github.com/coleam00/archon/issues' },
            ],
          },
        ],
        copyright: `Copyright © ${new Date().getFullYear()} Archon Project`,
      },
    }),
};
