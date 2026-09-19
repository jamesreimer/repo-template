// Test-only public Node loader controls; never imported by the production CLI.
import {registerHooks} from 'node:module';
const mode = process.env.LINK_TEST_CONTROL;
registerHooks({
  resolve(specifier, context, nextResolve) {
    const result = nextResolve(specifier, context);
    if (mode === 'isolated' && specifier === 'marked' &&
        context.parentURL?.endsWith('/tools/link-frontmatter.mjs')) {
      return {...result, url: result.url + '?separate-instance'};
    }
    return result;
  },
  load(url, context, nextLoad) {
    if (mode === 'disabled' && url.endsWith('/tools/link-frontmatter.mjs')) {
      return {format: 'module', shortCircuit: true,
        source: 'export const observations = {parsed: 0, yamlErrors: []};'};
    }
    return nextLoad(url, context);
  },
});
if (mode === 'double') {
  await import('../../tools/link-frontmatter.mjs?second-registration');
}
