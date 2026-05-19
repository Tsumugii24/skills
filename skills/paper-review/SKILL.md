---
name: paper-review
description: Submit existing PDF papers to paperreview.ai for venue-style peer review, fetch finished reviews by existing review token, save review tokens plus JSON and Markdown reports, and summarize or action-plan from saved paperreview.ai output. Use when Codex is asked to submit a paper PDF for external AI review, poll a paperreview.ai token, retrieve a completed review report, or work with paperreview.ai review artifacts.
---

# Paper Review

## Overview

Use this skill to submit an existing PDF to paperreview.ai, poll for the finished report, and save structured review artifacts. Treat external upload as sensitive: do not send an unpublished paper to paperreview.ai until the user explicitly confirms that upload is allowed.

## Workflow

1. Identify the PDF path from the user request. If no PDF path is available, ask for one.
2. Explain that paperreview.ai is an external service and ask for confirmation before upload unless the user already gave explicit approval in the current request.
3. Require an email address for upload. Prefer `--email`; use `PAPERREVIEW_EMAIL` only when it is already set or the user asks to use it.
4. Run the helper script from this skill directory. Add `--confirm-external-upload` only after the user has approved the upload.
5. Report the saved token, JSON, and Markdown paths. If the user wants a summary or revision plan, read the saved Markdown or JSON and synthesize from that artifact.

## Commands

Submit a PDF and wait for the completed review:

```powershell
python ./scripts/paperreview_ai_submit.py <paper.pdf> --email <email> --venue ICLR --confirm-external-upload
```

By default, polling starts with a 3-minute wait after the first not-ready response and adds 1 minute to each later wait. Override with `--poll-interval <seconds>` and `--poll-increment <seconds>` only when the user asks for a different schedule.

Submit and save only the review token:

```powershell
python ./scripts/paperreview_ai_submit.py <paper.pdf> --email <email> --venue NeurIPS --no-wait --confirm-external-upload
```

Fetch a review later by token:

```powershell
python ./scripts/paperreview_ai_submit.py --token <review-token> --output-dir <reviews-dir>
```

Use `--output-dir` when the user wants artifacts in a specific workspace folder. Without `--output-dir`, upload mode writes under `paperreview_reviews` next to the PDF; token mode writes under `paperreview_reviews` in the current working directory, or under the user home directory if the script is run from the installed skill folder.

## Output

The helper stores each run in a `round_N` folder. Upload mode writes a token JSON file immediately after successful submission, including when `--no-wait` is used. Completed reviews are saved as both raw JSON and Markdown.

## Guardrails

- Do not compile or modify a paper project; this skill expects an already-created `.pdf`.
- Do not upload without explicit user approval in the current conversation.
- Do not hard-code personal email addresses. Use `--email` or an explicitly configured `PAPERREVIEW_EMAIL`.
- Do not perform live upload during skill validation or smoke tests unless the user explicitly asks for it.
