---
name: image-svg-pptx
description: Use when converting slide screenshots, report pages, UI mockups, academic figures, posters, or AI-generated slide images into high-fidelity SVG and editable PowerPoint artifacts.
---

# Image SVG PPTX

## Overview

Use this skill to reconstruct a raster slide-like image as a mixed editable PowerPoint deck. The stable intermediate is a semantic `layout_plan.json` and a matching SVG; the final PPTX should make text and simple structure editable while preserving complex visuals as cropped assets.

## Default Workflow

1. Normalize the source image without modifying the original.
2. Build `layout_plan.json` from visual reasoning and the schema in `references/layout_plan_schema.md`.
3. Crop complex visual regions into `work/assets`.
4. Generate `work/reconstruction.svg`.
5. Generate `work/reconstructed.pptx` from the layout plan.
6. Run visual and editability QA, then correct the layout plan and regenerate if the first result is visibly wrong.

## Commands

```powershell
python scripts/preprocess_image.py input.png --out work/normalized.png --meta work/source_meta.json
python scripts/validate_plan.py work/layout_plan.json
python scripts/crop_assets.py work/normalized.png work/layout_plan.json --out work/assets
python scripts/plan_to_svg.py work/layout_plan.json --assets work/assets --out work/reconstruction.svg
python scripts/plan_to_pptx.py work/layout_plan.json --assets work/assets --out work/reconstructed.pptx
python scripts/visual_qa.py --plan work/layout_plan.json --svg work/reconstruction.svg --pptx work/reconstructed.pptx --out work/qa_report.md
```

If only an SVG exists, use the fallback converter:

```powershell
python scripts/svg_to_pptx_editable.py work/reconstruction.svg --out work/reconstructed.pptx
```

## Output Targets

Produce these files when possible:

- `reconstructed.pptx`: main editable PowerPoint deliverable.
- `reconstruction.svg`: visual intermediate for inspection and debugging.
- `layout_plan.json`: semantic reconstruction plan.
- `assets/`: cropped photos, logos, screenshots, icons, dense charts, or fallback regions.
- `qa_report.md`: concise visual fidelity and editability assessment.

## Reconstruction Policy

- Convert headings, body text, cards, lines, simple shapes, simple tables, and simple charts into editable PowerPoint elements.
- Preserve photos, dense screenshots, logos, complex icons, complex charts, gradients, and decorative art as cropped assets or SVG fallbacks.
- Do not hallucinate unreadable text. Mark uncertain text with `needs_review: true` or preserve the region as an image asset.
- Prefer visual usefulness over maximum editability. A mostly editable slide that looks correct is better than a fully editable slide that looks poor.
- Do not stretch text horizontally to match the source. Adjust font size, box width, line breaks, and spacing instead.

## References

- `references/layout_plan_schema.md`: required layout plan fields and examples.
- `references/reconstruction_rules.md`: decisions for text, shapes, logos, charts, and fallbacks.
- `references/quality_checklist.md`: QA checklist for final artifacts.
- `references/prompts.md`: prompts for layout planning and correction passes.
- `references/technical_route_optimized.md`: architecture notes for debugging reconstruction quality.
- `references/vba_rules.md`: optional VBA fallback guidance.

## Guardrails

- Keep all skill text and example content in English.
- Keep generated work products in a local `work/` directory or a user-specified output directory.
- Do not commit generated `__pycache__`, temporary previews, extracted assets, or reconstructed decks to the skill package.
- Do not claim the PPTX is editable until the main elements have been checked in PowerPoint or through a suitable inspection workflow.
