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
which dembrandt || echo "not installed"
```

If not installed, use `npx dembrandt` in place of `dembrandt` in all commands below (no install required).

### 2. Run extraction

Default command — outputs W3C DTCG tokens to `output/<domain>/<timestamp>.tokens.json`:

```bash
dembrandt <url> --dtcg --save-output
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
dembrandt stripe.com --dtcg --save-output --browser=firefox --slow
```

### 3. Move output to project documentation

Dembrandt writes to `output/<domain>/` by default. After extraction, move the files to the project's canonical design token location.

Derive a kebab-case short name from the site's domain (e.g. `stripe.com` → `stripe`, `fonts.google.com` → `google-fonts`) and run:

```bash
SITE_SLUG="<web_site_shortname_kebab>"
DEST="project-docs/project-documentation/design-tokens/$SITE_SLUG"
mkdir -p "$DEST"
mv output/<domain>/* "$DEST/"
```

Confirm the files are in place:
```bash
ls "$DEST"
```

### 4. Report to the user

Report the final file paths and summarize what token categories were extracted (colors, typography, spacing, shadows, borders, components, etc.).

### 5. Next steps (optional)

If the task requires integrating extracted tokens into the project:
- Copy relevant tokens into the project's design token file (CSS variables, YAML, or the project's existing format)
- Update `design-vision.md` to note the reference site and any borrowed tokens
