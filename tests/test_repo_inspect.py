from app.repo_inspect import RepoFacts, derive_repo_context


def _facts(files, tree=None, has_claude_md=False):
    return RepoFacts(
        files=files,
        tree=tree or list(files.keys()),
        has_claude_md=has_claude_md,
        has_claude_dir=False,
    )


def test_detects_node_stack_and_scripts():
    facts = _facts(
        {
            "web/package.json": '{"scripts": {"test": "vitest run", "build": "next build", "lint": "eslint ."}}'
        }
    )
    ctx = derive_repo_context(facts)
    assert "javascript" in {s.language for s in ctx.stacks}
    cmds = {c.name: c.command for c in ctx.commands}
    assert cmds["test"] == "npm run test"
    assert cmds["build"] == "npm run build"
    assert any(c.source.endswith("package.json") for c in ctx.commands)


def test_detects_python_pyproject_and_makefile():
    facts = _facts(
        {
            "pyproject.toml": '[project]\nname = "x"\n[tool.pytest.ini_options]\ntestpaths = ["tests"]\n',
            "Makefile": "test:\n\tpython -m pytest tests/ -q\nbuild:\n\techo build\n",
        }
    )
    ctx = derive_repo_context(facts)
    assert "python" in {s.language for s in ctx.stacks}
    cmds = {c.name: c.command for c in ctx.commands}
    assert cmds["test"] == "python -m pytest tests/ -q"  # Makefile target body wins for test


def test_empty_repo_is_safe():
    ctx = derive_repo_context(_facts({}))
    assert ctx.stacks == []
    assert ctx.commands == []


def test_surfaces_existing_claude_md():
    ctx = derive_repo_context(_facts({"CLAUDE.md": "# guide"}, has_claude_md=True))
    assert ctx.has_existing_claude_md is True
