/**
 * Ein Firmenname, der zur Firmen-Ansicht führt (#1080, v1.8): Kontakte › Firmen zeigt alles, was PBP zu dieser Firma weiß —
 * Bewerbungen auch als Vermittler und als Endkunde, Stellen, Kontakte, früheren Arbeitgeber, Dokumente, Recherchen.
 *
 * Der Name bleibt lesbarer Text; er wird nur anklickbar. Ohne Namen entsteht kein Knopf, nur der übergebene Ersatztext.
 */
import { useApp } from "@/app-context";

export default function FirmaLink({ name, children, vorher, className = "" }) {
  const { navigateTo } = useApp();
  const text = String(name || "").trim();
  if (!text) return <>{children ?? null}</>;
  return (
    <button
      type="button"
      className={`text-left underline-offset-2 hover:text-sky hover:underline ${className}`}
      data-firma-link={text}
      title={`Öffnet alles, was PBP zu ${text} weiß: Bewerbungen, Stellen, Kontakte, Lebenslauf, Dokumente.`}
      onClick={(event) => {
        event.stopPropagation();
        vorher?.();
        navigateTo("kontakte", { ansicht: "firmen", firmaName: text });
      }}
    >
      {children ?? text}
    </button>
  );
}
