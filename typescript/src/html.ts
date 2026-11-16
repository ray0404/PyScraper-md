/**
 * html.ts — dependency-free, tolerant HTML parser, serializer and tree
 * helpers for the TypeScript scraper engine.
 *
 * The parser mirrors the observable behaviour of the Python side's
 * BeautifulSoup/lxml pipeline closely enough for byte-comparable output
 * on well-formed pages:
 *   - tag and attribute names are lower-cased;
 *   - attributes serialize sorted alphabetically by name (lxml does this);
 *   - boolean attributes serialize as `name=""`;
 *   - attribute values use double quotes, single quotes when the value
 *     contains `"` but not `'`;
 *   - text escapes `&`, `<`, `>` on serialization;
 *   - void elements serialize self-closed (`<br/>`, `<img .../>`);
 *   - implied end tags (`<p>`, `<li>`, table cells, …) are honoured;
 *   - raw-text elements (script/style/…) keep their contents verbatim;
 *   - whitespace-only text nodes collapse to `\n` when they contain a
 *     newline, otherwise to a single space (libxml2 blank-node rule),
 *     except inside <pre> and raw-text elements;
 *   - the document is normalised to `<html>` with `<head>`/`<body>`
 *     children, created only when there is content for them.
 *
 * This is a faithful re-implementation of the engine that previously
 * lived in the PyScraper-md Space (`server/src/scraper.ts`); the Space
 * does not expose its source for export, so this file was rebuilt from
 * the Python source (the spec) and the recorded inspection of the
 * Space engine. It is not a byte copy.
 */

export interface DocNode {
  kind: "doc";
  children: Node[];
  parent: null;
}

export interface ElNode {
  kind: "el";
  tag: string;
  /** Attributes in source order; names lower-cased, values unescaped. */
  attrs: Array<[string, string]>;
  children: Node[];
  parent: DocNode | ElNode | null;
}

export interface TextNode {
  kind: "text";
  text: string;
  parent: DocNode | ElNode | null;
}

export interface CommentNode {
  kind: "comment";
  text: string;
  parent: DocNode | ElNode | null;
}

export interface DoctypeNode {
  kind: "doctype";
  /** Inner text of the doctype, e.g. `html`. */
  text: string;
  parent: DocNode | ElNode | null;
}

export interface PiNode {
  kind: "pi";
  /** Raw text including the `<?` … `?>` markers. */
  text: string;
  parent: DocNode | ElNode | null;
}

export type Node = DocNode | ElNode | TextNode | CommentNode | DoctypeNode | PiNode;
export type ParentNode = DocNode | ElNode;

export const VOID_ELEMENTS = new Set([
  "area", "base", "br", "col", "embed", "hr", "img", "input",
  "link", "meta", "param", "source", "track", "wbr",
]);

/** Elements whose contents are raw text (no markup parsed inside). */
export const RAW_TEXT_ELEMENTS = new Set([
  "script", "style", "xmp", "iframe", "noembed", "noframes", "noscript",
]);

/** Raw-text elements whose contents still have entities decoded (RCDATA). */
export const RCDATA_ELEMENTS = new Set(["title", "textarea"]);

/** Elements that belong in <head> when they appear before body content. */
const HEAD_ELEMENTS = new Set([
  "title", "meta", "link", "base", "style", "script", "noscript",
]);

// ---------------------------------------------------------------------------
// Named entities
// ---------------------------------------------------------------------------
//
// HTML5 defines ~2231 named entities. We carry the HTML4 set plus the
// commonly-seen HTML5 additions; anything unknown is left literally
// (matching lxml's behaviour of keeping `&unknown;` as text, which the
// serializer then re-escapes to `&amp;unknown;`).

