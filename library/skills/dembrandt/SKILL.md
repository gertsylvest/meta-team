---
name: dembrandt
description: Extract design tokens from any live website using the Dembrandt CLI, and save them in W3C Design Tokens (DTCG) format. Use when you need to inspect or borrow a site's design system.
allowed-tools: Bash, Read
argument-hint: "[url]"
---

# Dembrandt

Extract a website's design tokens (colors, typography, spacing, shadows, borders, components) into W3C DTCG-format `.tokens.json` using the [Dembrandt CLI](https://github.com/dembrandt/dembrandt).

## Instructions

The target URL is in `$ARGUMENTS`. If no URL is provided, ask the user for one before proceeding.

### 1. Check installation

```bash
command -v dembrandt || echo "not installed"
```

If not installed, use `npx --yes dembrandt@0.39.2` in place of `dembrandt` in all commands below (no install required). The version is pinned so runs are reproducible — bump it deliberately after checking the [changelog](https://github.com/dembrandt/dembrandt). On first use, fetch its browser once with `dembrandt install-browser`.

### 2. Run extraction in a temp directory

`--save-output` always writes to `output/<domain>/` **relative to the current directory**, and the CLI has no flag to change that. Run it from a throwaway directory so nothing lands in the project root:

```bash
PROJECT_ROOT="$(pwd)"
WORK="$(mktemp -d)"
( cd "$WORK" && dembrandt <url> --dtcg --save-output )
```

Adjust flags based on the site:

| Situation | Flag to add |
|-----------|-------------|
| JS-heavy SPA or slow site | `--slow` |
| Cloudflare / bot-detection issues | `--browser=firefox` (install first: `npx playwright install firefox`) |
| Need dark mode tokens | `--dark-mode` |
| Mobile viewport (390×844) | `--mobile` |

Example for a resilient extraction:
```bash
( cd "$WORK" && dembrandt stripe.com --dtcg --save-output --browser=firefox --slow )
```

### 3. Move output to project documentation

Extracted tokens from someone else's site are an external reference, so they belong under `project-docs/resources/` (see the `documentation-structure` rule).

Derive a kebab-case short name from the site's domain (e.g. `stripe.com` → `stripe`, `fonts.google.com` → `google-fonts`) and run:

```bash
SITE_SLUG="<web_site_shortname_kebab>"
DEST="$PROJECT_ROOT/project-docs/resources/design-tokens/$SITE_SLUG"
mkdir -p "$DEST"
mv "$WORK"/output/*/* "$DEST/"
rm -rf "$WORK"
```

Confirm the files are in place:
```bash
ls "$DEST"
```

If the project uses a different documentation layout, put the tokens in its equivalent external-references folder instead, and never in the project root.

### 4. Report to the user

Report the final file paths and summarize what token categories were extracted (colors, typography, spacing, shadows, borders, components, etc.).

### 5. Next steps (optional)

If the task requires integrating extracted tokens into the project:
- Copy relevant tokens into the project's design token file (CSS variables, YAML, or the project's existing format)
- Update `project-docs/architecture/design-vision.md` to note the reference site and any borrowed tokens
- Add the new `resources/design-tokens/` entry to `project-docs/INDEX.md` if the project keeps one
