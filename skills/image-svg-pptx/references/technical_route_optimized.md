# Optimized Technical Route: Image to SVG to Editable PPTX

## Why the SVG Intermediate Helps

A direct image-to-PPTX workflow often fails because the agent has to decide visual reconstruction and PowerPoint implementation at the same time. SVG separates the problem into two layers:

1. Visual reconstruction layer: represent the slide accurately with coordinates, text, fills, strokes, clipped assets, and z-order.
2. Office reconstruction layer: map supported SVG and layout elements to native PowerPoint shapes.

This reduces layout drift and makes debugging easier. If the PPTX is wrong, inspect the SVG first. If the SVG is right but PPTX is wrong, fix the converter. If the SVG is wrong, fix the layout plan.

## Recommended Architecture

```text
source.png
  -> preprocess_image.py
normalized.png + source_meta.json
  -> visual and semantic reasoning
layout_plan.json
  -> crop_assets.py
assets/*.png
  -> plan_to_svg.py
reconstruction.svg
  -> plan_to_pptx.py or svg_to_pptx_editable.py
reconstructed.pptx
  -> QA
qa_report.md + corrected layout_plan.json
```

## Three-Layer Reconstruction Strategy

### Layer A: Editable Structure

Use native PPT shapes for:

- background rectangles and bands.
- title, subtitle, and body text.
- card containers.
- dividers and connector lines.
- tables.
- simple bar and line charts.
- simple icons made from circles, rectangles, and lines.

### Layer B: SVG Vector Fidelity

Use SVG for:

- precise decorative vector patterns.
- simple but tedious icon or path art.
- mask or clip-path regions where PowerPoint approximation is acceptable.

### Layer C: Cropped Asset Fidelity

Use cropped PNG assets for:

- photographs.
- screenshots.
- logos.
- dense charts.
- complex icons.
- AI-generated illustration fragments.
- unreadable or uncertain text blocks that should not be hallucinated.

## Quality Policy

The best result usually comes from mixed editability, not maximum editability.

- A 90 percent editable slide that looks correct is better than a 100 percent editable slide that looks poor.
- Main narrative text must be editable.
- Complex image and logo regions should stay visually faithful.
- If a chart is too dense, use image fallback and optionally rebuild the key labels as editable overlays.
