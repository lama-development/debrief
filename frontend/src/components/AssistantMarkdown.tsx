import { ExternalLink } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { Link } from "react-router-dom";
import remarkGfm from "remark-gfm";

// Trova ID come INC-123 e accetta anche i trattini Unicode spesso prodotti dagli LLM.
const INCIDENT_REFERENCE_RE = /\bINC[-\u2010\u2011\u2012\u2013\u2014\u2015\u2212](\d{3,})\b/g;
// Riconosce gli ID già inseriti in un link Markdown per evitare di collegarli una seconda volta.
const EXISTING_INCIDENT_LINK_RE = /(\[INC-\d{3,}\]\([^)]+\))/g;
// Isola blocchi e frammenti di codice, nei quali gli ID devono rimanere testo non cliccabile.
const CODE_FENCE_OR_INLINE_RE = /(```[\s\S]*?```|`[^`\n]+`)/g;

// Collega gli ID senza alterare codice o collegamenti Markdown esistenti.
function linkIncidentReferences(markdown: string) {
  return markdown
    .split(CODE_FENCE_OR_INLINE_RE)
    .map((codeOrText, index) => {
      if (index % 2 === 1) return codeOrText;
      return codeOrText
        .replace(/<br\s*\/?>|<\/br>/gi, "  \n")
        .split(EXISTING_INCIDENT_LINK_RE)
        .map((part, partIndex) => {
          if (partIndex % 2 === 1) return part;
          return part.replace(
            INCIDENT_REFERENCE_RE,
            (_match, digits: string) => `[INC-${digits}](/incidents/INC-${digits})`,
          );
        })
        .join("");
    })
    .join("");
}

export default function AssistantMarkdown({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        a: ({ href, children }) => {
          if (href !== undefined && /^\/incidents\/INC-\d{3,}$/.test(href)) {
            return (
              <Link
                to={href}
                className="inline-flex items-center gap-1 rounded-sm font-medium underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                {children}
                <ExternalLink className="h-3 w-3" aria-hidden="true" />
              </Link>
            );
          }

          return (
            <a href={href} target="_blank" rel="noreferrer">
              {children}
            </a>
          );
        },
      }}
    >
      {linkIncidentReferences(content)}
    </ReactMarkdown>
  );
}
