const { run: launch } = require('../src/commands.cjs');
const audit = require('../src/audit.cjs');

function handleJob() {
  return "independent helper";
}

function main(handleJob) {
  audit.record('start');
  launch(['--dry-run']);
  handleJob();
}

module.exports = { main };
