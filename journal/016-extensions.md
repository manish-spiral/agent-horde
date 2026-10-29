# 016 — Feature 15: Extensions (your own tool files)

## Goal

Add tools without touching the harness's code: drop a Python file into
`~/.horde/tools/` and its tools are available in every session.

## Decisions

| Question | Choice and why |
|----------|----------------|
| Format | Plain Python files using the same `@tool` decorator as the built-ins ([003](003-tools.md)). Nothing new to learn. |
| Discovery | Every `Tool` object at the top level of a file is added. Other values are ignored. |
| Where from | **Only `~/.horde/tools/`** (or `--tools-dir`). Never auto-loaded from a project: these files run as code on your machine, so loading them from a cloned repo would be a security hole. |
| Broken file | Setup fails with the file name and the error, before any model call. |
| Approval | Whatever the tool declares (`@tool(needs_approval=True)` for side effects). |
| Other languages | Write an MCP server instead ([014](014-mcp.md)). Python files are the quick path. |

## What was done

```
src/horde/extensions.py      new: load_tool_files()
src/horde/cli.py             --tools-dir; extension tools added; listed on start
tests/conftest.py            tests never load the real ~/.horde/tools
tests/test_extensions.py     new: 4 tests
```

`importlib.util.spec_from_file_location` + `exec_module` loads a file as a
module without it being on `sys.path`.

## How it was tested

`uv run pytest` gives **101 passed** (97 + 4 new): tools found (non-tools
ignored), missing folder, broken file error, and an extension tool called
end to end through the CLI. Not run live (Groq's daily limit was used up).

## What you should learn here

- **Reuse the extension mechanism you already have.** Extensions use `@tool`,
  so built-in and user tools are the same thing.
- **Loading code is a trust decision.** Only load from places the user controls.
