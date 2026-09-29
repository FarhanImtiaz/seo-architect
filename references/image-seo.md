# Image SEO

Use meaningful filenames where practical, accurate concise alt text for informative images, empty alt for decorative images, responsive sizing, dimensions to reduce layout shift, and accessible captions when needed. Alt text describes the image’s purpose; it is not a keyword field.

`scripts/seo_tools.py images` (or `scan_images.py`) checks `<img>`/`<Image>`/`<NuxtImg>` tags: missing alt (MEDIUM), empty alt (INFO — confirm decorative, never treated as an error), alt matching the filename or a generic/repeated word (LOW), missing width/height on a raw `<img>` (LOW — layout shift, see [references/winning-patterns.md](winning-patterns.md) P11), `loading="lazy"` on the first image in a file (LOW — likely the LCP image), files over 300KB in `public`/`static` (LOW), and legacy formats (INFO). Astro’s `<Image>` compiles away at build time and needs a rendered/`--built-dir` check, not just source inspection.
