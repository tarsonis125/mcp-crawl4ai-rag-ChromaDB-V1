// @ts-check

/** @type {import('@docusaurus/types').Config} */
export default {
  title: 'Archon',
  tagline: 'Knowledge Engine for AI Coding Assistants',
  url: 'https://your-domain.com',
  baseUrl: '/',
  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'warn',
  favicon: 'img/favicon.ico',
  organizationName: 'your-org',
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
          editUrl: 'https://github.com/your-org/archon/edit/main/docs/',
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
            href: 'https://github.com/your-org/archon',
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
              { label: 'GitHub', href: 'https://github.com/your-org/archon' },
              { label: 'Issues', href: 'https://github.com/your-org/archon/issues' },
            ],
          },
        ],
        copyright: `Copyright © ${new Date().getFullYear()} Archon Project`,
      },
    }),
};
