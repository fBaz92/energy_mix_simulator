import { useParams, Link } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import remarkGfm from "remark-gfm";
import rehypeKatex from "rehype-katex";
import { getDoc } from "@/wiki/loader";

export function WikiPage() {
  const { slug } = useParams<{ slug: string }>();
  const doc = slug ? getDoc(slug) : undefined;

  if (!doc) {
    return (
      <div className="px-6 py-10 max-w-3xl">
        <h2 className="text-xl font-semibold mb-2">Documento non trovato</h2>
        <p className="text-sm text-muted-foreground">
          Nessun documento corrisponde a <code>{slug}</code>.
        </p>
        <Link
          to="/wiki"
          className="inline-block mt-4 text-sm text-primary hover:underline"
        >
          ← Torna all'indice
        </Link>
      </div>
    );
  }

  return (
    <article className="px-6 py-8 max-w-3xl prose prose-sm dark:prose-invert">
      <ReactMarkdown
        remarkPlugins={[remarkMath, remarkGfm]}
        rehypePlugins={[rehypeKatex]}
      >
        {doc.body}
      </ReactMarkdown>
    </article>
  );
}
