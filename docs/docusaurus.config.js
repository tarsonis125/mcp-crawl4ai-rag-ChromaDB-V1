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
      // Mermaid diagram theming - Glass morphism neon style
      mermaid: {
        theme: {
          light: 'base', 
          dark: 'base'
        },
        options: {
          themeVariables: {
            // Primary colors - Purple neon theme
            primaryColor: '#8b5cf6',
            primaryTextColor: '#ffffff',
            primaryBorderColor: '#a855f7',
            lineColor: '#a855f7',
            
            // Secondary colors
            secondaryColor: '#1f2937',
            secondaryTextColor: '#ffffff',
            secondaryBorderColor: '#6b7280',
            
            // Tertiary colors  
            tertiaryColor: '#111827',
            tertiaryTextColor: '#ffffff',
            tertiaryBorderColor: '#4b5563',
            
            // Background colors
            background: '#000000',
            mainBkg: 'rgba(17, 24, 39, 0.8)',
            secondBkg: 'rgba(31, 41, 55, 0.8)',
            tertiaryBkg: 'rgba(75, 85, 99, 0.6)',
            
            // Node colors
            nodeBkg: 'rgba(17, 24, 39, 0.8)',
            nodeTextColor: '#ffffff',
            nodeBorder: '#a855f7',
            
            // Cluster/subgraph colors
            clusterBkg: 'rgba(31, 41, 55, 0.6)',
            clusterBorder: '#8b5cf6',
            
            // Edge/arrow colors
            edgeLabelBackground: 'rgba(17, 24, 39, 0.9)',
            edgeLabelColor: '#ffffff',
            
            // Special element colors
            activeTaskBkgColor: '#8b5cf6',
            activeTaskBorderColor: '#a855f7',
            gridColor: 'rgba(139, 92, 246, 0.2)',
            section0: '#8b5cf6',
            section1: '#a855f7',
            section2: '#c084fc',
            
            // Git diagram colors
            git0: '#8b5cf6',
            git1: '#a855f7',
            git2: '#c084fc',
            git3: '#ddd6fe',
            gitBranchLabel0: '#ffffff',
            gitBranchLabel1: '#ffffff',
            gitBranchLabel2: '#ffffff',
            gitBranchLabel3: '#ffffff',
            
            // Journey diagram colors
            cScale0: '#8b5cf6',
            cScale1: '#a855f7',  
            cScale2: '#c084fc',
            cScaleLabel0: '#ffffff',
            cScaleLabel1: '#ffffff',
            cScaleLabel2: '#ffffff',
            
            // Flowchart colors
            flowchartNodeBkg: 'rgba(17, 24, 39, 0.8)',
            flowchartNodeBorder: '#a855f7',
            flowchartLinkColor: '#a855f7',
            flowchartInvLinkColor: '#8b5cf6',
            
            // Class diagram colors
            classText: '#ffffff',
            classBorderColor: '#a855f7',
            classBkgColor: 'rgba(17, 24, 39, 0.8)',
            
            // State diagram colors
            labelColor: '#ffffff',
            stateLabelColor: '#ffffff',
            stateBkg: 'rgba(17, 24, 39, 0.8)',
            stateBorder: '#a855f7',
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
