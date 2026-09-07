# Gugu favicon source

The user approved the Gugu head direction on 2026-09-07. `gugu-source.png`
is the final transparent output from built-in ImageGen. The source is retained
for future exports; it is not copied into the deployed Web bundle.

Generation brief: preserve the existing mascot's brown owl head, cream face,
purple eyes and gold beak; shorten the antlers, enlarge the face, simplify fine
details and remove the outer background to actual alpha transparency.

Export recipe (Pillow, no drawing or recoloring): locate the bounding box of
alpha > 128; center a square on that box, with side equal to its longest edge
plus 3.5% padding on each side. Preserve the original alpha, resize with Lanczos
to 16 and 32 pixels, and write the PNGs under `public/brand`. Export an ICO from
a 256px resize with 16, 32, 48, 64 and 256px entries. The `gugu-v1` filenames
version the browser cache; use a new version when replacing the artwork.

Only H5 copies `public/brand` into its configured output directory. HTML icon
URLs use the build's public path, including preview subpaths.