const NAMED_ENTITIES: Record<string, string> = {
  quot: '"', amp: "&", apos: "'", lt: "<", gt: ">", nbsp: " ",
  iexcl: "¡", cent: "¢", pound: "£", curren: "¤", yen: "¥", brvbar: "¦",
  sect: "§", uml: "¨", copy: "©", ordf: "ª", laquo: "«", not: "¬",
  shy: "­", reg: "®", macr: "¯", deg: "°", plusmn: "±", sup2: "²",
  sup3: "³", acute: "´", micro: "µ", para: "¶", middot: "·", cedil: "¸",
  sup1: "¹", ordm: "º", raquo: "»", frac14: "¼", frac12: "½", frac34: "¾",
  iquest: "¿", Agrave: "À", Aacute: "Á", Acirc: "Â", Atilde: "Ã",
  Auml: "Ä", Aring: "Å", AElig: "Æ", Ccedil: "Ç", Egrave: "È",
  Eacute: "É", Ecirc: "Ê", Euml: "Ë", Igrave: "Ì", Iacute: "Í",
  Icirc: "Î", Iuml: "Ï", ETH: "Ð", Ntilde: "Ñ", Ograve: "Ò",
  Oacute: "Ó", Ocirc: "Ô", Otilde: "Õ", Ouml: "Ö", times: "×",
  Oslash: "Ø", Ugrave: "Ù", Uacute: "Ú", Ucirc: "Û", Uuml: "Ü",
  Yacute: "Ý", THORN: "Þ", szlig: "ß", agrave: "à", aacute: "á",
  acirc: "â", atilde: "ã", auml: "ä", aring: "å", aelig: "æ",
  ccedil: "ç", egrave: "è", eacute: "é", ecirc: "ê", euml: "ë",
  igrave: "ì", iacute: "í", icirc: "î", iuml: "ï", eth: "ð",
  ntilde: "ñ", ograve: "ò", oacute: "ó", ocirc: "ô", otilde: "õ",
  ouml: "ö", divide: "÷", oslash: "ø", ugrave: "ù", uacute: "ú",
  ucirc: "û", uuml: "ü", yacute: "ý", thorn: "þ", yuml: "ÿ",
  OElig: "Œ", oelig: "œ", Scaron: "Š", scaron: "š", Yuml: "Ÿ",
  fnof: "ƒ", circ: "ˆ", tilde: "˜", Alpha: "Α", Beta: "Β",
  Gamma: "Γ", Delta: "Δ", Epsilon: "Ε", Zeta: "Ζ", Eta: "Η",
  Theta: "Θ", Iota: "Ι", Kappa: "Κ", Lambda: "Λ", Mu: "Μ",
  Nu: "Ν", Xi: "Ξ", Omicron: "Ο", Pi: "Π", Rho: "Ρ", Sigma: "Σ",
  Tau: "Τ", Upsilon: "Υ", Phi: "Φ", Chi: "Χ", Psi: "Ψ", Omega: "Ω",
  alpha: "α", beta: "β", gamma: "γ", delta: "δ", epsilon: "ε",
  zeta: "ζ", eta: "η", theta: "θ", iota: "ι", kappa: "κ",
  lambda: "λ", mu: "μ", nu: "ν", xi: "ξ", omicron: "ο", pi: "π",
  rho: "ρ", sigmaf: "ς", sigma: "σ", tau: "τ", upsilon: "υ",
  phi: "φ", chi: "χ", psi: "ψ", omega: "ω", thetasym: "ϑ",
  upsih: "ϒ", piv: "ϖ", ensp: " ", emsp: " ", thinsp: " ",
  zwnj: "‌", zwj: "‍", lrm: "‎", rlm: "‏", ndash: "–",
  mdash: "—", lsquo: "‘", rsquo: "’", sbquo: "‚", ldquo: "“",
  rdquo: "”", bdquo: "„", dagger: "†", Dagger: "‡", bull: "•",
  hellip: "…", permil: "‰", prime: "′", Prime: "″", lsaquo: "‹",
  rsaquo: "›", oline: "‾", frasl: "⁄", euro: "€", image: "ℑ",
  weierp: "℘", real: "ℜ", trade: "™", alefsym: "ℵ", larr: "←",
  uarr: "↑", rarr: "→", darr: "↓", harr: "↔", crarr: "↵",
  lArr: "⇐", uArr: "⇑", rArr: "⇒", dArr: "⇓", hArr: "⇔",
  forall: "∀", part: "∂", exist: "∃", empty: "∅", nabla: "∇",
  isin: "∈", notin: "∉", ni: "∋", prod: "∏", sum: "∑",
  minus: "−", lowast: "∗", radic: "√", prop: "∝", infin: "∞",
  ang: "∠", and: "∧", or: "∨", cap: "∩", cup: "∪", int: "∫",
  there4: "∴", sim: "∼", cong: "≅", asymp: "≈", ne: "≠",
  equiv: "≡", le: "≤", ge: "≥", sub: "⊂", sup: "⊃", nsub: "⊄",
  sube: "⊆", supe: "⊇", oplus: "⊕", otimes: "⊗", perp: "⊥",
  sdot: "⋅", lceil: "⌈", rceil: "⌉", lfloor: "⌊", rfloor: "⌋",
  lang: "⟨", rang: "⟩", loz: "◊", spades: "♠", clubs: "♣",
  hearts: "♥", diams: "♦", // HTML4 set ends here
  // Common HTML5 additions seen in the wild:
  apos2: "'", colon: ":", Tab: "\t", NewLine: "\n", excl: "!",
  num: "#", dollar: "$", percnt: "%", ast: "*", plus: "+",
  comma: ",", period: ".", sol: "/", semi: ";", equals: "=",
  quest: "?", commat: "@",lsqb: "[", bsol: "\\", rsqb: "]",
  Hat: "^", lowbar: "_", grave: "`", lcub: "{", verbar: "|",
  rcub: "}", check: "✓", cross: "✗", star: "☆", phone: "☎",
  female: "♀", male: "♂", squ: "□", rx: "℞", copysr: "℗",
 incare: "℅", trade2: "™", hbar: "ℏ", ell: "ℓ", numero: "№",
  ohm: "Ω", mho: "℧", angstrom: "Å", bernou: "ℬ", Cfr: "ℭ",
  Hfr: "ℌ", Ifr: "ℑ", Rfr: "ℜ", Zfr: "ℨ", planck: "ℎ",
  Aopf: "𝔸", Bopf: "𝔹", Dopf: "𝔻", Eopf: "𝔼", Fopf: "𝔽",
  Gopf: "𝔾", Iopf: "𝕀", Jopf: "𝕁", Kopf: "𝕂", Lopf: "𝕃",
  Mopf: "𝕄", Oopf: "𝕆", Sopf: "𝕊", Topf: "𝕋", Uopf: "𝕌",
  Vopf: "𝕍", Wopf: "𝕎", Xopf: "𝕏", Yopf: "𝕐", aopf: "𝕒",
  bopf: "𝕓", copf: "𝕔", dopf: "𝕕", eopf: "𝕖", fopf: "𝕗",
  gopf: "𝕘", hopf: "𝕙", iopf: "𝕚", jopf: "𝕛", kopf: "𝕜",
  lopf: "𝕝", mopf: "𝕞", nopf: "𝕟", oopf: "𝕠", popf: "𝕡",
  qopf: "𝕢", ropf: "𝕣", sopf: "𝕤", topf: "𝕥", uopf: "𝕦",
  vopf: "𝕧", wopf: "𝕨", xopf: "𝕩", yopf: "𝕪", zopf: "𝕫",
  hairsp: " ", ZeroWidthSpace: "​", ApplyFunction: "⁡",
  InvisibleTimes: "⁢", InvisibleComma: "⁣", NegativeMediumSpace: "​",
  heartsuit: "♥", spadesuit: "♠", clubsuit: "♣", diamsuit: "♦",
  bigstar: "★", emptyset: "∅", nexist: "∄", therefore: "∴",
  because: "∵", approx: "≈", nequiv: "≢", leq: "≤", geq: "≥",
  less: "<", greater: ">", NotEqualTilde: "≂̸", nless: "≮",
  ngtr: "≯", subne: "⊊", supne: "⊋", nsubseteq: "⊈", nsupseteq: "⊉",
  varsubsetneq: "⊊︀", varsupsetneq: "⊋︀", ctdot: "⋯", lmidot: "ŀ",
  Lmidot: "Ŀ", eng: "ŋ", ENG: "Ŋ", ohbar: "⦵", oacute2: "ő",
};

