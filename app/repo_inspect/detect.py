from __future__ import annotations

import json
import re

from .models import DetectedCommand, StackInfo

# Which manifest basenames imply which language.
_LANG_BY_MANIFEST = {
    "package.json": "javascript",
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "setup.py": "python",
    "Pipfile": "python",
    "go.mod": "go",
    "Cargo.toml": "rust",
    "pom.xml": "java",
    "build.gradle": "java",
    "composer.json": "php",
    "Gemfile": "ruby",
}

# npm script name -> canonical command name we care about.
_NPM_SCRIPT_ALIASES = {
    "test": "test",
    "build": "build",
    "lint": "lint",
    "dev": "dev",
    "format": "format",
    "fmt": "format",
    "start": "dev",
}
_MAKE_TARGET_ALIASES = {
    "test": "test",
    "build": "build",
    "lint": "lint",
    "dev": "dev",
    "format": "format",
    "fmt": "format",
}
_FRAMEWORK_NAMES = (
    "fastapi",
    "django",
    "flask",
    "next",
    "react",
    "vue",
    "svelte",
    "express",
    "nestjs",
)
_FRAMEWORK_PATTERNS = {
    name: re.compile(rf"(?<![a-z0-9_]){re.escape(name)}(?![a-z0-9_])") for name in _FRAMEWORK_NAMES
}


def parse_package_json_scripts(content: str, source: str) -> list[DetectedCommand]:
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return []
    scripts = data.get("scripts") or {}
    if not isinstance(scripts, dict):
        return []
    cmds: list[DetectedCommand] = []
    for raw_name, canonical in _NPM_SCRIPT_ALIASES.items():
        if raw_name in scripts:
            cmds.append(
                DetectedCommand(name=canonical, command=f"npm run {raw_name}", source=source)
            )
    return cmds


def parse_makefile_targets(content: str, source: str) -> list[DetectedCommand]:
    cmds: list[DetectedCommand] = []
    lines = content.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^([A-Za-z0-9_.-]+):(?!=)", line)
        if not m:
            continue
        target = m.group(1)
        canonical = _MAKE_TARGET_ALIASES.get(target)
        if not canonical:
            continue
        # Prefer the first recipe line (tab-indented) as the concrete command.
        recipe = ""
        for follow in lines[i + 1 :]:
            if follow.startswith("\t"):
                recipe = follow.strip()
                break
            if follow.strip() and not follow.startswith("\t"):
                break
        cmds.append(
            DetectedCommand(name=canonical, command=recipe or f"make {target}", source=source)
        )
    return cmds


def detect_stacks(files: dict[str, str]) -> list[StackInfo]:
    langs: dict[str, set[str]] = {}
    for path, content in files.items():
        base = path.rsplit("/", 1)[-1]
        lang = _LANG_BY_MANIFEST.get(base)
        if not lang:
            continue
        fw = langs.setdefault(lang, set())
        low = content.lower()
        for name, pattern in _FRAMEWORK_PATTERNS.items():
            if pattern.search(low):
                fw.add(name)
    return [
        StackInfo(language=lang, frameworks=tuple(sorted(fws)))
        for lang, fws in sorted(langs.items())
    ]
