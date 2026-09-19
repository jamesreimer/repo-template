// Separate process intentionally omits the hook; documents native false green.
import {LinkChecker} from 'linkinator';
const result = await new LinkChecker().check({path: ['source.md'],
  serverRoot: process.cwd(), markdown: true, checkFragments: true});
console.log(JSON.stringify(result));
process.exitCode = result.passed ? 0 : 1;
