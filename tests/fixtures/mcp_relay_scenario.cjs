const fs = require('node:fs');
const path = require('node:path');
const cp = require('node:child_process');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const scriptPath = path.join(root, 'scripts/mcp_queue_adapter.py');
const pythonPath = process.env.TEST_PYTHON;
const shellPath = process.env.TEST_PWSH;
assert(pythonPath && shellPath, 'Set TEST_PYTHON and TEST_PWSH to discovered runtimes');
const queuePath = path.join(process.argv[2], 'relay-' + Date.now());
fs.mkdirSync(queuePath);
const cases = [
  {id: '1'.repeat(32), tool: 'synthetic__gtm_tag', arguments: {action: 'get', tagId: '101'}},
  {id: '2'.repeat(32), tool: 'synthetic__gtm_tag', arguments: {action: 'create'}},
  {id: '3'.repeat(32), tool: 'synthetic__gtm_workspace', arguments: {action: 'publish'}},
  {id: '4'.repeat(32), tool: 'synthetic__gtm_variable', arguments: {action: 'get', variableId: '9'}},
  {id: '5'.repeat(32), tool: 'synthetic__gtm_trigger', arguments: {action: 'get', triggerId: '42'}},
  {id: '6'.repeat(32), tool: 'synthetic__gtm_tag', arguments: {action: 'get', tagId: 'large'}},
];
for (const item of cases) fs.writeFileSync(path.join(queuePath,item.id+'.request.json'),JSON.stringify(item));
fs.writeFileSync(path.join(queuePath,'complete.json'),JSON.stringify({status:'Synthetic relay done'}));
const calls = [];
const nativeName = "Événement d'O'Brien — 日本語";
let receiver;
const tools = {
  exec_command: async ({cmd}) => {
    if (cmd.endsWith(' --stream')) {
      receiver = cp.spawn(shellPath, ['-NoProfile','-NonInteractive','-Command',cmd], {stdio:['pipe','pipe','pipe']});
      return {session_id:1, output:'STREAM_READY'};
    }
    const child = cp.spawnSync(shellPath, ['-NoProfile','-NonInteractive','-Command',cmd], {encoding:'utf8'});
    return {exit_code:child.status, output:child.stdout, stderr:child.stderr};
  },
  write_stdin: async ({chars}) => {
    let output = '';
    receiver.stdout.on('data', value => {output += value.toString('utf8');});
    receiver.stderr.on('data', value => {output += value.toString('utf8');});
    const completion = new Promise(resolve => receiver.on('close', code => resolve({exit_code:code,output})));
    receiver.stdin.end(chars);
    return completion;
  },
  synthetic__gtm_tag: async args => {
    calls.push(['tag',args]);
    return {structuredContent:{tagId:args.tagId || '501',name:nativeName,type:'gaawe', notes: args.tagId === 'large' ? 'É日本語'.repeat(20000) : ''}};
  },
  synthetic__gtm_workspace: async args => {throw new Error('forbidden dispatch unexpectedly occurred');},
  synthetic__gtm_variable: async args => {calls.push(['variable',args]);throw new Error('synthetic transport exception');},
  synthetic__gtm_trigger: async args => {calls.push(['trigger',args]);return {isError:true,content:[{type:'text',text:'synthetic MCP tool error'}]};},
};
const outputs = [];
const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;
const source = fs.readFileSync(path.join(root,'scripts/mcp_relay.js'),'utf8');
const fn = new AsyncFunction('pythonPath','scriptPath','queuePath','tools','text','notify','yield_control', source);
(async () => {
  await fn(pythonPath,scriptPath,queuePath,tools,v=>outputs.push(v),v=>outputs.push(v),async()=>{});
  const replies = cases.map(item=>JSON.parse(fs.readFileSync(path.join(queuePath,item.id+'.response.json'),'utf8')));
  fs.writeFileSync(path.join(process.argv[2],'relay-result.json'),JSON.stringify({calls,replies,outputs},null,2));
  assert.equal(replies[0].result.name,nativeName);
  assert.equal(replies[1].result.tagId,'501');
  assert(replies[2].error && replies[3].error && replies[4].error);
  assert.equal(calls.length,5);
  assert.equal(replies[5].result.notes, 'É日本語'.repeat(20000));
  assert.equal(outputs.at(-1).status,'Synthetic relay done');
  assert.equal(fs.readdirSync(queuePath).filter(x=>x.endsWith('.claimed') || x.endsWith('.request.json')).length,0);
  fs.writeFileSync(path.join(process.argv[2],'relay-result.json'),JSON.stringify({calls,replies,outputs},null,2));
  console.log('PASS packaged JS relay syntax/execution with local mocked MCP tools and real PowerShell queue CLI; apostrophe/Unicode preserved; forbidden action blocked; thrown tool error delivered');
})().catch(error=>{console.error(error);process.exitCode=1;});
