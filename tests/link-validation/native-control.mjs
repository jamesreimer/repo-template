// Separate process intentionally omits the hook; exercises native behavior.
import {LinkChecker} from 'linkinator';
const result = await new LinkChecker().check({path: ['source.md'],
  serverRoot: process.cwd(), markdown: true, checkFragments: true,
  directoryListing: process.argv.includes('--directory-listing')});
console.log(JSON.stringify(result));
process.exitCode = result.passed ? 0 : 1;
