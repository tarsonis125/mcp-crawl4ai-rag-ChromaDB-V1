module.exports = {
  docs: [
    // INTRO & GETTING STARTED
    {
      type: 'doc',
      id: 'intro',
      label: 'Introduction',
    },
    {
      type: 'category',
      label: 'Getting Started',
      items: [
        'getting-started',
        'configuration',
        'deployment',
      ],
    },
    
    // CORE FEATURES (feature-based perspective)
    {
      type: 'category',
      label: 'Core Features',
      items: [
        {
          type: 'category',
          label: '📊 Archon Projects',
          items: [
            'projects-overview',
            'projects-features',
          ],
        },
        {
          type: 'category',
          label: '🧠 Archon Knowledge',
          items: [
            'knowledge-overview',
            'knowledge-features',
          ],
        },
      ],
    },
    
    // REFERENCE SECTION (organized by containers)
    {
      type: 'category',
      label: 'Reference',
      items: [
        {
          type: 'category',
          label: '🌐 UI',
          items: [
            'ui',
            'websockets',
            'ui-components',
          ],
        },
        {
          type: 'category',
          label: '🏗️ Server',
          items: [
            'server-overview',
            'server-services',
            'api-reference',
            'server-deployment',
            'server-monitoring',
          ],
        },
        {
          type: 'category',
          label: '🔌 MCP',
          items: [
            'mcp-overview',
            'mcp-server',
            'mcp-tools',
          ],
        },
        {
          type: 'category',
          label: '⚙️ Agents',
          items: [
            'agents-overview',
            'agent-document',
            'agent-rag',
            'agent-task',
          ],
        },
      ],
    },
    
    // ADDITIONAL RESOURCES
    {
      type: 'category',
      label: 'Additional Resources',
      items: [
        'testing',
        'testing-python-strategy',
        'testing-vitest-strategy',
      ],
    },
  ],
};
