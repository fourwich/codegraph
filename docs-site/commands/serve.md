# codegraph serve

Start the local Cytoscape visualizer.

```bash
codegraph serve [--port 8080] [--no-open-browser]
```

Time slider, scope filter, node-kind and decision-status filters, and decision cards.
The slider offers the dates that actually have node versions inside the current
scope, and the scope filter matches on path boundaries — a scope with no
decisions says so rather than showing decisions from elsewhere.
Keyboard: R / F / Esc.
