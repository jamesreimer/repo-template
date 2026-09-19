import {marked} from 'marked';
import {unified} from 'unified';
import remarkParse from 'remark-parse';
import remarkFrontmatter from 'remark-frontmatter';
import remarkRehype from 'remark-rehype';
import rehypeRaw from 'rehype-raw';
import rehypeSlug from 'rehype-slug';
import rehypeStringify from 'rehype-stringify';
import {visit} from 'unist-util-visit';
import {parseDocument} from 'yaml';

export const observations = {parsed: 0, yamlErrors: []};
function metadataGate() {
  return (tree, file) => {
    observations.parsed++;
    visit(tree, 'yaml', (node) => {
      try {
        const document = parseDocument(node.value, {uniqueKeys: true});
        if (document.errors.length || document.warnings.length) {
          throw document.errors[0] || document.warnings[0];
        }
        document.toJS();
      } catch (error) {
        observations.yamlErrors.push(error.message);
        file.fail(error.message, node.position, 'yaml-frontmatter:invalid');
      }
    });
  };
}
const renderer = unified().use(remarkParse).use(remarkFrontmatter)
  .use(metadataGate).use(remarkRehype, {allowDangerousHtml: true})
  .use(rehypeRaw).use(rehypeSlug).use(rehypeStringify);

// Marked's public hook composes maintained renderers in memory. Linkinator
// calls this shared Marked instance for both inputs and fetched targets.
marked.use({async: true, hooks: {
  async preprocess(source) { return String(await renderer.process(source)); },
}});
