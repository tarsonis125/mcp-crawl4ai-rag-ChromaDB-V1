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
      // Proper Mermaid configuration according to official docs
      mermaid: {
        theme: 'base',
        options: {
          darkMode: true,
          themeVariables: {            
            // Primary colors - Purple neon theme
            primaryColor: '#1f2937',
            primaryTextColor: '#ffffff', 
            primaryBorderColor: '#a855f7',
            
            // Secondary colors
            secondaryColor: '#374151',
            secondaryTextColor: '#ffffff',
            secondaryBorderColor: '#a855f7',
            
            // Tertiary colors  
            tertiaryColor: '#4b5563',
            tertiaryTextColor: '#ffffff',
            tertiaryBorderColor: '#a855f7',
            
            // Background and main colors
            background: '#111827',
            mainBkg: '#1f2937',
            
            // Lines and text
            lineColor: '#a855f7',
            textColor: '#ffffff',
            
            // Font configuration
            fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            fontSize: '14px',
            
            // Flowchart specific variables
            nodeBorder: '#a855f7',
            clusterBkg: '#374151',
            clusterBorder: '#a855f7',
            defaultLinkColor: '#a855f7',
            edgeLabelBackground: '#111827',
            nodeTextColor: '#ffffff',
            
            // Sequence diagram specific
            actorBkg: '#1f2937',
            actorBorder: '#a855f7',
            actorTextColor: '#ffffff',
            
            // Class diagram
            classText: '#ffffff',
            
            // State diagram
            labelColor: '#ffffff',
          }
        },
      },
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
