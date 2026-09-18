const fs = require('node:fs');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const root = path.resolve(__dirname, '..');
function scripts(dir) {
  return fs.readdirSync(dir, {withFileTypes:true}).flatMap(entry => {
    const file = path.join(dir, entry.name);
    return entry.isDirectory() ? scripts(file) : /\.(?:js|cjs|mjs)$/.test(file) ? [file] : [];
  });
}
const files = [path.join(root, 'server.js'), ...scripts(path.join(root, 'public')), ...scripts(__dirname)];
for (const file of files) {
  const result = spawnSync(process.execPath, ['--check', file], {stdio:'inherit'});
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status || 1);
}
console.log(`Syntax checked ${files.length} JavaScript files.`);
