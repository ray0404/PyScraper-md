/**
 * sanitizer.ts — port of `md_scraper.sanitizer.MarkdownSanitizer`.
 * Post-processes Markdown: collapses excess newlines, strips trailing
 * whitespace, fixes headers missing a space after `#`, drops empty
 * links/images and stray HTML comments.
 */
export class MarkdownSanitizer {
  sanitize(markdown: string): string {
    let cleaned = markdown;
    // 1. Remove excessive newlines (more than 2).
    cleaned = cleaned.replace(/\n{3,}/g, "\n\n");
    // 2. Strip trailing whitespace from lines.
    cleaned = cleaned.replace(/[ \t]+$/gm, "");
    // 3. Fix headers that don't have a space after #.
    cleaned = cleaned.replace(/^([ \t]{0,3}#+)([^#\s])/gm, "$1 $2");
    // 4. Remove empty links/images (only if they are truly empty).
    cleaned = cleaned.replace(/!?\[\s*\]\(\s*\)/g, "");
    // 5. Clean up residue HTML comments if they weren't stripped.
    cleaned = cleaned.replace(/<!--.*?-->/gs, "");
    return cleaned.trim();
  }

  static stripNonAscii(text: string): string {
    // eslint-disable-next-line no-control-regex
    return text.replace(/[^\x00-\x7F]/g, "");
  }
}
