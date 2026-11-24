# FunnelScript Language Support for VS Code & Cursor

Official language support, syntax highlighting, and file icons for **FunnelScript** (`.fnls`) files.

![FunnelScript Icon](icons/funnelscript-color.png)

## Features

- **Official Brand File Icons**: Displays the official Convergence symbol next to all `.fnls` files in the Explorer and Editor Tabs.
- **Accurate Syntax Highlighting**: Comprehensive TextMate grammar covering declarations (`world`, `entity`, `agent`, `trait`), rules, stochastic expressions (`sample bernoulli`, `sample uniform`), financial ledgers, and capacities.
- **Language Configuration**: Smart bracket matching, indentation rules, quote pairing, generic types (`Pool<...>`, `Currency<...>`), and comment toggling (`//` and `#`).
- **File Icon Theme**: Optional standalone `FunnelScript Icons` theme.

---

## Local Installation (.vsix)

You can package and install the extension directly in **VS Code**, **Cursor**, **Windsurf**, or **Antigravity**:

### 1. Build the Package
From the `editors/vscode/` directory (or repository root):

```bash
cd editors/vscode
bunx @vscode/vsce package --no-dependencies
```

This generates `funnelscript-lang-0.1.0.vsix`.

### 2. Install Locally
Run the installation command for your editor:

```bash
# In VS Code:
code --install-extension editors/vscode/funnelscript-lang-0.1.0.vsix

# In Cursor:
cursor --install-extension editors/vscode/funnelscript-lang-0.1.0.vsix

# In Antigravity / Windsurf:
antigravity --install-extension editors/vscode/funnelscript-lang-0.1.0.vsix
```

Alternatively, open the Extensions pane (`Ctrl+Shift+X` / `Cmd+Shift+X`), click the `...` menu at the top, and select **Install from VSIX...**.

---

## Workspace Configuration (Material Icon Theme)

If you use third-party icon packs like `material-icon-theme`, add this to `.vscode/settings.json` to display the FunnelScript mark:

```json
{
  "material-icon-theme.files.associations": {
    "*.fnls": "funnelscript"
  },
  "material-icon-theme.customIconPaths": {
    "funnelscript": "editors/vscode/icons/funnelscript-color.svg"
  }
}
```

---

## Publishing to Visual Studio Marketplace

1. Create a publisher account on [Visual Studio Marketplace Management Portal](https://marketplace.visualstudio.com/manage).
2. Generate a Personal Access Token (PAT) with `Marketplace (Manage)` scope from Azure DevOps.
3. Login and publish:
   ```bash
   bunx @vscode/vsce login funnelscript
   bunx @vscode/vsce publish
   ```
