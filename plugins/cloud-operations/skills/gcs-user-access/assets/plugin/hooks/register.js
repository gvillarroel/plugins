// Loaded directly by Claude Code; validate with: claude plugin validate <plugin> --strict.
const HELP = [
  "Google Cloud Storage with your Google user account",
  "/gcs status",
  "/gcs projects",
  "/gcs buckets PROJECT_ID",
  "/gcs objects gs://BUCKET [PREFIX]",
  "/gcs login EMAIL",
  "Lists at most 100 results. Object contents are never read.",
  "Login reuses valid authorization or opens Google sign-in; it preserves your active gcloud account and ADC and selects the user for this Claude session.",
  "Project discovery and bucket discovery are separate permissions; a known bucket can work even when discovery is denied.",
].join("\n");

const CONFIG_FORMAT = "json(core.account,core.project,auth.impersonate_service_account,auth.credential_file_override,auth.access_token_file,auth.disable_credentials,auth.login_config_file)";
const PROJECT = /^[a-z][a-z0-9-]{4,61}[a-z0-9]$/;
const EMAIL = /^[A-Za-z0-9.!#$%&'+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}$/;

function userEmail(value) {
  return typeof value === "string" && EMAIL.test(value) && !value.toLowerCase().endsWith(".gserviceaccount.com");
}

function clean(value) {
  // Resource names are data, including untrusted terminal control characters.
  return String(value ?? "").replace(/[\u0000-\u001f\u007f-\u009f]/g, " ").slice(0, 1600);
}

function failure(result) {
  const message = `${result.stderr || ""} ${result.stdout || ""}`;
  if (/permission.denied|403|does not have.*access|not have.*permission/i.test(message)) {
    return "Google denied this listing. Keep the same user; use a known project/bucket or request the required list permission.";
  }
  if (/invalid_grant|reauth|refresh.*token|log.?in|no.*credentials|expired/i.test(message)) {
    return "Google credentials need authorization. Run /gcs login YOUR_EMAIL and complete Google's browser flow.";
  }
  if (/invalid.*project|project.*invalid|not found|404/i.test(message)) {
    return "The requested project or bucket was not found or is not visible to this user.";
  }
  return `gcloud could not complete this operation (exit ${Number(result.exitCode)}). Check the selected project and Google account in your terminal.`;
}

function parse(args) {
  const words = String(args || "").trim().split(/\s+/).filter(Boolean);
  const action = words.shift() || "help";
  if (["help", "status", "projects"].includes(action) && words.length === 0) return { action };
  if (action === "buckets" && words.length === 1 && PROJECT.test(words[0])) return { action, project: words[0] };
  if (action === "login" && words.length === 1 && userEmail(words[0])) return { action, email: words[0] };
  if (action === "objects" && words.length >= 1) {
    const target = words.shift();
    const match = /^gs:\/\/([a-z0-9][a-z0-9._-]{1,220}[a-z0-9])(?:\/(.*))?$/.exec(target);
    if (match) {
      const prefix = (match[2] || "") + words.join(" ");
      if (!/[\u0000-\u001f\u007f*?\[\]]/.test(prefix) && prefix.length <= 1024) {
        return { action, bucket: match[1], prefix };
      }
    }
  }
  throw new Error("Unsupported arguments. Use /gcs help. Project IDs, Google user emails, and one gs:// bucket are accepted; extra flags and wildcard prefixes are refused.");
}

async function guardEnvironment($) {
  // Literal names let Claude Code's validator expose every environment read.
  const overrides = [
    ["CLOUDSDK_AUTH_ACCESS_TOKEN", await $.env.get("CLOUDSDK_AUTH_ACCESS_TOKEN")],
    ["CLOUDSDK_AUTH_ACCESS_TOKEN_FILE", await $.env.get("CLOUDSDK_AUTH_ACCESS_TOKEN_FILE")],
    ["CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE", await $.env.get("CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE")],
    ["CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT", await $.env.get("CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT")],
    ["CLOUDSDK_AUTH_DISABLE_CREDENTIALS", await $.env.get("CLOUDSDK_AUTH_DISABLE_CREDENTIALS")],
    ["CLOUDSDK_AUTH_LOGIN_CONFIG_FILE", await $.env.get("CLOUDSDK_AUTH_LOGIN_CONFIG_FILE")],
  ];
  for (const [name, value] of overrides) {
    const disabled = name === "CLOUDSDK_AUTH_DISABLE_CREDENTIALS" && /^(false|0)$/i.test(value || "");
    if (value && !disabled) throw new Error(`Refusing ${name}. Remove this authentication override before using the Google user command.`);
  }
}

async function run($, args, timeoutMs = 60000) {
    const result = await $.process.run(["gcloud", ...args, "--quiet"], {
      timeoutMs,
      env: {
        CLOUDSDK_CORE_DISABLE_FILE_LOGGING: "true",
        CLOUDSDK_COMPONENT_MANAGER_DISABLE_UPDATE_CHECK: "true",
        CLOUDSDK_CORE_DISABLE_PROMPTS: "true",
      },
    });
    if (result.exitCode !== 0) throw new Error(failure(result));
    return result.stdout;
  }

async function json($, args) {
    const raw = await run($, args);
    try { return JSON.parse(raw); }
    catch { throw new Error("gcloud returned an unexpected response. No listing was accepted."); }
  }

async function configuration($) {
    await guardEnvironment($);
    const config = await json($, ["config", "list", `--format=${CONFIG_FORMAT}`]);
    if (!config || typeof config !== "object" || Array.isArray(config)) throw new Error("gcloud returned an invalid configuration.");
    const auth = config.auth || {};
    for (const name of ["impersonate_service_account", "credential_file_override", "access_token_file", "disable_credentials", "login_config_file"]) {
      const disabled = name === "disable_credentials" && (auth[name] === false || /^(false|0)$/i.test(String(auth[name])));
      if (auth[name] && !disabled) {
        throw new Error(`Refusing gcloud auth/${name}. Remove this authentication override before using the Google user command.`);
      }
    }
    return config;
  }

async function identity($, config, selectedAccount) {
    const account = selectedAccount || config.core?.account;
    if (!userEmail(account)) throw new Error("No Google user account is selected. Run /gcs login YOUR_EMAIL; service accounts are refused.");
    const accounts = await json($, ["auth", "list", `--account=${account}`, `--filter=account=${account}`, "--format=json(account,status)"]);
    if (!Array.isArray(accounts) || accounts.length !== 1 || accounts[0].account !== account) throw new Error("This Google user has no stored gcloud credentials. Run /gcs login YOUR_EMAIL.");
    return account;
  }

export function register(on) {
  let selectedAccount = "";

  on("session.start", async ($, e, next) => {
    await $.command.register({ name: "gcs", description: "List Cloud Storage as your Google user", argumentHint: "help | status | projects | buckets PROJECT | objects gs://BUCKET [PREFIX] | login EMAIL" });
    return next(e);
  });

  on("command.run", { command: "gcs" }, async ($, e) => {
    try {
      const request = parse(e.args);
      if (request.action === "help") return { text: HELP };
      const config = await configuration($);
      if (request.action === "login") {
        // Only this explicit command starts browser authorization. Never print OAuth output.
        await run($, ["auth", "login", request.email, "--brief", "--no-activate", "--no-update-adc"], 600000);
        const previous = selectedAccount;
        selectedAccount = request.email;
        try { await identity($, config, selectedAccount); }
        catch (error) { selectedAccount = previous; throw error; }
        return { text: `Google authorization is available for ${clean(selectedAccount)}. Selected for this Claude session; active gcloud configuration and ADC were preserved.` };
      }
      const account = await identity($, config, selectedAccount);
      const heading = `Google user: ${clean(account)}`;
      if (request.action === "status") return { text: `${heading}\nConfigured project: ${clean(config.core?.project || "(none)")}\nSource: gcloud user credentials; no impersonation or token-file override.\nStored credentials are present; this status check does not validate token refresh or IAM access.` };
      let args;
      let scope;
      if (request.action === "projects") {
        args = ["projects", "list", "--format=json(projectId,name)"];
        scope = "Projects visible through project discovery";
      } else if (request.action === "buckets") {
        args = ["storage", "buckets", "list", `--project=${request.project}`, "--format=json(name,location,storage_url)"];
        scope = `Buckets in ${request.project}`;
      } else {
        const target = `gs://${request.bucket}/${request.prefix}**`;
        args = ["storage", "objects", "list", target, "--format=json(name,bucket,size,storage_url)"];
        scope = `Objects in gs://${request.bucket}/${clean(request.prefix)}`;
      }
      const rows = await json($, [...args, `--account=${account}`, "--limit=100"]);
      if (!Array.isArray(rows) || rows.length > 100) throw new Error("gcloud returned an invalid or unbounded listing.");
      const lines = rows.map(row => request.action === "projects"
        ? `${clean(row.projectId)}  ${clean(row.name)}`
        : request.action === "buckets"
          ? `${clean(row.storage_url || `gs://${row.name}`)}  ${clean(row.location)}`
          : `${clean(row.storage_url || `gs://${request.bucket}/${row.name}`)}  ${clean(row.size)} bytes`);
      return { text: `${heading}\n${scope}\n${lines.length ? lines.join("\n") : "No matching results."}\nReturned ${lines.length} results (limit 100; this is not a global inventory).${lines.length === 100 ? " More results may exist." : ""}` };
    } catch (error) {
      // Keep process exceptions and OAuth state out of the transcript.
      const message = typeof error?.message === "string" && /^(Unsupported arguments|Refusing |No Google user|This Google user|Google denied|Google credentials|The requested|gcloud |No matching)/.test(error.message)
        ? error.message
        : "The local gcloud command could not start or timed out. Confirm Google Cloud CLI is installed and on PATH, then retry.";
      return { text: clean(message) };
    }
  });
}
