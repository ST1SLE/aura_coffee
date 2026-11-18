import fs from 'node:fs';
import path from 'node:path';

// START_MODULE_CONTRACT
// PURPOSE: Emit collected identities and actual Vitest task semantics without diagnostic payloads.
// SCOPE: Pinned Vitest 3 task API; expected failures and retries never count as success.
// DEPENDS: Node standard library, installed locked Vitest.
// LINKS: C-REQUIRED-EVIDENCE-GATE
// ROLE: CONFIG
// MAP_MODE: NONE
// END_MODULE_CONTRACT
const flatten = (files) => {
  const rows = [];
  const visit = (task, parents, file) => {
    if (task.type === 'test') {
      const relative = path.relative(process.env.AURA_GATE_ROOT, file).split(path.sep).join('/');
      const retry = task.result?.retryCount ?? 0;
      rows.push({ id: relative + '::' + [...parents, task.name].join(' > '),
        profile: 'default', retry,
        status: task.result?.state === 'pass' && !task.fails && retry === 0 && (task.result?.repeatCount ?? 0) === 0 ? 'passed' : 'not-passed' });
    } else {
      for (const child of task.tasks ?? []) visit(child, task.filepath ? [] : [...parents, task.name], task.filepath ?? file);
    }
  };
  files.forEach(file => visit(file, [], file.filepath));
  return rows;
};
export default class {
  collected = [];
  onCollected(files) { this.collected = flatten(files).map(row => row.id); }
  onFinished(files, errors) {
    const results = flatten(files);
    if (errors?.length) results.forEach(row => { row.status = 'not-passed'; });
    fs.writeFileSync(process.env.AURA_GATE_REPORT, JSON.stringify({version: 1, collected: this.collected, results}));
  }
}
