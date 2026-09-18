"use strict";

// Markdown permits implicit closure. This authoring safeguard requires an
// explicit closer so an accidental fence cannot silently absorb later prose.
// Recognition of fences and their containers belongs to micromark.
module.exports = {
  names: ["MDX001", "fenced-code-closed"],
  description: "Fenced code blocks should have an explicit closing fence",
  tags: ["code"],
  parser: "micromark",
  function: (params, onError) => {
    const visit = (tokens) => {
      for (const token of tokens) {
        // HTML-flow children may be reparsed; they are not Markdown fences.
        if (token.type === "htmlFlow") continue;
        if (token.type === "codeFenced") {
          const fences = token.children.filter(
            (child) => child.type === "codeFencedFence"
          );
          if (fences.length === 1) {
            onError({
              lineNumber: fences[0].startLine,
              detail: "Code fence opened here has no explicit closing fence"
            });
          }
        }
        if (token.children) visit(token.children);
      }
    };
    visit(params.parsers.micromark.tokens);
  }
};
