# GitHub Linguist Readiness: FunnelScript

This document details the configuration required for upstream submission to [github-linguist/linguist](https://github.com/github-linguist/linguist).

## Upstream `languages.yml` Entry

When submitting to `github-linguist/linguist`, append the following entry to `lib/linguist/languages.yml`:

```yaml
FunnelScript:
  type: programming
  color: "#725CFF"
  aliases:
    - fnls
  extensions:
    - ".fnls"
  tm_scope: source.funnelscript
  ace_mode: text
  language_id: 849204918 # (Assigned sequentially by linguist maintainers)
```

### Color Token Rationale
* **Hex Code**: `#725CFF` (Signal Violet)
* **Source of Truth**: Defined in `docs/brand/tokens.css` and `docs/brand/README.md` as the primary brand, mark, and visual identity color.
* **Contrast**: Paired with `#121525` (Graphite) and `#61E7C3` (Event Mint).

---

## Repository-Level Overrides (`.gitattributes`)

Prior to upstream inclusion in GitHub Linguist, repository statistics and syntax detection are controlled via `.gitattributes` at the root of the repository:

```gitattributes
*.fnls linguist-language=FunnelScript linguist-detectable=true
```

To provide immediate fallback syntax coloring on GitHub before the custom TextMate grammar is bundled upstream:

```gitattributes
# Optional fallback for GitHub web view syntax highlighting:
*.fnls linguist-language=Ruby
```

---

## PR Submission Checklist for `github-linguist`

1. [ ] **Grammar submodule**: Point to this repository or a dedicated syntax repo providing `syntaxes/funnelscript.tmLanguage.json`.
2. [ ] **Sample files**: Include 1–2 real `.fnls` sample programs under `samples/FunnelScript/` in the Linguist repository.
3. [ ] **Extension uniqueness**: `.fnls` is dedicated exclusively to FunnelScript (disambiguating from `.fnl` which belongs to Fennel).
4. [ ] **Color validation**: Hex color `#725CFF` conforms to GitHub Linguist contrast guidelines.
