const { parseArgs } = require('./flags.cjs');
const audit = require('./audit.cjs');

module.exports = {
  run(args) {
    const flags = parseArgs(args);
    if (flags.dryRun) return audit.record('dry-run');
    return audit.record('started');
  },
};
