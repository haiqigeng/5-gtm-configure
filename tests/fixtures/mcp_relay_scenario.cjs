const fs = require('node:fs');
const path = require('node:path');
const cp = require('node:child_process');
const assert = require('node:assert/strict');
const root = process.env.RUNTIME_ROOT || path.resolve(__dirname, '../..');
const pythonPath = process.env.TEST_PYTHON;
const discoveryMode = process.env.RELAY_DISCOVERY === '1';
const cancelMode = process.env.RELAY_CANCEL === '1';
const shellPath = process.env.TEST_PWSH;
assert(pythonPath && shellPath, 'Set TEST_PYTHON and TEST_PWSH to discovered runtimes');
const quoted = fs.mkdtempSync(path.join(process.argv[2], "l’agent ‘test’ “double” "));
const scriptPath = discoveryMode ? path.join(root, 'scripts/configure_gtm.py') : path.join(quoted, 'worker.py');
if (!discoveryMode) fs.copyFileSync(path.join(__dirname, cancelMode ? 'mcp_cancel_worker.py' : 'mcp_stdio_worker.py'), scriptPath);
const runPath = path.join(quoted, 'run.json'), profilesPath = path.join(quoted, 'profiles.json');
const discoveryPath = path.join(quoted, 'input.json'), discoveryOutputPath = path.join(quoted, 'inventory.json');
let fixture;
if (discoveryMode) {
  fixture = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
  fs.writeFileSync(discoveryPath, JSON.stringify(fixture.request));
  fs.writeFileSync(profilesPath, JSON.stringify(fixture.profiles));
}
let worker, pending = '', exited = false, exitCode;
const calls = [], commands = [];
const outputs = [];
const delay = () => new Promise(resolve => setTimeout(resolve, 10));
async function pull() {
  for (let i = 0; i < 100 && !pending && !exited; i++) await delay();
  const output = pending; pending = '';
  assert(output.length < 20000, 'Worker output must stay within bounded host chunks');
  // Mimic wrapped terminal output and ANSI state. The data parser must tolerate it.
  const wrapped = '\x1b[0m' + output.replace(/(.{79})/g, '$1\b\r\n');
  return exited ? {exit_code:exitCode, output:wrapped} : {session_id:1, output:wrapped};
}
const nativeName = "Événement d'O’Brien ‘quoted’ “double” — 日本語";
const tools = {
  exec_command: async ({cmd}) => {
    commands.push(cmd);
    worker = cp.spawn(shellPath, ['-NoProfile', '-NonInteractive', '-Command', cmd], {
      stdio:['pipe','pipe','pipe'], env:{...process.env,RUNTIME_SCRIPTS:path.join(root,'scripts')}
    });
    worker.stdout.on('data', value => {pending += value.toString('utf8');});
    worker.stderr.on('data', value => {pending += value.toString('utf8');});
    worker.on('close', code => {exited = true; exitCode = code;});
    return pull();
  },
  write_stdin: async ({chars}) => {
    assert((chars || '').length < 17000, 'Every host reply transfer must be bounded');
    if (chars) worker.stdin.write(chars);
    return pull();
  },
  synthetic__gtm_tag: async args => {
    calls.push(args.action);
    if (cancelMode) return new Promise(() => {});
    if (args.tagId === 'quota') { const error = new Error('private diagnostic'); error.status = 429; error.headers = {'Retry-After':'17'}; throw error; }
    if (args.tagId === 'sensitive') return {content:[{type:'text',text:JSON.stringify({access_token:'SYNTHETIC_ONLY'})}]};
    if (args.action === 'create') {
      assert.equal(args.createOrUpdateConfig.name, nativeName);
      assert.equal(args.createOrUpdateConfig.notes, 'É日本語'.repeat(30000));
    }
    return {structuredContent:{name:nativeName,notes:args.createOrUpdateConfig?.notes || ''}};
  },
  synthetic__gtm_workspace: async () => {throw new Error('Forbidden action was dispatched');},
  synthetic__gtm_variable: async () => {calls.push('failed');throw new Error('Synthetic tool failure');},
  synthetic__gtm_template: async () => {
    calls.push('template');
    return {structuredContent:{templateId:'77',templateData:fs.readFileSync(path.join(root,'tests/fixtures/openai-web-template.tpl'),'utf8') + '\n' + 'Équipe 日本語\n'.repeat(100000)}};
  },
};
const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;
const source = fs.readFileSync(path.join(root,'scripts/mcp_relay.js'),'utf8');
if (discoveryMode) {
  const target = fixture.request.targets[0];
  for (const family of ['workspace', 'container', ...Object.keys(fixture.data)]) {
    tools['synthetic__gtm_' + family] = async args => {
      assert(['get','list','getStatus'].includes(args.action), 'Discovery must never dispatch a mutation');
      calls.push(args.action);
      if (family === 'workspace') return args.action === 'getStatus' ? {workspaceChange:[]} : {accountId:target.account_id,containerId:target.container_id,workspaceId:target.workspace_id};
      if (family === 'container') return {accountId:target.account_id,containerId:target.container_id,usageContext:[target.container_type]};
      const items = Object.values(fixture.data[family]);
      return {[family]:items.slice((args.page - 1) * args.itemsPerPage, args.page * args.itemsPerPage)};
    };
  }
}
const fn = new AsyncFunction('pythonPath','scriptPath','runPath','profilesPath','tools','text','notify','yield_control','discoveryPath','discoveryOutputPath','shellPath','runTimeoutSeconds',source);
(async () => {
  try {
    try {
      await fn(pythonPath,scriptPath,discoveryMode ? undefined : runPath,profilesPath,tools,v=>outputs.push(v),v=>outputs.push(v),async()=>{},discoveryMode ? discoveryPath : undefined,discoveryMode ? discoveryOutputPath : undefined,shellPath,cancelMode ? 3 : undefined);
      assert(!cancelMode, 'Cancellation must surface its deadline');
    } catch (error) {
      if (!cancelMode) throw error;
      assert.match(error.message, /deadline/);
    }
    while (!exited) await delay();
    assert.equal(exitCode,0,pending);
    if (cancelMode) {
      assert.deepEqual(calls,['create']);
      assert.deepEqual(JSON.parse(fs.readFileSync(runPath.replace(/\.json$/,'.execution.json'),'utf8')), {status:'Interrupted',writes_attempted:1});
      const check = cp.spawnSync(pythonPath,['-X','utf8','-B','-c',"import sys; from pathlib import Path; from gtm_configure.runtime.adapter_protocol import run_file_lock; context=run_file_lock(Path(sys.argv[1])); context.__enter__(); context.__exit__(None,None,None)",runPath],{encoding:'utf8',env:{...process.env,PYTHONPATH:path.join(root,'scripts')}});
      assert.equal(check.status,0,check.stderr);
      console.log('PASS actual relay cancellation during write, confirmed worker exit and lock reacquisition');
      return;
    }
    if (discoveryMode) {
      assert.equal(outputs.at(-1).status,'Discovered');
      const inventory = JSON.parse(fs.readFileSync(discoveryOutputPath,'utf8'));
      assert.equal(inventory.targets[0].objects.length,Object.values(fixture.data).reduce((sum,items)=>sum+Object.keys(items).length,0));
      assert.equal(commands.length,1);
      console.log('PASS actual discovery CLI through JS/PowerShell/Python relay, zero mutations');
      return;
    }
    assert.equal(outputs.at(-1).status,'Synthetic relay done');
    assert.equal(calls.length,6);
    assert.equal(commands.length,1, 'A persistent worker should be launched exactly once');
    assert(commands.every(command => !command.includes(nativeName) && !command.includes('SYNTHETIC_ONLY')));
    assert(!JSON.stringify(outputs).includes('SYNTHETIC_ONLY'));
    assert.deepEqual(fs.readdirSync(quoted), ['worker.py'], 'Transport must not create a disk reply queue');
    console.log('PASS actual JS/PowerShell/Python relay: smart quotes, Unicode, 100KB+ payloads, bounded chunks, no response shell interpolation, forbidden actions, tool errors');
  } finally { if (worker && !exited) worker.kill(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
