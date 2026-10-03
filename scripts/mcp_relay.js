// Run in Codex functions.exec with absolute pythonPath, scriptPath (mcp_execute.py),
// runPath and profilesPath. For read-only discovery supply discoveryPath and
// discoveryOutputPath instead of runPath. Optional callTimeoutSeconds/runTimeoutSeconds.
// The relay starts its worker. Responses stay in memory and never enter shell code.
// Host tool transcripts can retain recoverable request/response data; hex is not encryption.
const encode = value => {
  let result = "";
  for (let i = 0; i < value.length; i++) result += value.charCodeAt(i).toString(16).padStart(4, "0");
  return result;
};
const decode = value => {
  if (!/^(?:[a-f0-9]{4})+$/i.test(value)) throw new Error("Invalid worker frame encoding");
  return value.match(/.{4}/g).map(item => String.fromCharCode(parseInt(item, 16))).join("");
};
const psPath = value => `[Text.Encoding]::BigEndianUnicode.GetString([Convert]::FromHexString('${encode(String(value))}'))`;
const callTimeout = typeof callTimeoutSeconds === "undefined" ? 180 : callTimeoutSeconds;
const runTimeout = typeof runTimeoutSeconds === "undefined" ? 1800 : runTimeoutSeconds;
if (![callTimeout, runTimeout].every(value => Number.isFinite(value) && value > 0)) throw new Error("Timeouts must be positive numbers");
const discoveryMode = typeof discoveryPath !== "undefined";
const inputPath = discoveryMode ? discoveryPath : (typeof runPath === "undefined" ? undefined : runPath);
if (discoveryMode && typeof runPath !== "undefined") throw new Error("Select execution or discovery, not both");
if (![pythonPath, scriptPath, inputPath, profilesPath, ...(discoveryMode ? [typeof discoveryOutputPath === "undefined" ? undefined : discoveryOutputPath] : [])].every(value => typeof value === "string" && value.length)) throw new Error("Absolute runtime paths are required");
if (typeof tools.exec_command !== "function" || typeof tools.write_stdin !== "function") throw new Error("This relay requires Codex exec_command and write_stdin session tools");
const allowed = new Set(["gtm_tag", "gtm_trigger", "gtm_variable", "gtm_folder", "gtm_client", "gtm_transformation", "gtm_template", "gtm_zone"]);
const maxHexSize = 64 * 1024 * 1024;
const inputArgs = discoveryMode ? `--discover (${psPath(inputPath)}) --output (${psPath(discoveryOutputPath)})` : `--run (${psPath(inputPath)})`;
const command = `$ErrorActionPreference='Stop'; if ($PSVersionTable.PSVersion.Major -lt 7) { throw 'PowerShell 7 or newer is required' }; & (${psPath(pythonPath)}) -B (${psPath(scriptPath)}) ${inputArgs} --profiles (${psPath(profilesPath)}) --call-timeout ${callTimeout}`;
const started = Date.now();
let lastUpdate = started;
let calls = 0;
let finished = false;
let state = await tools.exec_command({cmd: command, shell: "pwsh", login: false, tty: true, yield_time_ms: 1000, max_output_tokens: 5000});
let session = state.session_id;
let buffer = state.output || "";
let requestId;
let parts = [];
let totalParts = 0;
const clean = value => value.replace(/\x1b\][^\x07]*(?:\x07|\x1b\\)/g, "").replace(/\x1b\[[0-?]*[ -/]*[@-~]/g, "");
async function receive(chars = "") {
  if (!session) throw new Error("Worker stopped before completion");
  state = await tools.write_stdin({session_id: session, chars, yield_time_ms: 1000, max_output_tokens: 5000});
  buffer += state.output || "";
  session = state.session_id;
}
try {
  while (Date.now() - started < runTimeout * 1000) {
    if (Date.now() - lastUpdate > 40000) {
      notify(`GTM runtime is active: ${calls} MCP calls serviced. Saved-state verification remains in progress.`);
      lastUpdate = Date.now();
      await yield_control();
    }
    // ConPTY can insert backspace+CR at a wrap boundary without removing data.
    // Frames contain only hex and fixed ASCII headers, so those controls are not payload.
    buffer = clean(buffer).replace(/[\b\r\n]/g, "");
    const done = buffer.match(/DONE ([a-f0-9\s]+) END/);
    if (done) {
      const result = JSON.parse(decode(done[1].replace(/\s/g, "")));
      text(result);
      finished = true;
      break;
    }
    const frame = buffer.match(/MCP1 ([a-f0-9]{32}) (\d+)\/(\d+) ([a-f0-9\s]+) END/);
    if (frame) {
      buffer = buffer.slice(frame.index + frame[0].length);
      const [, id, partText, totalText, rawHex] = frame;
      const part = Number(partText), total = Number(totalText);
      const chunk = rawHex.replace(/\s/g, "");
      if (part === 1) { requestId = id; totalParts = total; parts = []; }
      if (id !== requestId || total !== totalParts || total < 1 || total > maxHexSize / 4096 || part !== parts.length + 1 || chunk.length > 4096) throw new Error("Invalid worker chunk sequence");
      parts.push(chunk);
      if (part < total) {
        await receive("NEXT\n");
        continue;
      }
      const request = JSON.parse(decode(parts.join("")));
      if (request.id !== requestId) throw new Error("Worker request identity mismatch");
      const suffix = request.tool.split("__").at(-1);
      const action = request.arguments.action;
      const valid = (allowed.has(suffix) && (discoveryMode ? ["get", "list"] : ["get", "list", "create", "update", "remove"]).includes(action)) ||
        (suffix === "gtm_workspace" && ["get", "getStatus"].includes(action)) ||
        (suffix === "gtm_container" && action === "get");
      let reply;
      try {
        if (!valid || typeof tools[request.tool] !== "function") throw new Error("Undiscovered or forbidden action");
        reply = {id: request.id, result: await tools[request.tool](request.arguments)};
      } catch (error) {
        // Forward only a typed HTTP rejection, never infer application status from prose.
        const status = error?.statusCode ?? error?.status;
        reply = {id: request.id, error: Number.isInteger(status) ? {code: status} : {}};
      }
      const payload = encode(JSON.stringify(reply));
      if (payload.length > maxHexSize) throw new Error("MCP response exceeds the documented in-memory transport limit");
      parts = [];
      await receive(payload.match(/.{1,2048}/g).join("\n") + "\n.\n");
      calls += 1;
    } else {
      if (!session) throw new Error("Worker ended without a completion frame; inspect the saved execution diagnostic");
      if (buffer.length > 32768) throw new Error("Worker output has no valid bounded frame");
      await receive();
    }
  }
  if (!finished) throw new Error("Relay deadline reached; inspect the run and read back before resuming");
} finally {
  if (!finished && session) await tools.write_stdin({session_id: session, chars: "STOP\n", yield_time_ms: 1000, max_output_tokens: 1000});
}
