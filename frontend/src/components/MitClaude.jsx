/**
 * MitClaude — G72 (#1087 E4).
 *
 * Jeder Knopf, der eine Anleitung fuer Claude kopiert, traegt dasselbe
 * Symbol und endet auf "mit Claude". Vorher hiessen dieselben Knoepfe
 * "Prompt kopieren", "Anleitung kopieren", "Kopieren", "Sag Claude",
 * "Profil-Prompt kopieren" oder nur "Lebenslauf" — ob ein Klick etwas
 * im Dashboard tut oder etwas fuer Claude bereitlegt, war nicht zu sehen.
 *
 * Kopiert wird immer ueber `copyPrompt` (App-Kontext); ein Guard-Test
 * verbietet direkte Zwischenablage-Aufrufe fuer Anleitungen.
 */
import { MessageSquareShare } from "lucide-react";

export const ClaudeSymbol = MessageSquareShare;

export const MIT_CLAUDE = "mit Claude";

export default function MitClaude({ children, size = 15 }) {
  return (
    <>
      <ClaudeSymbol size={size} aria-hidden="true" className="shrink-0" data-claude-symbol />
      {children ? <>{children} {MIT_CLAUDE}</> : "Mit Claude"}
    </>
  );
}
