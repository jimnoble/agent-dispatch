#!/usr/bin/env python3
from pathlib import Path

p = Path("SKILL.md")
text = p.read_text(encoding="utf-8")
if not text.startswith("---\n"):
    raise SystemExit("SKILL.md missing YAML frontmatter")
end = text.find("\n---\n", 4)
if end < 0:
    raise SystemExit("SKILL.md frontmatter not closed")
front = text[4:end]
required = {"name", "description"}
keys = {line.split(":", 1)[0].strip() for line in front.splitlines() if ":" in line}
missing = required - keys
if missing:
    raise SystemExit(f"SKILL.md missing required frontmatter keys: {sorted(missing)}")
if "name: agent-dispatch" not in front:
    raise SystemExit("skill name must be agent-dispatch")
for required_path in ("scripts/dispatch.py", "scripts/usage.py", "scripts/bootstrap_agents.py", "references/routing.md", "references/learning.md", "references/contracts.md", "references/parallel-safety.md", "agents/openai.yaml"):
    if not Path(required_path).exists():
        raise SystemExit(f"missing required skill resource: {required_path}")
print("standalone skill package OK")