function decodeCodePoint(code: number): string {
  if (code <= 0 || code > 0x10ffff || (code >= 0xd800 && code <= 0xdfff)) {
    return "�";
  }
  return String.fromCodePoint(code);
}

/** Decode HTML entities in a text run (numeric + the named table above). */
export function decodeEntities(text: string): string {
  if (!text.includes("&")) return text;
  return text.replace(/&(#x[0-9a-fA-F]+|#\d+|[A-Za-z][A-Za-z0-9]*);?/g, (whole, body: string) => {
    if (body.startsWith("#x") || body.startsWith("#X")) {
      const code = parseInt(body.slice(2), 16);
      return Number.isNaN(code) ? whole : decodeCodePoint(code);
    }
    if (body.startsWith("#")) {
      const code = parseInt(body.slice(1), 10);
      return Number.isNaN(code) ? whole : decodeCodePoint(code);
    }
    const named = NAMED_ENTITIES[body];
    if (named !== undefined) return named;
    // Unknown named entity: lxml keeps it literally.
    return whole;
  });
}

function escapeText(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function escapeAttrDoubleQuoted(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function escapeAttrSingleQuoted(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/'/g, "&#x27;");
}

// ---------------------------------------------------------------------------
// Tree helpers
// ---------------------------------------------------------------------------

export function makeEl(tag: string, attrs: Array<[string, string]> = []): ElNode {
  return { kind: "el", tag, attrs, children: [], parent: null };
}

export function makeText(text: string): TextNode {
  return { kind: "text", text, parent: null };
}

export function appendChild(parent: ParentNode, child: Node): void {
  child.parent = parent;
  parent.children.push(child);
}

export function getAttr(el: ElNode, name: string): string | undefined {
  const lower = name.toLowerCase();
  for (const [n, v] of el.attrs) {
    if (n === lower) return v;
  }
  return undefined;
}

export function hasAttr(el: ElNode, name: string): boolean {
  return getAttr(el, name) !== undefined;
}

export function setAttr(el: ElNode, name: string, value: string): void {
  const lower = name.toLowerCase();
  for (let i = 0; i < el.attrs.length; i++) {
    if (el.attrs[i][0] === lower) {
      el.attrs[i][1] = value;
      return;
    }
  }
  el.attrs.push([lower, value]);
}

export function removeAttr(el: ElNode, name: string): void {
  const lower = name.toLowerCase();
  el.attrs = el.attrs.filter(([n]) => n !== lower);
}

/** The `class` attribute split on whitespace (bs4 returns a list). */
export function classList(el: ElNode): string[] {
  const cls = getAttr(el, "class");
  if (!cls) return [];
  return cls.split(/\s+/).filter(Boolean);
}

export function hasClass(el: ElNode, name: string): boolean {
  return classList(el).includes(name);
}

/** Concatenated text of all descendant text nodes (bs4 `get_text()`). */
export function textContent(node: Node): string {
  if (node.kind === "text") return node.text;
  if (node.kind === "el" || node.kind === "doc") {
    let out = "";
    for (const child of node.children) out += textContent(child);
    return out;
  }
  return "";
}

/** First child element with the given tag, depth-first (bs4 `find`). */
export function findFirst(node: Node, predicate: (el: ElNode) => boolean): ElNode | null {
  if (node.kind === "el" && predicate(node)) return node;
  if (node.kind === "el" || node.kind === "doc") {
    for (const child of node.children) {
      const found = findFirst(child, predicate);
      if (found) return found;
    }
  }
  return null;
}

/** All matching elements in document order (bs4 `find_all`). */
export function findAll(node: Node, predicate: (el: ElNode) => boolean): ElNode[] {
  const out: ElNode[] = [];
  const walk = (n: Node): void => {
    if (n.kind === "el") {
      if (predicate(n)) out.push(n);
      for (const child of n.children) walk(child);
    } else if (n.kind === "doc") {
      for (const child of n.children) walk(child);
    }
  };
  walk(node);
  return out;
}

/** All matching *descendant* elements (excluding `node` itself). */
export function findDescendants(
  node: ElNode | DocNode,
  predicate: (el: ElNode) => boolean,
): ElNode[] {
  const out: ElNode[] = [];
  const walk = (n: Node): void => {
    if (n.kind === "el") {
      if (predicate(n)) out.push(n);
      for (const child of n.children) walk(child);
    } else if (n.kind === "doc") {
      for (const child of n.children) walk(child);
    }
  };
  for (const child of node.children) walk(child);
  return out;
}

export function findByTag(node: Node, tag: string): ElNode[] {
  const lower = tag.toLowerCase();
  return findAll(node, (el) => el.tag === lower);
}

export function findFirstByTag(node: Node, tag: string): ElNode | null {
  return findFirst(node, (el) => el.tag === tag.toLowerCase());
}

/** Detach a node from its parent. */
export function detach(node: Node): void {
  const parent = node.parent;
  if (!parent) return;
  const idx = parent.children.indexOf(node);
  if (idx >= 0) parent.children.splice(idx, 1);
  node.parent = null;
}

/** Replace `node` with `replacement` in the tree. */
export function replaceWith(node: Node, replacement: Node): void {
  const parent = node.parent;
  if (!parent) return;
  const idx = parent.children.indexOf(node);
  if (idx < 0) return;
  parent.children[idx] = replacement;
  replacement.parent = parent;
  node.parent = null;
}

/** Replace an element with its own children (bs4 `unwrap`). */
export function unwrap(el: ElNode): void {
  const parent = el.parent;
  if (!parent) return;
  const idx = parent.children.indexOf(el);
  if (idx < 0) return;
  const kids = el.children;
  parent.children.splice(idx, 1, ...kids);
  for (const kid of kids) kid.parent = parent;
  el.children = [];
  el.parent = null;
}

export function previousSibling(node: Node): Node | null {
  const parent = node.parent;
  if (!parent) return null;
  const idx = parent.children.indexOf(node);
  return idx > 0 ? parent.children[idx - 1] : null;
}

export function nextSibling(node: Node): Node | null {
  const parent = node.parent;
  if (!parent) return null;
  const idx = parent.children.indexOf(node);
  return idx >= 0 && idx + 1 < parent.children.length
    ? parent.children[idx + 1]
    : null;
}

/** Nearest ancestor element with the given tag (bs4 `find_parent`). */
export function findParent(node: Node, tags: string | string[]): ElNode | null {
  const wanted = new Set(
    (Array.isArray(tags) ? tags : [tags]).map((t) => t.toLowerCase()),
  );
  let cur = node.parent;
  while (cur && cur.kind === "el") {
    if (wanted.has(cur.tag)) return cur;
    cur = cur.parent;
  }
  return null;
}

/** Is `node` a descendant of an element with one of `tags`? */
export function hasAncestor(node: Node, tags: string | string[]): boolean {
  return findParent(node, tags) !== null;
}

/** Previous sibling that is a "block content" element (markdownify helper). */
export function prevBlockContentSibling(el: ElNode): Node | null {
  let cur: Node | null = el;
  while (cur) {
    cur = previousSibling(cur);
    if (isBlockContent(cur)) return cur;
  }
  return null;
}

/** Next sibling that is a "block content" element (markdownify helper). */
export function nextBlockContentSibling(el: ElNode): Node | null {
  let cur: Node | null = el;
  while (cur) {
    cur = nextSibling(cur);
    if (isBlockContent(cur)) return cur;
  }
  return null;
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

/** All previous element siblings (bs4 `find_previous_siblings`). */
export function previousElementSiblings(el: ElNode): ElNode[] {
  const parent = el.parent;
  if (!parent) return [];
  const idx = parent.children.indexOf(el);
  const out: ElNode[] = [];
  for (let i = 0; i < idx; i++) {
    const sib = parent.children[i];
    if (sib.kind === "el") out.push(sib);
  }
  return out;
}

/** Previous sibling element, if any (bs4 `find_previous_sibling`). */
export function previousElementSibling(el: ElNode): ElNode | null {
  const sibs = previousElementSiblings(el);
  return sibs.length ? sibs[sibs.length - 1] : null;
}

// ---------------------------------------------------------------------------
// Minimal CSS matching (for the noise selectors and general queries)
// ---------------------------------------------------------------------------

interface SimpleSelector {
  tag?: string;
  id?: string;
  classes: string[];
  attrName?: string;
  attrValue?: string;
  attrPresent?: boolean;
}

function parseSimpleSelector(part: string): SimpleSelector | null {
  const sel: SimpleSelector = { classes: [] };
  let rest = part.trim();
  if (!rest) return null;
  const tagMatch = /^([a-zA-Z][\w-]*|\*)/.exec(rest);
  if (tagMatch) {
    sel.tag = tagMatch[1].toLowerCase();
    rest = rest.slice(tagMatch[1].length);
  }
  while (rest.length > 0) {
    if (rest.startsWith(".")) {
      const m = /^\.([\w-]+)/.exec(rest);
      if (!m) return null;
      sel.classes.push(m[1]);
      rest = rest.slice(m[0].length);
    } else if (rest.startsWith("#")) {
      const m = /^#([\w-]+)/.exec(rest);
      if (!m) return null;
      sel.id = m[1];
      rest = rest.slice(m[0].length);
    } else if (rest.startsWith("[")) {
      const m = /^\[([\w-]+)(?:=(?:"([^"]*)"|'([^']*)'|([^\]"']+)))?\]/.exec(rest);
      if (!m) return null;
      sel.attrName = m[1].toLowerCase();
      if (m[2] !== undefined || m[3] !== undefined || m[4] !== undefined) {
        sel.attrValue = m[2] ?? m[3] ?? m[4] ?? "";
      } else {
        sel.attrPresent = true;
      }
      rest = rest.slice(m[0].length);
    } else {
      return null;
    }
  }
  return sel;
}

function matchesSimple(el: ElNode, sel: SimpleSelector): boolean {
  if (sel.tag && sel.tag !== "*" && el.tag !== sel.tag) return false;
  if (sel.id !== undefined && getAttr(el, "id") !== sel.id) return false;
  for (const cls of sel.classes) {
    if (!hasClass(el, cls)) return false;
  }
  if (sel.attrName) {
    const v = getAttr(el, sel.attrName);
    if (sel.attrPresent) {
      if (v === undefined) return false;
    } else if (v !== sel.attrValue) {
      return false;
    }
  }
  return true;
}

/**
 * Match an element against a selector list (`a, b`) where each selector
 * is a chain of simple selectors joined by descendant combinators
 * (`div.content a[href]`). Only what the scraper needs is supported.
 */
export function matchesSelector(el: ElNode, selector: string): boolean {
  for (const group of selector.split(",")) {
    const parts = group
      .trim()
      .split(/\s+/)
      .map(parseSimpleSelector);
    if (parts.some((p) => p === null)) continue;
    const chain = parts as SimpleSelector[];
    if (chain.length === 0) continue;
    // Last part must match the element itself; earlier parts match ancestors.
    if (!matchesSimple(el, chain[chain.length - 1])) continue;
    let ancestor: DocNode | ElNode | null = el.parent;
    let ok = true;
    for (let i = chain.length - 2; i >= 0; i--) {
      let found = false;
      while (ancestor && ancestor.kind === "el") {
        if (matchesSimple(ancestor, chain[i])) {
          found = true;
          ancestor = ancestor.parent;
          break;
        }
        ancestor = ancestor.parent;
      }
      if (!found) {
        ok = false;
        break;
      }
    }
    if (ok) return true;
  }
  return false;
}

/** All elements matching a selector, in document order (bs4 `select`). */
export function selectAll(node: Node, selector: string): ElNode[] {
  return findAll(node, (el) => matchesSelector(el, selector));
}

// ---------------------------------------------------------------------------
// Serialization (bs4/lxml-compatible)
// ---------------------------------------------------------------------------

export function serialize(node: Node): string {
  switch (node.kind) {
    case "doc":
      return node.children.map(serialize).join("");
    case "text":
      return escapeText(node.text);
    case "comment":
      return `<!--${node.text}-->`;
    case "doctype":
      return `<!DOCTYPE ${node.text}>`;
    case "pi":
      return node.text;
    case "el": {
      const attrs = [...node.attrs].sort(([a], [b]) =>
        a < b ? -1 : a > b ? 1 : 0,
      );
      const attrStr = attrs
        .map(([name, value]) => {
          if (value.includes('"') && !value.includes("'")) {
            return ` ${name}='${escapeAttrSingleQuoted(value)}'`;
          }
          return ` ${name}="${escapeAttrDoubleQuoted(value)}"`;
        })
        .join("");
      if (VOID_ELEMENTS.has(node.tag)) {
        return `<${node.tag}${attrStr}/>`;
      }
      return `<${node.tag}${attrStr}>${node.children
        .map(serialize)
        .join("")}</${node.tag}>`;
    }
  }
}

// ---------------------------------------------------------------------------
// Parsing
// ---------------------------------------------------------------------------

const BLOCK_START_TAGS = new Set([
  "address", "article", "aside", "blockquote", "div", "dl", "fieldset",
  "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5",
  "h6", "header", "hr", "main", "nav", "ol", "p", "pre", "section",
  "table", "ul",
]);

interface OpenTag {
  tag: string;
  attrs: Array<[string, string]>;
  selfClosing: boolean;
}

function parseTag(inner: string): OpenTag | null {
  // inner is the text between `<` and `>` (without the brackets).
  const m = /^([A-Za-z][^\s/>]*)([\s\S]*)$/.exec(inner.trimStart());
  if (!m) return null;
  const tag = m[1].toLowerCase();
  let rest = m[2];
  let selfClosing = false;
  if (/\/\s*$/.test(rest)) {
    selfClosing = true;
    rest = rest.replace(/\/\s*$/, "");
  }
  const attrs: Array<[string, string]> = [];
  const seen = new Set<string>();
  const attrRe =
    /([^\s=/>]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/g;
  let am: RegExpExecArray | null;
  while ((am = attrRe.exec(rest)) !== null) {
    const name = am[1].toLowerCase();
    if (seen.has(name)) continue;
    seen.add(name);
    const value = am[2] ?? am[3] ?? am[4] ?? "";
    attrs.push([name, decodeEntities(value)]);
  }
  return { tag, attrs, selfClosing };
}

/** Collapse a whitespace-only text run the way libxml2 does. */
function collapseBlank(text: string): string {
  return text.includes("\n") ? "\n" : " ";
}

/**
 * Parse an HTML string into a normalised document:
 * `<html>` with `<head>`/`<body>` children, created only when there is
 * content for them (mirroring lxml).
 */
export function parseHtml(html: string): DocNode {
  const doc: DocNode = { kind: "doc", children: [], parent: null };
  // Stack of open elements; the document is the root.
  const stack: Array<DocNode | ElNode> = [doc];
  const top = (): DocNode | ElNode => stack[stack.length - 1];

  const pushText = (raw: string, decode: boolean, verbatim: boolean): void => {
    if (raw.length === 0) return;
    let text = decode ? decodeEntities(raw) : raw;
    // Blank-node rule: only ASCII whitespace counts (libxml2's
    // IS_BLANK is ASCII-only, so e.g. U+2003 em-spaces survive).
    if (!verbatim && /^[ \t\r\n]*$/.test(text)) {
      text = collapseBlank(text);
    }
    const node: TextNode = { kind: "text", text, parent: null };
    appendChild(top(), node);
  };

  const closeTo = (tag: string): void => {
    // Pop elements until the named open element is closed (inclusive).
    for (let i = stack.length - 1; i >= 1; i--) {
      const node = stack[i];
      if (node.kind === "el" && node.tag === tag) {
        stack.length = i;
        return;
      }
    }
    // No such open element: stray end tag, ignore.
  };

  const closeImpliedFor = (tag: string): void => {
    const cur = top();
    if (cur.kind !== "el") return;
    if (BLOCK_START_TAGS.has(tag) && cur.tag === "p") {
      stack.pop();
      return;
    }
    if (tag === "li" && cur.tag === "li") stack.pop();
    else if (tag === "dt" && (cur.tag === "dt" || cur.tag === "dd")) stack.pop();
    else if (tag === "dd" && (cur.tag === "dt" || cur.tag === "dd")) stack.pop();
    else if (tag === "tr") {
      if (cur.tag === "td" || cur.tag === "th") stack.pop();
      if (top().kind === "el" && (top() as ElNode).tag === "tr") stack.pop();
    } else if ((tag === "td" || tag === "th") && (cur.tag === "td" || cur.tag === "th")) {
      stack.pop();
    } else if (tag === "option" && cur.tag === "option") stack.pop();
    else if (tag === "optgroup") {
      if (cur.tag === "option") stack.pop();
      if (top().kind === "el" && (top() as ElNode).tag === "optgroup") stack.pop();
    } else if (tag === "thead" || tag === "tbody" || tag === "tfoot") {
      if (cur.tag === "thead" || cur.tag === "tbody" || cur.tag === "tfoot") {
        stack.pop();
      }
    } else if (tag === "a" && cur.tag === "a") stack.pop();
    else if (tag === "button" && cur.tag === "button") stack.pop();
    else if ((tag === "h1" || tag === "h2" || tag === "h3" || tag === "h4" || tag === "h5" || tag === "h6") &&
      /^h[1-6]$/.test(cur.tag)) stack.pop();
  };

  const openElement = (parsed: OpenTag): void => {
    const { tag, attrs } = parsed;
    if (tag === "body" || tag === "html" || tag === "head") {
      // A second <body>/<html>/<head> is ignored; its children still parse.
      const existing = stack.some(
        (n) => n.kind === "el" && (n as ElNode).tag === tag,
      );
      if (existing) return;
    }
    closeImpliedFor(tag);
    if (tag === "body" || tag === "html") {
      // Opening <body> closes an open <head>.
      const cur = top();
      if (cur.kind === "el" && cur.tag === "head") stack.pop();
    }
    const el: ElNode = { kind: "el", tag, attrs, children: [], parent: null };
    appendChild(top(), el);
    // Per HTML parsing rules the `/` in `<div/>` is ignored for
    // non-void elements (only void elements are implicitly closed);
    // lxml behaves the same, serializing e.g. `<path/>` as `<path></path>`.
    if (!VOID_ELEMENTS.has(tag)) {
      stack.push(el);
    }
  };

  let i = 0;
  const len = html.length;
  while (i < len) {
    const lt = html.indexOf("<", i);
    if (lt === -1) {
      pushText(html.slice(i), true, isVerbatim(top()));
      break;
    }
    if (lt > i) {
      pushText(html.slice(i, lt), true, isVerbatim(top()));
    }
    // Now at a `<`.
    if (html.startsWith("<!--", lt)) {
      const end = html.indexOf("-->", lt + 4);
      const text = end === -1 ? html.slice(lt + 4) : html.slice(lt + 4, end);
      const node: CommentNode = { kind: "comment", text, parent: null };
      appendChild(top(), node);
      i = end === -1 ? len : end + 3;
      continue;
    }
    if (/^<!doctype/i.test(html.slice(lt, lt + 9))) {
      const end = html.indexOf(">", lt);
      const inner = end === -1 ? html.slice(lt + 9) : html.slice(lt + 9, end);
      const node: DoctypeNode = {
        kind: "doctype",
        text: inner.trim(),
        parent: null,
      };
      appendChild(top(), node);
      i = end === -1 ? len : end + 1;
      continue;
    }
    if (html.startsWith("<![CDATA[", lt)) {
      const end = html.indexOf("]]>", lt + 9);
      const text = end === -1 ? html.slice(lt + 9) : html.slice(lt + 9, end);
      pushText(text, false, true);
      i = end === -1 ? len : end + 3;
      continue;
    }
    if (html.startsWith("<?", lt)) {
      const end = html.indexOf("?>", lt + 2);
      const text = end === -1 ? html.slice(lt) : html.slice(lt, end + 2);
      const node: PiNode = { kind: "pi", text, parent: null };
      appendChild(top(), node);
      i = end === -1 ? len : end + 2;
      continue;
    }
    if (html.startsWith("</", lt)) {
      const end = html.indexOf(">", lt + 2);
      if (end === -1) {
        pushText(html.slice(lt), true, isVerbatim(top()));
        break;
      }
      const name = html
        .slice(lt + 2, end)
        .trim()
        .split(/\s+/)[0]
        .toLowerCase();
      if (name === "br") {
        // `</br>` is treated as `<br>` by browsers.
        openElement({ tag: "br", attrs: [], selfClosing: false });
      } else if (name) {
        closeTo(name);
      }
      i = end + 1;
      continue;
    }
    if (html.startsWith("<plaintext", lt) || html.startsWith("<PLAINTEXT", lt)) {
      const end = html.indexOf(">", lt);
      pushText(html.slice(end === -1 ? len : end + 1), false, true);
      break;
    }
    // Open tag.
    const end = html.indexOf(">", lt + 1);
    if (end === -1) {
      pushText(html.slice(lt), true, isVerbatim(top()));
      break;
    }
    const inner = html.slice(lt + 1, end);
    const parsed = parseTag(inner);
    if (!parsed) {
      // A bare `<` that does not start a tag is literal text.
      pushText("<", false, isVerbatim(top()));
      i = lt + 1;
      continue;
    }
    openElement(parsed);
    i = end + 1;
    // Raw-text / RCDATA element: swallow everything up to its end tag.
    if (RAW_TEXT_ELEMENTS.has(parsed.tag) || RCDATA_ELEMENTS.has(parsed.tag)) {
      const closeRe = new RegExp(`</${parsed.tag}(\\s[^>]*)?>`, "i");
      const rest = html.slice(i);
      const m = closeRe.exec(rest);
      const raw = m ? rest.slice(0, m.index) : rest;
      const decode = RCDATA_ELEMENTS.has(parsed.tag);
      pushText(raw, decode, true);
      if (m) {
        i += m.index + m[0].length;
        // Close the raw-text element itself, if it is still open.
        const cur = top();
        if (cur.kind === "el" && cur.tag === parsed.tag) stack.pop();
      } else {
        i = len;
      }
    }
  }

  return normalizeDocument(doc);

  function isVerbatim(node: DocNode | ElNode): boolean {
    if (node.kind !== "el") return false;
    return (
      node.tag === "pre" ||
      RAW_TEXT_ELEMENTS.has(node.tag) ||
      RCDATA_ELEMENTS.has(node.tag)
    );
  }
}

function normalizeDocument(doc: DocNode): DocNode {
  // Find or create the <html> element.
  let htmlEl = doc.children.find(
    (c): c is ElNode => c.kind === "el" && c.tag === "html",
  ) as ElNode | undefined;

  if (!htmlEl) {
    htmlEl = makeEl("html");
    // Move all element/text children of the document into <html>.
    const kids = doc.children;
    doc.children = [];
    htmlEl.parent = doc;
    doc.children.push(htmlEl);
    for (const kid of kids) {
      if (kid.kind === "doctype" || kid.kind === "comment" || kid.kind === "pi") {
        // Doctype/comments stay at document level, before <html>.
        doc.children.splice(doc.children.length - 1, 0, kid);
        kid.parent = doc;
      } else {
        appendChild(htmlEl, kid);
      }
    }
  } else {
    // Stray top-level elements after <html> belong inside it.
    const strays = doc.children.filter(
      (c) => c !== htmlEl && c.kind === "el",
    );
    for (const stray of strays) {
      detach(stray);
      appendChild(htmlEl, stray);
    }
  }

  // Within <html>: split children into head / body.
  let headEl = htmlEl.children.find(
    (c): c is ElNode => c.kind === "el" && c.tag === "head",
  ) as ElNode | undefined;
  let bodyEl = htmlEl.children.find(
    (c): c is ElNode => c.kind === "el" && c.tag === "body",
  ) as ElNode | undefined;

  const headKids: Node[] = headEl ? [...headEl.children] : [];
  const bodyKids: Node[] = bodyEl ? [...bodyEl.children] : [];

  // Strays before <body> are prepended to the body; strays after it are
  // appended (lxml moves stray content into the body at the matching
  // end). Whitespace-only text directly under <html> stays exactly
  // where it is — lxml keeps it as a child of <html>, not of <body>.
  const bodyPrefix: Node[] = [];
  const bodySuffix: Node[] = [];
  let seenBody = bodyEl !== undefined;
  let passedBody = bodyEl === undefined;
  for (const child of [...htmlEl.children]) {
    if (child === headEl || child === bodyEl) {
      if (child === bodyEl) passedBody = true;
      continue;
    }
    if (child.kind === "text" && /^[ \t\r\n]*$/.test(child.text)) {
      // Stays under <html>; handled in the rebuild below.
      continue;
    }
    detach(child);
    if (
      !seenBody &&
      child.kind === "el" &&
      HEAD_ELEMENTS.has(child.tag)
    ) {
      headKids.push(child);
    } else {
      if (child.kind === "el" || child.kind === "text") {
        seenBody = true;
      }
      (passedBody ? bodySuffix : bodyPrefix).push(child);
    }
  }

  // Rebuild <head> and <body>, created only when there is content.
  let newHead: ElNode | undefined;
  if (headEl || headKids.length > 0) {
    newHead = headEl ?? makeEl("head");
    newHead.children = [];
    for (const kid of headKids) appendChild(newHead, kid);
  }
  let newBody: ElNode | undefined;
  if (bodyEl || bodyPrefix.length > 0 || bodyKids.length > 0 || bodySuffix.length > 0) {
    newBody = bodyEl ?? makeEl("body");
    newBody.children = [];
    for (const kid of [...bodyPrefix, ...bodyKids, ...bodySuffix]) {
      appendChild(newBody, kid);
    }
  }

  // Rebuild <html>'s children in original order: the rebuilt <head> /
  // <body> take the place of the originals (or are inserted first /
  // last when newly created), and whitespace-only text nodes directly
  // under <html> keep their positions.
  const original = htmlEl.children;
  const rebuilt: Node[] = [];
  let headEmitted = false;
  let bodyEmitted = false;
  for (const child of original) {
    if (child === headEl) {
      if (newHead) {
        rebuilt.push(newHead);
        headEmitted = true;
      }
    } else if (child === bodyEl) {
      if (newBody) {
        rebuilt.push(newBody);
        bodyEmitted = true;
      }
    } else if (
      child.kind === "text" &&
      /^[ \t\r\n]*$/.test(child.text)
    ) {
      rebuilt.push(child);
    }
    // Other strays were moved into head/body above and are skipped.
  }
  if (newHead && !headEmitted) rebuilt.unshift(newHead);
  if (newBody && !bodyEmitted) rebuilt.push(newBody);
  htmlEl.children = [];
  for (const kid of rebuilt) appendChild(htmlEl, kid);
  return doc;
}

/** The <body> element of a parsed document, if one exists. */
export function documentBody(doc: DocNode | ElNode): ElNode | null {
  if (doc.kind !== "doc") return null;
  const htmlEl = doc.children.find(
    (c): c is ElNode => c.kind === "el" && c.tag === "html",
  );
  if (!htmlEl) return null;
  return (
    htmlEl.children.find(
      (c): c is ElNode => c.kind === "el" && c.tag === "body",
    ) ?? null
  );
}

/** The <html> element of a parsed document, if one exists. */
export function documentElement(doc: DocNode): ElNode | null {
  return (
    doc.children.find(
      (c): c is ElNode => c.kind === "el" && c.tag === "html",
    ) ?? null
  );
}
