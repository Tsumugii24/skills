# VBA Helper Notes

VBA is optional. Use it mainly when the user wants to demonstrate the image-to-SVG-to-Office route or when PowerPoint's built-in SVG insertion is useful.

Recommended use:

1. Generate `reconstruction.svg`.
2. Insert the SVG into PowerPoint as a full-slide fallback or reference layer.
3. Add editable overlays with native shapes and text from the generated PPTX.

Limitations:

- PowerPoint may not expose every SVG path as a clean editable shape through automation.
- Filters, masks, gradients, and complex paths may import visually but not become clean native shapes.
- For production output, prefer `plan_to_pptx.py` for native editable elements.
