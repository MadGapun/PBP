/**
 * "Zuerst dein Profil" — G63 (#1087 A6), G83 (#1170 U5 bis U7).
 *
 * Ohne Profil zeigte der Stellen-Tab "Starte eine Jobsuche oder öffne das
 * Suchprofil", der Bewerbungen-Tab "Auf Kurs — Bewerbungsboard ist gerade
 * sauber" und "Bewerbung anlegen". Ohne Profil ist der nächste Schritt
 * aber das Profil, und "Auf Kurs" über einem leeren System beruhigt zu
 * Unrecht. Alle Leerzustände ohne Profil nennen deshalb denselben Schritt.
 *
 * U6 (#1170): die Karte trug keinen Knopf ("Der Einstieg auf dem Dashboard
 * führt dich hin") und stand mit Kennzahlen aus Nullen, Filtern und einer
 * Quellenkarte auf derselben Seite. Jetzt ist sie der GANZE Inhalt der Seite
 * und hat einen Knopf, der dort beginnt, wo der Einstieg beginnt: beim
 * Lebenslauf. Derselbe Knopf steht auf dem Dashboard (U7: ein Weg).
 */
import { Upload } from "lucide-react";

import { Button, EmptyState } from "@/components/ui";
import { useApp } from "@/app-context";
import { STARTSATZ } from "@/lib/startsatz";

export const ZUERST_PROFIL_STATUS = {
  badge: "Zuerst dein Profil",
  tone: "amber",
  title: "Zuerst dein Profil",
  description: "Ohne Profil weiß PBP nicht, wonach es suchen und was es bewerten soll. Am schnellsten geht es mit deinem Lebenslauf.",
};

export default function ZuerstProfil({ bereich }) {
  const { openCreateProfileModal } = useApp();
  return (
    <div data-zuerst-profil={bereich || ""}>
      <EmptyState
        title="Zuerst dein Profil"
        description={`${bereich ? `${bereich} kommen danach. ` : ""}Ohne Profil weiß PBP nicht, wonach es suchen und was es bewerten soll. Am schnellsten geht es mit deinem Lebenslauf — daraus entsteht dein Profil.`}
        action={
          <div className="grid justify-items-center gap-2">
            <Button onClick={openCreateProfileModal}>
              <Upload size={15} />
              Lebenslauf hochladen
            </Button>
            <p className="max-w-sm text-xs text-muted">
              Ohne Lebenslauf geht es auch: in Claude „{STARTSATZ}“ sagen.
            </p>
          </div>
        }
      />
    </div>
  );
}
