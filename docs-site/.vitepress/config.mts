import { defineConfig } from "vitepress";

export default defineConfig({
  title: "CodeGraph",
  description: "Decision memory layer for your codebase",
  base: "/codegraph/",
  themeConfig: {
    name: "CodeGraph",
    nav: [
      { text: "Guide", link: "/guide/getting-started" },
      { text: "Commands", link: "/commands/" },
      { text: "GitHub", link: "https://github.com/fourwich/codegraph" },
    ],
    sidebar: [
      {
        text: "Guide",
        items: [
          { text: "Getting started", link: "/guide/getting-started" },
          { text: "Installation", link: "/guide/installation" },
          { text: "First index", link: "/guide/first-index" },
          { text: "Backends", link: "/guide/backends" },
        ],
      },
      {
        text: "Commands",
        items: [
          { text: "Overview", link: "/commands/" },
          { text: "index", link: "/commands/index" },
          { text: "why", link: "/commands/why" },
          { text: "graph", link: "/commands/graph" },
          { text: "decisions", link: "/commands/decisions" },
          { text: "conflicts", link: "/commands/conflicts" },
          { text: "export", link: "/commands/export" },
          { text: "serve", link: "/commands/serve" },
        ],
      },
      {
        text: "Concepts",
        items: [
          { text: "CodeNode", link: "/concepts/code-node" },
          { text: "Decision", link: "/concepts/decision" },
          { text: "Time travel", link: "/concepts/time-travel" },
        ],
      },
      {
        text: "Integrations",
        items: [
          { text: "VS Code", link: "/integrations/vscode" },
          { text: "Cursor / Copilot", link: "/integrations/cursor" },
          { text: "Ollama", link: "/integrations/ollama" },
        ],
      },
      {
        text: "Contributing",
        items: [
          { text: "Setup", link: "/contributing/setup" },
          { text: "Architecture", link: "/contributing/architecture" },
          { text: "Roadmap", link: "/contributing/roadmap" },
        ],
      },
    ],
  },
});
