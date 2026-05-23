# Personal Skills

Personal Agent Skills repository for reusable Codex workflows.

Skills are self-contained folders of instructions, scripts, and supporting resources that an agent can load when a task matches the skill description. This repository follows the public Agent Skills pattern used by the [OpenAI skills repository](https://github.com/openai/skills) and the [Anthropic skills repository](https://github.com/anthropics/skills).

## Repository Layout

```text
skills/
  <skill-name>/
    SKILL.md
    agents/
      openai.yaml
    scripts/
    references/
    assets/
```

Only `SKILL.md` is required for a skill. Other folders are included when the skill needs UI metadata, executable helpers, detailed references, or reusable assets.

## Skills

| Skill | Purpose |
| --- | --- |
| [`image-svg-pptx`](skills/image-svg-pptx/) | Convert slide-like images into high-fidelity SVG and editable PowerPoint artifacts. |
| [`paper-review`](skills/paper-review/) | Submit existing PDF papers to paperreview.ai, poll or fetch review reports, and save token, JSON, and Markdown artifacts. |

## Installing Locally

Clone the repository:

```powershell
git clone https://github.com/Tsumugii24/skills.git
cd skills
```

Install a skill into Codex by copying its folder into your Codex skills directory:

```powershell
Copy-Item -Recurse -Force ./skills/paper-review "$env:USERPROFILE/.codex/skills/paper-review"
Copy-Item -Recurse -Force ./skills/image-svg-pptx "$env:USERPROFILE/.codex/skills/image-svg-pptx"
```

Restart Codex after installing or updating skills so the new metadata is discovered.

## Developing Skills

Each skill should be small, task-focused, and directly usable by another agent. Keep procedural guidance in `SKILL.md`; move longer details into `references/`; put repeatable automation in `scripts/`; and avoid adding extra docs inside each skill unless they are required for execution.

Validate a skill before committing:

```powershell
python "$env:USERPROFILE/.codex/skills/.system/skill-creator/scripts/quick_validate.py" ./skills/paper-review
python "$env:USERPROFILE/.codex/skills/.system/skill-creator/scripts/quick_validate.py" ./skills/image-svg-pptx
```

For Python helper scripts, also run:

```powershell
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "skills-pycache"
python -m py_compile ./skills/paper-review/scripts/paperreview_ai_submit.py
```

## Safety

These skills are personal automation helpers. Review each skill before use, especially scripts that call external services, upload files, or touch private data. Keep secrets in environment variables or local configuration files that are ignored by Git.

## References

- [OpenAI Agent Skills](https://github.com/openai/skills)
- [Anthropic Skills](https://github.com/anthropics/skills)
- [Agent Skills open standard](https://agentskills.io)
