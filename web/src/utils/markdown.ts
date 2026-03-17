import MarkdownIt from 'markdown-it'

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
})

// ---- Mermaid fence override ----
// Save original fence rule
const defaultFence =
  md.renderer.rules.fence ||
  function (tokens, idx, options, _env, self) {
    return self.renderToken(tokens, idx, options)
  }

md.renderer.rules.fence = (tokens, idx, options, env, self) => {
  const token = tokens[idx]
  if (token.info.trim().toLowerCase() === 'mermaid') {
    // Preserve raw content for Mermaid post-processing
    const escaped = md.utils.escapeHtml(token.content)
    return `<div class="mermaid-block"><pre class="mermaid-source">${escaped}</pre></div>\n`
  }
  return defaultFence(tokens, idx, options, env, self)
}

/**
 * Render a Markdown string to HTML using markdown-it.
 * Replaces the hand-written renderMarkdown in ChatView.
 */
export function renderMarkdown(text: string): string {
  if (!text) return ''
  return md.render(text)
}
