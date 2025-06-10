module.exports = {
  docs: [
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
    {
      type: 'category',
      label: 'Core Features',
      items: [
        'server',
        'rag',
        'tasks',
        'websockets',
      ],
    },
    {
      type: 'category',
      label: 'MCP',
      items: [
        'mcp-overview',
        'mcp-server',
        'mcp-client',
      ],
    },
    {
      type: 'category',
      label: 'API Reference',
      items: [
        'api-reference',
      ],
    },
    {
      type: 'category',
      label: 'User Interface',
      items: [
        'ui',
        'testing',
      ],
    },
  ],
};
