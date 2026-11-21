window.__ModuleLoader__.load({
  id: `dsh-codegraph`,
  factory: require => {
    var module = { exports: {} };
    var exports = module.exports;
    Object.defineProperty(exports, Symbol.toStringTag, { value: `Module` });

    const react = require(`react`);

    /**
     * Menu kind this plugin owns.
     *
     * DSH defines no `code` or `selection` menu kind, so a wrapper and its rows have
     * to agree on one. The registry publishes a kind automatically when the first
     * provider registers for it, so nothing else needs declaring.
     */
    const MENU_KIND = `codegraph-code`;

    /** Inserted by the slash entry; the user replaces the placeholder line. */
    const SLASH_TEMPLATE = `Why is this line written this way? path/to/file.py:42`;

    /**
     * Wrap a rendered code fence so right-clicking offers an "ask why" row.
     *
     * The fence slot is `kind: 'hoc'`: a contribution receives the default renderer
     * as `children` and returns a component that renders it. Wrapping rather than
     * re-implementing keeps syntax highlighting and streaming behaviour intact.
     */
    function CodeFenceWithWhy(props) {
      const { code, lang, children, useContextMenu } = props;

      // The trigger captures this object; a memo keeps its identity stable across
      // renders so the menu target does not change every frame.
      const target = react.useMemo(
        () => ({
          kind: MENU_KIND,
          value: {
            code: typeof code === `string` ? code : ``,
            lang: typeof lang === `string` ? lang : ``,
          },
        }),
        [code, lang],
      );

      // Outside a context-menu host the fence must still render untouched.
      if (typeof useContextMenu !== `function`) return children ?? null;
      const bindings = useContextMenu();
      if (bindings === undefined || bindings === null) return children ?? null;

      const triggerProps = bindings.getTriggerProps(target);
      return react.createElement(`div`, triggerProps, children);
    }

    /** Turn the default fence renderer into the wrapped one. */
    function fenceHoc(Render) {
      return function WrappedFence(props) {
        return react.createElement(
          CodeFenceWithWhy,
          props,
          react.createElement(Render, props),
        );
      };
    }

    /**
     * One menu row for every code fence.
     *
     * `resolve` runs when a menu opens for a fence; the row's `run` receives the
     * captured target, which carries the fence text.
     */
    function whyMenuProvider() {
      return {
        id: `codegraph.why`,
        target: MENU_KIND,
        order: 100,
        async resolve(target, signal) {
          if (signal?.aborted) return [];
          const code = target?.value?.code ?? ``;
          const lang = target?.value?.lang ?? ``;
          const lines = code === `` ? 0 : code.split(`\n`).length;
          return [
            {
              id: `ask-why`,
              label: `Ask why this code is written this way`,
              // An empty fence has nothing to ask about; disable rather than fail
              // after the click.
              disabled: lines === 0,
              run: async () => {
                const note =
                  lines === 0
                    ? `Why is this code written this way?`
                    : `Why is this ${lang || `code`} written this way? (${lines} line${lines === 1 ? `` : `s`})`;
                try {
                  await navigator.clipboard?.writeText?.(note);
                } catch {
                  // Clipboard permission is optional; the row still closes.
                }
              },
            },
          ];
        },
      };
    }

    /** Slash source that inserts a location template. */
    function buildWhySource() {
      return {
        trigger: `/`,
        name: `why`,
        order: 5,

        async candidates(_session, { query, signal }) {
          if (signal?.aborted) return [];
          const needle = String(query ?? ``).trim().toLowerCase();
          if (needle.length > 0 && !`why`.startsWith(needle)) return [];
          return [
            {
              name: `why`,
              description: `Ask why a line of code exists, from the repository's own decision records`,
              value: `/why`,
            },
          ];
        },

        onPick({ candidate }) {
          return {
            insert: {
              source: `why`,
              ref: candidate?.value ?? `/why`,
              label: `/why`,
              appearance: `file`,
              clipboardText: SLASH_TEMPLATE,
            },
          };
        },

        codec: {
          clipboardText: () => SLASH_TEMPLATE,
          serialize: ref => Promise.resolve(ref),
        },
      };
    }

    /**
     * Install both contributions.
     *
     * Every step degrades independently: a deployment with slots but no context menu
     * still gets the slash entry, and one with neither still renders fences.
     */
    function apply(ctx) {
      // A DOM marker is the only observable channel the renderer offers: a browser
      // module has no filesystem. Reading `document.documentElement.dataset.codegraph`
      // in DevTools answers "did the client bundle load and run" without guessing.
      try {
        if (typeof document !== `undefined`) {
          document.documentElement.dataset.codegraph = `applied`;
          const services = [`slots`, `contextMenus`, `inputTriggers`].filter(name => {
            const value = typeof ctx.get === `function` ? ctx.get(name) : undefined;
            return value !== undefined && value !== null;
          });
          document.documentElement.dataset.codegraphServices = services.join(`,`);
        }
      } catch {
        // A missing document means a non-browser host; nothing to mark.
      }

      const get = typeof ctx.get === `function` ? ctx.get.bind(ctx) : () => undefined;
      const effect = typeof ctx.effect === `function` ? ctx.effect.bind(ctx) : fn => fn();

      if (ctx.slots !== undefined) {
        ctx.slots.inject?.(`conversation.chat.markdown.fence`, () =>
          ctx.slots.register(
            {
              name: `conversation.chat.markdown.fence`,
              id: `codegraph.why-fence`,
              // Above the built-in math/diff/patch layers, which key on a language.
              order: 1000,
            },
            fenceHoc,
          ),
        );
      }

      const menus = get(`contextMenus`);
      if (menus !== undefined && menus !== null) {
        effect(() => menus.register(whyMenuProvider()), `codegraph: fence menu`);
      }

      const inputTriggers = get(`inputTriggers`);
      if (inputTriggers !== undefined && inputTriggers !== null) {
        effect(() => {
          const unregister = inputTriggers.registerSource(buildWhySource());
          return () => {
            unregister();
          };
        }, `codegraph: /why source`);
      }
    }

    const inject = [
      `@deepseek-ai/dsh-client-ui-chat`,
      `@deepseek-ai/dsh-client-ui-context-menu`,
      `@deepseek-ai/dsh-client-ui-input-trigger`,
      `@deepseek-ai/dsh-client-locale`,
    ];

    exports.apply = apply;
    exports.inject = inject;
    return module.exports;
  },
});
