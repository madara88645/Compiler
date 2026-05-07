const vscode = require("vscode");
const { titleCaseArtifact } = require("./model");

class SidebarNode extends vscode.TreeItem {
  constructor({ id, label, collapsibleState = vscode.TreeItemCollapsibleState.None, description, tooltip, command, iconPath }) {
    super(label, collapsibleState);
    this.id = id;
    this.description = description;
    this.tooltip = tooltip;
    this.command = command;
    this.iconPath = iconPath;
  }
}

class PromptCSidebarProvider {
  constructor(getState) {
    this.getState = getState;
    this._onDidChangeTreeData = new vscode.EventEmitter();
    this.onDidChangeTreeData = this._onDidChangeTreeData.event;
  }

  refresh() {
    this._onDidChangeTreeData.fire();
  }

  getTreeItem(element) {
    return element;
  }

  async getChildren(element) {
    const state = this.getState();
    if (!element) {
      return [
        new SidebarNode({
          id: "status",
          label: "Status",
          collapsibleState: vscode.TreeItemCollapsibleState.Expanded,
          iconPath: new vscode.ThemeIcon("pulse"),
        }),
        new SidebarNode({
          id: "artifacts",
          label: "Artifacts",
          collapsibleState: vscode.TreeItemCollapsibleState.Expanded,
          iconPath: new vscode.ThemeIcon("files"),
        }),
        new SidebarNode({
          id: "history",
          label: "History",
          collapsibleState: vscode.TreeItemCollapsibleState.Collapsed,
          iconPath: new vscode.ThemeIcon("history"),
        }),
        new SidebarNode({
          id: "favorites",
          label: "Favorites",
          collapsibleState: vscode.TreeItemCollapsibleState.Collapsed,
          iconPath: new vscode.ThemeIcon("star-empty"),
        }),
      ];
    }

    if (element.id === "status") {
      return [
        new SidebarNode({
          id: "status.connection",
          label: state.connectionLabel,
          description: state.baseUrl,
          tooltip: `${state.connectionLabel}\n${state.baseUrl}`,
          command: { command: "promptc.checkConnection", title: "Check Connection" },
          iconPath: new vscode.ThemeIcon(state.connectionOk ? "pass-filled" : "warning"),
        }),
        new SidebarNode({
          id: "status.latest",
          label: state.latestLabel,
          description: state.latestDescription,
          tooltip: state.latestTooltip,
          command: { command: "promptc.openPanel", title: "Open Panel" },
          iconPath: new vscode.ThemeIcon("note"),
        }),
      ];
    }

    if (element.id === "artifacts") {
      if (!state.currentEntry) {
        return [
          new SidebarNode({
            id: "artifacts.empty",
            label: "Run PromptC compile to populate artifacts",
            iconPath: new vscode.ThemeIcon("circle-slash"),
          }),
        ];
      }

      return state.artifactTypes.map((type) => {
        const content = state.currentEntry.artifacts[type] || "";
        return new SidebarNode({
          id: `artifact.${type}`,
          label: titleCaseArtifact(type),
          description: content ? `${content.length} chars` : "Empty",
          tooltip: content || "Artifact is empty",
          command: { command: "promptc.copyArtifact", title: "Copy Artifact", arguments: [type] },
          iconPath: new vscode.ThemeIcon("copy"),
        });
      });
    }

    if (element.id === "history") {
      if (!state.history.length) {
        return [
          new SidebarNode({
            id: "history.empty",
            label: "No compile history yet",
            iconPath: new vscode.ThemeIcon("circle-slash"),
          }),
        ];
      }

      return state.history.map((entry) => {
        return new SidebarNode({
          id: `history.${entry.id}`,
          label: entry.preview || "Untitled compile",
          description: `${entry.summary.domain} - ${entry.summary.riskLevel}`,
          tooltip: `${entry.savedAt}\n${entry.sourceText}`,
          command: {
            command: "promptc.openHistoryEntry",
            title: "Open History Entry",
            arguments: [entry.id],
          },
          iconPath: new vscode.ThemeIcon("history"),
        });
      });
    }

    if (element.id === "favorites") {
      if (!state.favorites.length) {
        return [
          new SidebarNode({
            id: "favorites.empty",
            label: "No favorites saved yet",
            iconPath: new vscode.ThemeIcon("circle-slash"),
          }),
        ];
      }

      return state.favorites.map((entry) => {
        return new SidebarNode({
          id: `favorite.${entry.id}`,
          label: entry.label,
          description: `${entry.domain} - ${entry.riskLevel}`,
          tooltip: entry.content,
          command: {
            command: "promptc.copyFavoriteEntry",
            title: "Copy Favorite Entry",
            arguments: [entry.id],
          },
          iconPath: new vscode.ThemeIcon("star-full"),
        });
      });
    }

    return [];
  }
}

module.exports = {
  PromptCSidebarProvider,
};
