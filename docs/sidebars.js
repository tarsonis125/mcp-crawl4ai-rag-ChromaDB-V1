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
    
    // CORE FEATURES
    {
      type: 'category',
      label: 'Features',
      items: [
        'projects-overview',
        'knowledge-overview',
      ],
    },
    
    // REFERENCE SECTION
    {
      type: 'category',
      label: 'Reference',
      items: [
        'architecture',
        'server-overview',
        'server-services',
        'api-reference',
        'mcp-server',
        'websockets',
        'testing',
      ],
    },
    
    // GUIDES
    {
      type: 'category',
      label: 'Guides',
      items: [
        'ui',
        'agents-overview',
        'server-monitoring',
      ],
    },
  ],
};
