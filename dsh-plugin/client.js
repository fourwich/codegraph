window.__ModuleLoader__.load({
  id: `dsh-codegraph`,
  factory: require => {
    var module = { exports: {} };
    var exports = module.exports;
    Object.defineProperty(exports, Symbol.toStringTag, { value: `Module` });

    const react = require(`react`);

    /** The question the button puts on the clipboard. */
    function whyQuestion(code) {
      const text = typeof code === `string` ? code : ``;
      const lines = text === `` ? 0 : text.split(`\n`).length;
      const subject = lines > 1 ? `block of code` : `line`;
      const body = text === `` ? `` : `\n\n\`\`\`\n${text}\n\`\`\`\n`;
      return (
        `Why is this ${subject} written this way?`
        + `${body}\nUse codegraph_why with the path:line, and show the decision card.`
      );
    }

    /**
     * Wrap a rendered code fence with a copy-the-question button.
     *
     * A `kind: 'hoc'` contribution is an ordinary component: the renderer calls it
     * with the default renderer in `children`, so this wraps that child rather than
     * re-implementing the fence.
     *
     * The button copies instead of sending because DSH publishes no way to write into
     * the composer from a slot — the `setDraft` occurrences inside other plugins are
     * their own React state, not a service. Copy plus a clear prompt is the honest
     * ceiling for this surface.
     */
    function CodeFenceLayer(props) {
      const { code, children } = props;
      const [notice, setNotice] = react.useState(null);
      const [hover, setHover] = react.useState(false);

      const onClick = react.useCallback(
        async event => {
          event.preventDefault();
          event.stopPropagation();
          try {
            await navigator.clipboard.writeText(whyQuestion(code));
            setNotice(`已复制 — 粘贴到输入框发送`);
          } catch {
            setNotice(`复制失败 — 手动选中代码 Ctrl+C`);
          }
          setTimeout(() => setNotice(null), 4000);
        },
        [code],
      );

      return react.createElement(
        `div`,
        {
          style: {
            display: `flex`,
            flexDirection: `column`,
            alignItems: `flex-start`,
            gap: `4px`,
          },
        },
        react.createElement(
          `button`,
          {
            type: `button`,
            title: `复制「为什么这样写」的提问`,
            onClick,
            onMouseEnter: () => setHover(true),
            onMouseLeave: () => setHover(false),
            style: {
              padding: `2px 10px`,
              fontSize: `11px`,
              lineHeight: `18px`,
              borderRadius: `4px`,
              border: `1px solid var(--dsw-alias-border-l2, #d0d0d0)`,
              background: hover
                ? `var(--dsw-alias-interactive-bg-hover, #f0f0f0)`
                : `var(--dsw-alias-bg-module-platform, #ffffff)`,
              color: `var(--dsw-alias-label-secondary, #555555)`,
              cursor: `pointer`,
              transition: `background 120ms`,
              fontFamily: `inherit`,
            },
          },
          notice ?? `Why?`,
        ),
        children,
      );
    }

    /** Slot name the chat view declares for code fences. */
    const SLOT = `conversation.chat.markdown.fence`;

    /**
     * Register the fence layer.
     *
     * `inject` declares `slots` because cordis refuses a service read that was not
     * declared — the failure is a silent `cannot get property "slots" without inject`
     * that leaves the fiber inactive and `apply` never running.
     */
    function apply(ctx) {
      if (ctx.slots === undefined) return;

      ctx.slots.inject(SLOT, () => {
        try {
          return ctx.slots.register(
            { name: SLOT, id: `codegraph.why-fence`, order: 1000 },
            CodeFenceLayer,
          );
        } catch {
          return () => {};
        }
      });
    }

    const inject = [`slots`];

    module.exports.apply = apply;
    module.exports.inject = inject;
    return module.exports;
  },
});
