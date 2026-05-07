const { createExtensionApp } = require("./app");

let appInstance = null;

function activate(context) {
  appInstance = createExtensionApp(context);
  return appInstance.getTestApi();
}

function deactivate() {
  appInstance?.dispose();
  appInstance = null;
}

module.exports = {
  activate,
  deactivate,
  getTestApi() {
    return appInstance?.getTestApi();
  },
};
