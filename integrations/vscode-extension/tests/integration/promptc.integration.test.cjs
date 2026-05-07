const assert = require("node:assert/strict");
const vscode = require("vscode");

suite("PromptC extension", () => {
  let extension;
  let testApi;
  let originalFetch;
  let originalShowInputBox;

  setup(async () => {
    extension = vscode.extensions.getExtension("madara88645.promptc-vscode");
    assert.ok(extension, "Extension should be discoverable in the test host.");
    await extension.activate();
    testApi = extension.exports;
    originalFetch = global.fetch;
    originalShowInputBox = vscode.window.showInputBox;
  });

  teardown(async () => {
    global.fetch = originalFetch;
    vscode.window.showInputBox = originalShowInputBox;
    await vscode.commands.executeCommand("workbench.action.closeActiveEditor");
  });

  test("registers the public commands", async () => {
    const commands = await vscode.commands.getCommands(true);

    [
      "promptc.compileSelection",
      "promptc.compileFile",
      "promptc.openPanel",
      "promptc.recompileLast",
      "promptc.checkConnection",
      "promptc.setApiKey",
      "promptc.clearApiKey",
      "promptc.copyArtifact",
      "promptc.insertArtifact",
      "promptc.saveFavorite",
    ].forEach((command) => {
      assert.ok(commands.includes(command), `Missing command ${command}`);
    });
  });

  test("compileSelection uses the selected text and updates the panel", async () => {
    const requests = [];
    global.fetch = createFetchStub(requests, {
      requestId: "req_selection",
      prompts: {
        system: "selection system",
        user: "selection user",
        plan: "selection plan",
        expanded: "selection expanded",
      },
    });

    const editor = await openDocument("alpha\nbeta\ngamma");
    editor.selection = new vscode.Selection(new vscode.Position(1, 0), new vscode.Position(1, 4));

    await vscode.commands.executeCommand("promptc.compileSelection");

    const compileRequest = requests.find((item) => item.url.endsWith("/compile"));
    assert.ok(compileRequest, "Expected a compile request.");
    assert.equal(JSON.parse(compileRequest.init.body).text, "beta");
    assert.match(testApi.getLastPanelHtml(), /req_selection/);
    assert.equal(testApi.getCurrentEntry().summary.requestId, "req_selection");
  });

  test("compileFile uses the full document and copy/insert actions work", async () => {
    const requests = [];
    global.fetch = createFetchStub(requests, {
      requestId: "req_file",
      prompts: {
        system: "full system artifact",
        user: "full user artifact",
        plan: "full plan artifact",
        expanded: "full expanded artifact",
      },
    });

    const editor = await openDocument("one\ntwo\nthree");

    await vscode.commands.executeCommand("promptc.compileFile");
    await vscode.commands.executeCommand("promptc.copyArtifact", "plan");
    assert.equal(await vscode.env.clipboard.readText(), "full plan artifact");

    editor.selection = new vscode.Selection(new vscode.Position(0, 0), new vscode.Position(0, 3));
    await vscode.commands.executeCommand("promptc.insertArtifact", "system");
    assert.ok(editor.document.getText().startsWith("full system artifact"));

    const compileRequest = requests.find((item) => item.url.endsWith("/compile"));
    assert.equal(JSON.parse(compileRequest.init.body).text, "one\ntwo\nthree");
  });

  test("401 compile responses trigger API key prompt, retry, and favorite reuse", async () => {
    let compileAttempts = 0;
    const headersSeen = [];

    global.fetch = async (url, init = {}) => {
      if (url.endsWith("/health")) {
        return okJson({ status: "ok" });
      }
      if (url.endsWith("/compile")) {
        compileAttempts += 1;
        headersSeen.push(init.headers || {});
        if (compileAttempts === 1) {
          return {
            ok: false,
            status: 401,
            headers: { get: () => "application/json" },
            json: async () => ({ detail: "missing key" }),
          };
        }

        return okJson(
          compilePayload({
            requestId: "req_auth",
            prompts: {
              system: "auth system",
              user: "auth user",
              plan: "auth plan",
              expanded: "auth expanded",
            },
          })
        );
      }
      throw new Error(`Unexpected URL ${url}`);
    };

    vscode.window.showInputBox = async () => "fresh-key";

    await openDocument("secure text");
    await vscode.commands.executeCommand("promptc.compileFile");
    await vscode.commands.executeCommand("promptc.saveFavorite", "expanded");

    const favorite = testApi.getFavorites()[0];
    assert.ok(favorite, "Expected a saved favorite.");
    await vscode.commands.executeCommand("promptc.copyFavoriteEntry", favorite.id);

    assert.equal(await vscode.env.clipboard.readText(), "auth expanded");
    assert.equal(compileAttempts, 2);
    assert.equal(headersSeen[1]["x-api-key"], "fresh-key");
  });
});

async function openDocument(content) {
  const document = await vscode.workspace.openTextDocument({ content, language: "plaintext" });
  return vscode.window.showTextDocument(document);
}

function createFetchStub(requests, { requestId, prompts }) {
  return async (url, init = {}) => {
    requests.push({ url, init });
    if (url.endsWith("/health")) {
      return okJson({ status: "ok" });
    }
    if (url.endsWith("/compile")) {
      return okJson(compilePayload({ requestId, prompts }));
    }
    throw new Error(`Unexpected URL ${url}`);
  };
}

function compilePayload({ requestId, prompts }) {
  return {
    request_id: requestId,
    processing_ms: 25,
    system_prompt_v2: prompts.system,
    user_prompt_v2: prompts.user,
    plan_v2: prompts.plan,
    expanded_prompt_v2: prompts.expanded,
    ir_v2: {
      domain: "engineering",
      persona: "assistant",
      intents: ["code"],
      policy: {
        risk_level: "low",
        risk_domains: [],
        allowed_tools: ["workspace_read"],
        forbidden_tools: [],
        sanitization_rules: [],
        data_sensitivity: "public",
        execution_mode: "advice_only",
      },
    },
  };
}

function okJson(payload) {
  return {
    ok: true,
    status: 200,
    headers: { get: () => "application/json" },
    json: async () => payload,
  };
}
