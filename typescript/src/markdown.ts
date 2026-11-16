/**
 * markdown.ts — GitHub Flavored Markdown conversion, a faithful port of
 * the `markdownify` library's `MarkdownConverter` (v1.2.x, as used by
 * the Python engine) over the tree from `html.ts`.
 *
 * The conversion rules — whitespace collapsing at child boundaries,
 * inline chomping, heading/list/table/block handling, escaping — are
 * copied from markdownify's algorithm so the two engines agree field
 * for field on the same input. Options mirror the Python call site:
 * ATX headings, `-` bullets, and a code-language callback.
 */
import {
  type Node,
  type ElNode,
  type TextNode,
  type DocNode,
  findAll,
  nextBlockContentSibling,
  previousElementSibling,
  previousElementSiblings,
  previousSibling,
  nextSibling,
  getAttr,
  textContent,
} from "./html.js";

export interface MarkdownOptions {
  /** Bullet characters, cycled by nesting depth. Default `"-"`. */
  bullets?: string;
  /** Called with a `<pre>` element to detect its code language. */
  codeLanguageCallback?: (el: ElNode) => string;
  /** Tags whose conversion is skipped (children are still processed). */
  strip?: string[];
}

const RE_NEWLINE_WS = /[\t \r\n]*[\r\n][\t \r\n]*/g;
const RE_WS = /[\t ]+/g;
const RE_ALL_WS = /[\t \r\n]+/g;
const RE_EXTRACT_NEWLINES = /^(\n*)((?:.*[^\n])?)(\n*)$/s;
const RE_LINE_WITH_CONTENT = /^(.*)/gm;
const RE_BACKTICK_RUNS = /`+/g;

const SHOULD_REMOVE_INSIDE = new Set([
  "p", "blockquote", "article", "div", "section",
  "ol", "ul", "li", "dl", "dt", "dd",
  "table", "thead", "tbody", "tfoot", "tr", "td", "th",
]);

function isHeading(tag: string): boolean {
  return /^h\d+$/.test(tag);
}

function shouldRemoveWhitespaceInside(node: Node | null): boolean {
  if (!node || node.kind !== "el") return false;
  if (isHeading(node.tag)) return true;
  return SHOULD_REMOVE_INSIDE.has(node.tag);
}

function shouldRemoveWhitespaceOutside(node: Node | null): boolean {
  return (
    shouldRemoveWhitespaceInside(node) ||
    (node !== null && node.kind === "el" && node.tag === "pre")
  );
}

function isBlockContent(node: Node | null): boolean {
  if (!node) return false;
  if (node.kind === "el") return true;
  if (node.kind === "comment" || node.kind === "doctype" || node.kind === "pi") {
    return false;
  }
  if (node.kind === "text") return node.text.trim() !== "";
  return false;
}

function chomp(text: string): [string, string, string] {
  const prefix = text.length > 0 && text[0] === " " ? " " : "";
  const suffix =
    text.length > 0 && text[text.length - 1] === " " ? " " : "";
  return [prefix, suffix, text.trim()];
}

function escapeText(text: string): string {
  if (!text) return "";
  return text.replace(/\*/g, "\\*").replace(/_/g, "\\_");
}

type ParentTags = Set<string>;

function abstractInline(markup: string) {
  return (
    _el: ElNode,
    text: string,
    parentTags: ParentTags,
  ): string => {
    if (parentTags.has("_noformat")) return text;
    const [prefix, suffix, stripped] = chomp(text);
    if (!stripped) return "";
    return `${prefix}${markup}${stripped}${markup}${suffix}`;
  };
}

type ConvertFn = (
  el: ElNode,
  text: string,
  parentTags: ParentTags,
) => string;

export class MarkdownConverter {
  private readonly bullets: string;
  private readonly codeLanguageCallback?: (el: ElNode) => string;
  private readonly strip: Set<string>;

  constructor(options: MarkdownOptions = {}) {
    this.bullets = options.bullets ?? "-";
    this.codeLanguageCallback = options.codeLanguageCallback;
    this.strip = new Set((options.strip ?? []).map((t) => t.toLowerCase()));
  }

  /** Convert a parsed document (or any element) to Markdown. */
  convert(node: DocNode | ElNode): string {
    if (node.kind === "doc") {
      const text = this.processChildren(node, new Set());
      return text.replace(/^\n+/, "").replace(/\n+$/, "");
    }
    return this.processTag(node, new Set());
  }

  private processChildren(
    node: DocNode | ElNode,
    parentTags: ParentTags,
  ): string {
    const shouldRemoveInside =
      node.kind === "el" ? shouldRemoveWhitespaceInside(node) : false;

    const canIgnore = (child: Node): boolean => {
      if (child.kind === "el") return false;
      if (
        child.kind === "comment" ||
        child.kind === "doctype" ||
        child.kind === "pi"
      ) {
        return true;
      }
      if (child.kind === "text") {
        if (child.text.trim() !== "") return false;
        if (
          shouldRemoveInside &&
          (!previousSibling(child) || !nextSibling(child))
        ) {
          return true;
        }
        if (
          shouldRemoveWhitespaceOutside(previousSibling(child)) ||
          shouldRemoveWhitespaceOutside(nextSibling(child))
        ) {
          return true;
        }
        return false;
      }
      return true;
    };

    const childrenToConvert = node.children.filter((c) => !canIgnore(c));

    const parentTagsForChildren = new Set(parentTags);
    if (node.kind === "el") {
      parentTagsForChildren.add(node.tag);
      if (isHeading(node.tag) || node.tag === "td" || node.tag === "th") {
        parentTagsForChildren.add("_inline");
      }
      if (
        node.tag === "pre" ||
        node.tag === "code" ||
        node.tag === "kbd" ||
        node.tag === "samp"
      ) {
        parentTagsForChildren.add("_noformat");
      }
    }

    const childStrings = childrenToConvert
      .map((child) => this.processElement(child, parentTagsForChildren))
      .filter((s) => s !== "");

    const inPre =
      (node.kind === "el" && node.tag === "pre") || parentTags.has("pre");
    if (!inPre) {
      // Collapse newlines at child element boundaries.
      const updated: string[] = [""];
      for (const childString of childStrings) {
        const m = RE_EXTRACT_NEWLINES.exec(childString);
        let leading = "";
        let content = "";
        let trailing = "";
        if (m) {
          leading = m[1];
          content = m[2];
          trailing = m[3];
        } else {
          content = childString;
        }
        if (updated[updated.length - 1] && leading) {
          const prevTrailing = updated.pop() as string;
          const num = Math.min(
            2,
            Math.max(prevTrailing.length, leading.length),
          );
          leading = "\n".repeat(num);
        }
        updated.push(leading, content, trailing);
      }
      return updated.join("");
    }
    return childStrings.join("");
  }

  private processElement(node: Node, parentTags: ParentTags): string {
    if (node.kind === "text") return this.processText(node, parentTags);
    if (node.kind === "el") return this.processTag(node, parentTags);
    return "";
  }

  private processTag(node: ElNode, parentTags: ParentTags): string {
    const text = this.processChildren(node, parentTags);
    const fn = this.getConvertFn(node.tag);
    if (!fn) return text;
    return fn(node, text, parentTags);
  }

  private processText(el: TextNode, parentTags: ParentTags): string {
    let text = el.text;
    if (!parentTags.has("pre")) {
      text = text.replace(RE_NEWLINE_WS, "\n").replace(RE_WS, " ");
    }
    if (!parentTags.has("_noformat")) {
      text = escapeText(text);
    }
    const prev = previousSibling(el);
    const next = nextSibling(el);
    const parent = el.parent;
    if (
      shouldRemoveWhitespaceOutside(prev) ||
      (parent && shouldRemoveWhitespaceInside(parent) && !prev)
    ) {
      text = text.replace(/^[ \t\r\n]+/, "");
    }
    if (
      shouldRemoveWhitespaceOutside(next) ||
      (parent && shouldRemoveWhitespaceInside(parent) && !next)
    ) {
      text = text.replace(/\s+$/, "");
    }
    return text;
  }

  private getConvertFn(tag: string): ConvertFn | null {
    const lower = tag.toLowerCase();
    if (this.strip.has(lower)) return null;
    switch (lower) {
      case "a": return (el, text, pt) => this.convertA(el, text, pt);
      case "b":
      case "strong": return abstractInline("**");
      case "em":
      case "i": return abstractInline("*");
      case "del":
      case "s": return abstractInline("~~");
      case "sub":
      case "sup": return abstractInline("");
      case "blockquote": return (el, text, pt) => this.convertBlockquote(el, text, pt);
      case "br": return (el, text, pt) => this.convertBr(el, text, pt);
      case "code":
      case "kbd":
      case "samp": return (el, text, pt) => this.convertCode(el, text, pt);
      case "div":
      case "article":
      case "section":
      case "dl": return (el, text, pt) => this.convertDiv(el, text, pt);
      case "dd": return (el, text, pt) => this.convertDd(el, text, pt);
      case "dt": return (el, text, pt) => this.convertDt(el, text, pt);
      case "hr": return () => "\n\n---\n\n";
      case "img": return (el, text, pt) => this.convertImg(el, text, pt);
      case "video": return (el, text, pt) => this.convertVideo(el, text, pt);
      case "ul":
      case "ol": return (el, text, pt) => this.convertList(el, text, pt);
      case "li": return (el, text, pt) => this.convertLi(el, text, pt);
      case "p": return (el, text, pt) => this.convertP(el, text, pt);
      case "pre": return (el, text, pt) => this.convertPre(el, text, pt);
      case "q": return (_el, text, _pt) => `"${text}"`;
      case "script":
      case "style": return () => "";
      case "table": return (el, text, pt) => this.convertTable(el, text, pt);
      case "caption": return (_el, text, _pt) => `${text.trim()}\n\n`;
      case "figcaption": return (_el, text, _pt) => `\n\n${text.trim()}\n\n`;
      case "td": return (el, text, pt) => this.convertTd(el, text, pt);
      case "th": return (el, text, pt) => this.convertTh(el, text, pt);
      case "tr": return (el, text, pt) => this.convertTr(el, text, pt);
      default: {
        const hm = /^h(\d+)$/.exec(lower);
        if (hm) {
          const n = parseInt(hm[1], 10);
          return (el, text, parentTags) => this.convertH(n, el, text, parentTags);
        }
        return null;
      }
    }
  }

  // -- conversion functions (mirroring markdownify's convert_* methods) --

  private convertA(el: ElNode, text: string, parentTags: ParentTags): string {
    if (parentTags.has("_noformat")) return text;
    const [prefix, suffix, stripped] = chomp(text);
    if (!stripped) return "";
    const href = getAttr(el, "href");
    const title = getAttr(el, "title");
    if (
      href !== undefined &&
      stripped.replace(/\\_/g, "_") === href &&
      !title
    ) {
      return `<${href}>`;
    }
    const titlePart = title
      ? ` "${title.replace(/"/g, '\\"')}"`
      : "";
    return href !== undefined
      ? `${prefix}[${stripped}](${href}${titlePart})${suffix}`
      : stripped;
  }

  private convertBlockquote(
    el: ElNode,
    text: string,
    parentTags: ParentTags,
  ): string {
    void el;
    const stripped = text.replace(/^[ \t\r\n]+/, "").replace(/[ \t\r\n]+$/, "");
    if (parentTags.has("_inline")) return ` ${stripped} `;
    if (!stripped) return "\n";
    const indented = stripped.replace(RE_LINE_WITH_CONTENT, (_m, line: string) =>
      line ? `> ${line}` : ">",
    );
    return `\n${indented}\n\n`;
  }

  private convertBr(el: ElNode, text: string, parentTags: ParentTags): string {
    void el;
    if (parentTags.has("_inline")) return text ? `${text} ` : " ";
    return `  \n${text}`;
  }

  private convertCode(el: ElNode, text: string, parentTags: ParentTags): string {
    void el;
    if (parentTags.has("_noformat")) return text;
    const [prefix, suffix, stripped] = chomp(text);
    if (!stripped) return "";
    const runs = stripped.match(RE_BACKTICK_RUNS) ?? [];
    const maxBackticks = runs.reduce((m, r) => Math.max(m, r.length), 0);
    const delimiter = "`".repeat(maxBackticks + 1);
    const body = maxBackticks > 0 ? ` ${stripped} ` : stripped;
    return `${prefix}${delimiter}${body}${delimiter}${suffix}`;
  }

  private convertDiv(el: ElNode, text: string, parentTags: ParentTags): string {
    void el;
    if (parentTags.has("_inline")) return ` ${text.trim()} `;
    const stripped = text.trim();
    return stripped ? `\n\n${stripped}\n\n` : "";
  }

  private convertDd(el: ElNode, text: string, parentTags: ParentTags): string {
    void el;
    const stripped = text.trim();
    if (parentTags.has("_inline")) return ` ${stripped} `;
    if (!stripped) return "\n";
    const indented = stripped.replace(
      RE_LINE_WITH_CONTENT,
      (_m, line: string) => (line ? `    ${line}` : ""),
    );
    return `${`:${indented.slice(1)}`}\n`;
  }

  private convertDt(el: ElNode, text: string, parentTags: ParentTags): string {
    void el;
    let stripped = text.trim().replace(RE_ALL_WS, " ");
    if (parentTags.has("_inline")) return ` ${stripped} `;
    if (!stripped) return "\n";
    return `\n\n${stripped}\n`;
  }

  private convertH(
    n: number,
    _el: ElNode,
    text: string,
    parentTags: ParentTags,
  ): string {
    if (parentTags.has("_inline")) return text;
    const depth = Math.max(1, Math.min(6, n));
    const stripped = text.trim().replace(RE_ALL_WS, " ");
    const hashes = "#".repeat(depth);
    return `\n\n${hashes} ${stripped}\n\n`;
  }

  private convertImg(el: ElNode, _text: string, parentTags: ParentTags): string {
    const alt = getAttr(el, "alt") ?? "";
    const src = getAttr(el, "src") ?? "";
    const title = getAttr(el, "title") ?? "";
    const titlePart = title ? ` "${title.replace(/"/g, '\\"')}"` : "";
    // keep_inline_images_in is empty in the Python call site, so an
    // image inside a heading or table cell degrades to its alt text.
    if (parentTags.has("_inline")) return alt;
    return `![${alt}](${src}${titlePart})`;
  }

  private convertVideo(
    el: ElNode,
    text: string,
    parentTags: ParentTags,
  ): string {
    if (parentTags.has("_inline")) return text;
    let src = getAttr(el, "src") ?? "";
    if (!src) {
      const sources = findAll(el, (e) => e.tag === "source" && getAttr(e, "src") !== undefined);
      if (sources.length > 0) src = getAttr(sources[0], "src") ?? "";
    }
    const poster = getAttr(el, "poster") ?? "";
    if (src && poster) return `[![${text}](${poster})](${src})`;
    if (src) return `[${text}](${src})`;
    if (poster) return `![${text}](${poster})`;
    return text;
  }

  private convertList(el: ElNode, text: string, parentTags: ParentTags): string {
    const next = nextBlockContentSibling(el);
    let beforeParagraph = false;
    if (next && next.kind === "el" && next.tag !== "ul" && next.tag !== "ol") {
      beforeParagraph = true;
    }
    if (parentTags.has("li")) {
      return `\n${text.replace(/\s+$/, "")}`;
    }
    return `\n\n${text}${beforeParagraph ? "\n" : ""}`;
  }

  private convertLi(el: ElNode, text: string, _parentTags: ParentTags): string {
    const stripped = text.trim();
    if (!stripped) return "\n";
    const parent = el.parent;
    let bullet: string;
    if (parent && parent.kind === "el" && parent.tag === "ol") {
      const startAttr = getAttr(parent, "start");
      const start =
        startAttr !== undefined && /^\d+$/.test(startAttr)
          ? parseInt(startAttr, 10)
          : 1;
      const prevLis = previousElementSiblings(el).filter(
        (sib) => sib.tag === "li",
      ).length;
      bullet = `${start + prevLis}.`;
    } else {
      let depth = -1;
      let cur: Node | null = el;
      while (cur) {
        if (cur.kind === "el" && cur.tag === "ul") depth += 1;
        cur = cur.parent;
      }
      bullet = this.bullets[depth % this.bullets.length];
    }
    bullet = `${bullet} `;
    const width = bullet.length;
    const indent = " ".repeat(width);
    const indented = stripped.replace(
      RE_LINE_WITH_CONTENT,
      (_m, line: string) => (line ? `${indent}${line}` : ""),
    );
    return `${bullet}${indented.slice(width)}\n`;
  }

  private convertP(el: ElNode, text: string, parentTags: ParentTags): string {
    void el;
    if (parentTags.has("_inline")) {
      return ` ${text.replace(/^[ \t\r\n]+/, "").replace(/[ \t\r\n]+$/, "")} `;
    }
    const stripped = text.replace(/^[ \t\r\n]+/, "").replace(/[ \t\r\n]+$/, "");
    return stripped ? `\n\n${stripped}\n\n` : "";
  }

  private convertPre(el: ElNode, text: string, _parentTags: ParentTags): string {
    if (!text) return "";
    let language = "";
    if (this.codeLanguageCallback) {
      language = this.codeLanguageCallback(el) || language;
    }
    // strip_pre == STRIP: drop leading whitespace-through-first-newline
    // and all trailing spaces/newlines.
    text = text.replace(/^[ \n]*\n/, "").replace(/[ \n]*$/, "");
    return `\n\n\`\`\`${language}\n${text}\n\`\`\`\n\n`;
  }

  private convertTable(el: ElNode, text: string, _parentTags: ParentTags): string {
    void el;
    return `\n\n${text.trim()}\n\n`;
  }

  private convertTd(el: ElNode, text: string, _parentTags: ParentTags): string {
    const colspan = getColspan(el);
    return ` ${text.trim().replace(/\n/g, " ")}${" |".repeat(colspan)}`;
  }

  private convertTh(el: ElNode, text: string, _parentTags: ParentTags): string {
    const colspan = getColspan(el);
    return ` ${text.trim().replace(/\n/g, " ")}${" |".repeat(colspan)}`;
  }

  private convertTr(el: ElNode, text: string, _parentTags: ParentTags): string {
    const cells = findAll(el, (e) => e.tag === "td" || e.tag === "th");
    const isFirstRow = previousElementSibling(el) === null;
    const parent = el.parent;
    const parentTag = parent && parent.kind === "el" ? parent.tag : "";
    const isHeadRow =
      cells.every((c) => c.tag === "th") ||
      (parentTag === "thead" &&
        parent !== null &&
        parent.kind === "el" &&
        findAll(parent, (e) => e.tag === "tr").length === 1);
    const tableEl =
      parent !== null && parent.kind === "el" ? parent.parent : null;
    const hasThead =
      tableEl !== null && tableEl.kind === "el"
        ? findAll(tableEl, (e) => e.tag === "thead").length >= 1
        : false;
    const isHeadRowMissing =
      (isFirstRow && parentTag !== "tbody") ||
      (isFirstRow && parentTag === "tbody" && !hasThead);
    let fullColspan = 0;
    for (const cell of cells) {
      fullColspan += getColspan(cell);
    }
    // table_infer_header is False in the Python call site.
    let overline = "";
    let underline = "";
    if (isHeadRow && isFirstRow) {
      underline += `| ${Array(fullColspan).fill("---").join(" | ")} |\n`;
    } else if (
      isHeadRowMissing ||
      (isFirstRow &&
        (parentTag === "table" ||
          (parentTag === "tbody" &&
            parent !== null &&
            parent.kind === "el" &&
            previousElementSibling(parent) === null)))
    ) {
      overline += `| ${Array(fullColspan).fill("").join(" | ")} |\n`;
      overline += `| ${Array(fullColspan).fill("---").join(" | ")} |\n`;
    }
    return `${overline}|${text}\n${underline}`;
  }
}

function getColspan(el: ElNode): number {
  const attr = getAttr(el, "colspan");
  if (attr !== undefined && /^\d+$/.test(attr)) {
    return Math.max(1, Math.min(1000, parseInt(attr, 10)));
  }
  return 1;
}

/** Convert a parsed document/element to Markdown with default options. */
export function convertToMarkdown(
  node: DocNode | ElNode,
  options: MarkdownOptions = {},
): string {
  return new MarkdownConverter(options).convert(node);
}
