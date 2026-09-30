// @ts-check
// `@type` JSDoc annotations allow editor autocompletion and type checking
// (when paired with `@ts-check`).
// There are various equivalent ways to declare your Docusaurus config.
// See: https://docusaurus.io/docs/api/docusaurus-config

import {themes as prismThemes} from 'prism-react-renderer';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

// Preview deploys override the base URL with the BASE_URL env var (e.g. BASE_URL=/).
const baseUrl = process.env.BASE_URL ?? '/agentic-graphrag/';

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'Agentic GraphRAG',
  tagline: 'Build a knowledge graph from your documents, then ask it questions',
  favicon: 'img/favicon.ico',

  future: {
    v4: true, // Improve compatibility with the upcoming Docusaurus v4
  },

  // Served at https://ontogr.github.io/agentic-graphrag/
  // baseUrl defaults to /agentic-graphrag/ for production (GitHub Pages);
  // preview deploys override it with the BASE_URL env var (e.g. BASE_URL=/).
  url: 'https://ontogr.github.io',
  baseUrl,

  organizationName: 'ontogr',
  projectName: 'agentic-graphrag',

  onBrokenLinks: 'throw',

  headTags: [
    {
      tagName: 'link',
      attributes: {rel: 'apple-touch-icon', href: `${baseUrl}img/apple-touch-icon.png`},
    },
  ],

  markdown: {
    mermaid: true,
  },

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          path: 'docs',
          routeBasePath: '/',
          sidebarPath: './sidebars.js',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      }),
    ],
  ],

  themes: [
    '@docusaurus/theme-mermaid',
    [
      '@easyops-cn/docusaurus-search-local',
      /** @type {import('@easyops-cn/docusaurus-search-local').PluginOptions} */
      ({
        hashed: true,
        docsRouteBasePath: '/',
        indexBlog: false,
        language: ['en'],
      }),
    ],
  ],

  plugins: [
    [
      'docusaurus-plugin-llms',
      {
        title: 'Agentic GraphRAG',
        description:
          'Build a knowledge graph from your documents, then ask it questions with an agent that cites its evidence.',
        // The generated API pages are large and add little for a language model.
        ignoreFiles: ['api/**'],
      },
    ],
  ],

  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      image: 'img/social-card.png',
      colorMode: {
        respectPrefersColorScheme: true,
      },
      mermaid: {
        theme: {light: 'neutral', dark: 'dark'},
      },
      navbar: {
        title: 'Agentic GraphRAG',
        logo: {alt: 'Agentic GraphRAG logo', src: 'img/logo.svg'},
        items: [
          {type: 'docSidebar', sidebarId: 'startSidebar', position: 'left', label: 'Get Started'},
          {type: 'docSidebar', sidebarId: 'guidesSidebar', position: 'left', label: 'Guides'},
          {type: 'docSidebar', sidebarId: 'referenceSidebar', position: 'left', label: 'Reference'},
          {type: 'search', position: 'right'},
          {
            href: 'https://github.com/ontogr/agentic-graphrag',
            label: 'GitHub',
            position: 'right',
          },
          {
            href: 'https://pypi.org/project/agentic-graphrag/',
            label: 'PyPI',
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
              {label: 'Introduction', to: '/get-started/introduction'},
              {label: 'Guides', to: '/guides/ingest-documents'},
              {label: 'API Reference', to: '/api'},
            ],
          },
          {
            title: 'Project',
            items: [
              {label: 'GitHub', href: 'https://github.com/ontogr/agentic-graphrag'},
              {label: 'PyPI', href: 'https://pypi.org/project/agentic-graphrag/'},
              {
                label: 'Issues',
                href: 'https://github.com/ontogr/agentic-graphrag/issues',
              },
            ],
          },
        ],
      },
      prism: {
        theme: prismThemes.github,
        darkTheme: prismThemes.dracula,
      },
    }),
};

export default config;
