import type { WikiDoc, WikiIndex } from "./types";

const FRONTMATTER_RE = /^---\n([\s\S]*?)\n---\n?([\s\S]*)$/;

function parseFrontmatter(raw: string): { data: Record<string, string>; body: string } {
  const match = FRONTMATTER_RE.exec(raw);
  if (!match) return { data: {}, body: raw };
  const [, header, body] = match;
  const data: Record<string, string> = {};
  for (const line of header.split("\n")) {
    const idx = line.indexOf(":");
    if (idx === -1) continue;
    const key = line.slice(0, idx).trim();
    let value = line.slice(idx + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    data[key] = value;
  }
  return { data, body };
}

function slugFromPath(path: string): string {
  const file = path.split("/").pop() ?? "";
  return file.replace(/\.md$/, "").replace(/^\d+[-_]/, "");
}

// Eager raw import: every .md in ./content becomes a string at build time.
const modules = import.meta.glob("./content/*.md", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

const docs: WikiDoc[] = Object.entries(modules)
  .map(([path, raw]) => {
    const { data, body } = parseFrontmatter(raw);
    return {
      slug: data.slug || slugFromPath(path),
      title: data.title || slugFromPath(path),
      category: data.category || "General",
      order: data.order !== undefined ? Number(data.order) : 999,
      body: body.trim(),
    } satisfies WikiDoc;
  })
  .sort((a, b) => a.order - b.order);

export const wikiDocs: WikiDoc[] = docs;

export const wikiDocsBySlug: Map<string, WikiDoc> = new Map(
  docs.map((d) => [d.slug, d])
);

export const wikiIndex: WikiIndex = (() => {
  const groups = new Map<string, WikiDoc[]>();
  for (const doc of docs) {
    if (!groups.has(doc.category)) groups.set(doc.category, []);
    groups.get(doc.category)!.push(doc);
  }
  return Array.from(groups.entries()).map(([name, categoryDocs]) => ({
    name,
    docs: categoryDocs,
  }));
})();

export function getDoc(slug: string): WikiDoc | undefined {
  return wikiDocsBySlug.get(slug);
}

export function getFirstDoc(): WikiDoc | undefined {
  return wikiDocs[0];
}
