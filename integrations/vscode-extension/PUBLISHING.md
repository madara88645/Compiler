# Publishing `promptc-vscode`

This checklist is **one-time human-owned setup** to unblock the tag-triggered
publish workflow at [`.github/workflows/publish-vscode.yml`](../../.github/workflows/publish-vscode.yml).
None of these steps can be done by CI or an agent — they require a browser
session and account ownership.

## 1. Claim the publisher on VS Code Marketplace

1. Sign in to <https://marketplace.visualstudio.com/manage> with a Microsoft account.
2. If you don't already have an Azure DevOps organization, create one (any name, any region).
3. Create a new **Publisher** with ID `madara88645`. The ID must match the
   `publisher` field in [`package.json`](package.json).
4. Fill in the display name, logo (reuse [`icon.png`](icon.png)), and
   description.

## 2. Mint a Personal Access Token (VSCE_PAT)

1. In the same Azure DevOps org, open **User settings → Personal access tokens**.
2. Click **New Token** with:
   - **Name**: `promptc-vscode-publish`
   - **Organization**: `All accessible organizations`
   - **Expiration**: 1 year (max)
   - **Scopes**: **Custom defined** → enable **Marketplace → Manage**
     (the default `Marketplace → Acquire` is read-only and will fail with
     `403 Forbidden` at publish time).
3. Copy the token.
4. In the GitHub repo, go to **Settings → Secrets and variables → Actions →
   New repository secret** and save as `VSCE_PAT`.

## 3. Claim the namespace on Open VSX

1. Sign in to <https://open-vsx.org> with your GitHub account.
2. **User settings → Namespaces** → create namespace `madara88645`.
3. **User settings → Access tokens** → create a token.
4. Save as `OVSX_PAT` in the same GitHub secrets location.

## 4. First release

```bash
git tag vscode-v0.1.0
git push origin vscode-v0.1.0
```

The workflow runs `vsce package`, `vsce publish`, and `ovsx publish` in order.
Watch the run under **Actions** and confirm listings at:

- <https://marketplace.visualstudio.com/items?itemName=madara88645.promptc-vscode>
- <https://open-vsx.org/extension/madara88645/promptc-vscode>

## 5. Subsequent releases

1. Bump `version` in [`package.json`](package.json).
2. Add a new `## [x.y.z] - YYYY-MM-DD` section at the top of [`CHANGELOG.md`](CHANGELOG.md).
3. Commit, then push a matching `vscode-v{x.y.z}` tag.

The Marketplace rejects republishing the same version, so every publish
must be tag-driven.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `403 Forbidden` on `vsce publish` | `VSCE_PAT` missing **Marketplace → Manage** scope |
| `ERROR: Publisher 'madara88645' doesn't exist` | Publisher not claimed in step 1, or wrong case |
| `ERROR: Unknown namespace` on `ovsx publish` | Namespace not claimed in step 3 |
| Workflow runs but skips publish | Tag pattern mismatch — must start with `vscode-v` |
| `.vsix` bundles test files | Edit [`.vscodeignore`](.vscodeignore) and re-run |
