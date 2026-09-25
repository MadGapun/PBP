/**
 * "Zuerst dein Profil" — G63 (#1087 A6).
 *
 * Ohne Profil zeigte der Stellen-Tab "Starte eine Jobsuche oder öffne das
 * Suchprofil", der Bewerbungen-Tab "Auf Kurs — Bewerbungsboard ist gerade
 * sauber" und "Bewerbung anlegen". Ohne Profil ist der nächste Schritt
 * aber das Profil, und "Auf Kurs" über einem leeren System beruhigt zu
 * Unrecht. Alle Leerzustände ohne Profil nennen deshalb denselben Schritt.
 */
import { UserRound } from "lucide-react";

import { Button, EmptyState } from "@/components/ui";
import { useApp } from "@/app-context";

export const ZUERST_PROFIL_STATUS = {
  badge: "Zuerst dein Profil",
  tone: "amber",
  title: "Zuerst dein Profil",
  description: "Ohne Profil weiß PBP nicht, wonach es suchen und was es bewerten soll. Der Einstieg auf dem Dashboard führt dich hin.",
};

export default function ZuerstProfil({ bereich }) {
  const { navigateTo } = useApp();
  return (
    <div data-zuerst-profil={bereich || ""}>
    <EmptyState
      title="Zuerst dein Profil"
      description={`${bereich ? `${bereich} kommen danach. ` : ""}Ohne Profil weiß PBP nicht, wonach es suchen und was es bewerten soll.`}
      action={
        <Button onClick={() => navigateTo("dashboard")}>
          <UserRound size={15} />
          Zum Einstieg
        </Button>
      }
    />
    </div>
  );
}
