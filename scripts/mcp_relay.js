// Run in functions.exec after setting absolute scriptPath, queuePath, pythonPath.
// The Python worker must already be running. Never print MCP responses.
// Response data crosses the host tool transcript; disk redaction is not host-log control.
function quotePS(value) { return "'" + String(value).replaceAll("'", "''") + "'"; }
const command = action => `& ${quotePS(pythonPath)} -B ${quotePS(scriptPath)} ${action} --queue ${quotePS(queuePath)}`;
const allowed = new Set(["gtm_tag", "gtm_trigger", "gtm_variable", "gtm_folder", "gtm_client", "gtm_transformation", "gtm_template", "gtm_zone"]);
const started = Date.now();
let lastUpdate = started;
let count = 0;
let finished = false;
while (Date.now() - started < 30 * 60 * 1000) {
  const next = await tools.exec_command({cmd: command("next"), max_output_tokens: 12000});
  if (next.exit_code !== 0) throw new Error("Queue request could not be read");
  const request = JSON.parse(next.output);
  if (Date.now() - lastUpdate > 40000) {
    notify(`GTM runtime is active: ${count} MCP calls serviced. Saved-state verification remains in progress.`);
    lastUpdate = Date.now();
    await yield_control();
  }
  if (!request) {
    const completed = await tools.exec_command({cmd: `if (Test-Path -LiteralPath ${quotePS(queuePath + "/complete.json")}) { Get-Content -LiteralPath ${quotePS(queuePath + "/complete.json")} }`, max_output_tokens: 1000});
    if (completed.output.trim()) { text(JSON.parse(completed.output)); finished = true; break; }
    await new Promise(resolve => setTimeout(resolve, 250));
    continue;
  }
  const suffix = request.tool.split("__").at(-1);
  const action = request.arguments.action;
  const valid = (allowed.has(suffix) && ["get", "list", "create", "update", "remove"].includes(action)) ||
    (suffix === "gtm_workspace" && ["get", "getStatus"].includes(action)) ||
    (suffix === "gtm_container" && action === "get");
  let reply;
  try {
    if (!valid || typeof tools[request.tool] !== "function") throw new Error("Undiscovered or forbidden tool action");
    reply = {id: request.id, result: await tools[request.tool](request.arguments)};
  } catch {
    reply = {id: request.id, error: "MCP call failed; application status unknown"};
  }
  const payload = JSON.stringify(reply);
  const inlineCommand = `${quotePS(payload)} | ${command("reply")}`;
  let delivered;
  if (inlineCommand.length <= 16000) {
    delivered = await tools.exec_command({cmd: inlineCommand, max_output_tokens: 1000});
  } else {
    let receiver = await tools.exec_command({cmd: command("reply") + " --stream", tty: true, yield_time_ms: 1000, max_output_tokens: 1000});
    const readyDeadline = Date.now() + 120000;
    while (receiver.session_id && !receiver.output.includes("STREAM_READY") && Date.now() < readyDeadline) {
      receiver = await tools.write_stdin({session_id: receiver.session_id, chars: "", yield_time_ms: 1000, max_output_tokens: 1000});
    }
    if (!receiver.session_id || !receiver.output.includes("STREAM_READY")) throw new Error("Response stream could not be opened safely");
    // ASCII blocks avoid console encoding and command-line size limits. The
    // receiver disables console echo before accepting any response bytes.
    let encoded = "";
    for (let i = 0; i < payload.length; i++) encoded += payload.charCodeAt(i).toString(16).padStart(4, "0");
    delivered = await tools.write_stdin({session_id: receiver.session_id, chars: encoded.match(/.{1,2048}/g).join("\n") + "\n.\n", yield_time_ms: 1000, max_output_tokens: 1000});
    const deliveryDeadline = Date.now() + 120000;
    while (delivered.session_id && Date.now() < deliveryDeadline) {
      delivered = await tools.write_stdin({session_id: receiver.session_id, chars: "", yield_time_ms: 1000, max_output_tokens: 1000});
    }
  }
  if (delivered.exit_code !== 0) throw new Error("Reply could not be delivered; stop and inspect the run");
  count += 1;
}
if (!finished) throw new Error("Relay deadline reached; stop the worker and inspect the run before resuming");
