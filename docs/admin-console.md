# Admin console integration

The admin console can load **schema** and **documentation** from this repo at runtime so it stays in sync with the Platform Engine. Use a GitHub token for private repos or raw URLs for public.

## What to load

| Asset | Purpose |
|-------|---------|
| **JSON Schema** | Validate YAML and drive wizard forms (field types, required, enums, descriptions). |
| **Overview doc** | “What is the Platform Engine?” — first-time or context help. |
| **Capabilities doc** | Per-section help (compute, storage, cache, etc.) for help boxes or tooltips. |
| **Schema guide** | Human-readable field meanings and defaults for tooltips or a “Schema reference” panel. |

## URLs (branch `main`)

Replace `BRANCH` with `main` (or the tag you support). Repo: `althq-org/platform-engine-temp`.

**Raw content (no token for public repo):**

```
# JSON Schema — use for validation and wizard
https://raw.githubusercontent.com/althq-org/platform-engine-temp/BRANCH/devops/schema/platform-spec-v1.json

# Docs (Markdown)
https://raw.githubusercontent.com/althq-org/platform-engine-temp/BRANCH/docs/overview.md
https://raw.githubusercontent.com/althq-org/platform-engine-temp/BRANCH/docs/capabilities.md
https://raw.githubusercontent.com/althq-org/platform-engine-temp/BRANCH/docs/schema-guide.md
```

**With GitHub API (supports private repo; use token in `Authorization: Bearer <token>`):**

```
GET https://api.github.com/repos/althq-org/platform-engine-temp/contents/devops/schema/platform-spec-v1.json
GET https://api.github.com/repos/althq-org/platform-engine-temp/contents/docs/overview.md
# etc.
```

Response has `content` (base64). Use `?ref=main` to pin branch. [API docs](https://docs.github.com/en/rest/repos/contents).

## Recommended usage

1. **Schema** — Fetch `platform-spec-v1.json` once (or on app load / refresh). Use with a JSON Schema validator (e.g. Ajv) and/or a form generator. Schema includes `description` on properties for short tooltips.
2. **Overview** — Fetch `overview.md`, render as Markdown in a “What is the Platform Engine?” or onboarding panel.
3. **Capabilities** — Fetch `capabilities.md`. Either render the whole doc or split by `##` headers and show the section that matches the current wizard step (e.g. `# compute`, `# storage`).
4. **Schema guide** — Fetch `schema-guide.md` for a “Schema reference” or per-field help; or use it to build tooltips from the table (section → field → meaning).

## Caching and versioning

- Cache responses (e.g. 5–15 minutes or until user clicks “Refresh”) to avoid hitting GitHub on every wizard step.
- To pin to a release, use a tag instead of `main` in the URL (e.g. `v1.0.0`).

## Zod (optional)

The source of truth for structure is the **JSON Schema**. If the admin console prefers Zod:

- **Option A:** Generate Zod from the JSON Schema at build time (e.g. [json-schema-to-zod](https://github.com/StefanTerdell/json-schema-to-zod)) and commit the generated file in the admin console repo; re-run when the schema changes.
- **Option B:** This repo could add a script that emits a TypeScript/Zod file from the JSON Schema and commit it here; the admin console would fetch that file the same way as the schema. Not added yet; JSON Schema alone is enough for validation and form generation.
