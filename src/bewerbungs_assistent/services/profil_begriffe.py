"""Was steht im Profil? Eine Frage, eine Funktion (#1390, #1385).

`skill_gap_analyse` meldete "feinplanung" und "av" als fehlend, obwohl das
Profil ein Projekt "SAP-PP-Feinplanung eingeführt" und die Station
"Arbeitsvorbereitung" trug. Drei Ursachen, alle hier behoben:

1. Das Profil-Vokabular bestand nur aus den Namen der Kompetenzen und den
   Technologien der Stationen. Titel, Aufgaben, Erfolge und Projekte
   gingen nicht ein. Jetzt: `profil_text` (alles, was der Mensch
   aufgeschrieben hat).
2. Abgeglichen wurde in einer Richtung. Jetzt: `ist_belegt` prüft ganze
   Wörter, Wortstämme, Abkürzungen und die Gegenrichtung (ein Profilbegriff
   steckt in einem mehrteiligen Begriff der Anzeige).
3. Abkürzungen waren unbekannt. Jetzt: `ABKUERZUNGEN`, in beide
   Richtungen. Begriffe unter drei Buchstaben zählen nur, wenn sie hier
   stehen (Lehre 3: Wortgrenzen und Schreibweisen).

Abgrenzung: `stellen_skills` zieht Begriffe aus ANZEIGEN; dieses Modul sagt,
ob ein Begriff im PROFIL belegt ist. `lebenslauf_bewerten` (#1385) nutzt
dieselbe Prüfung für die fehlenden Begriffe - keine zweite Begriffslogik.

Messung zu #1390 ("aus derselben Quelle wie fit_analyse"): `fit_analyse`
selbst kennt nur die Namen der Kompetenzen (`_profile_skills`); es gab keine
gemeinsame Quelle, die man hätte wiederverwenden können. Sie entsteht hier.
"""
from __future__ import annotations

import re

#: Abkürzung -> ausgeschriebene Formen (alles klein, ohne Umlaute).
ABKUERZUNGEN: dict[str, tuple[str, ...]] = {
    "av": ("arbeitsvorbereitung",),
    "avor": ("arbeitsvorbereitung",),
    "qs": ("qualitaetssicherung", "qualitaetskontrolle"),
    "qm": ("qualitaetsmanagement",),
    "pps": ("produktionsplanung und steuerung", "produktionsplanung",
            "produktionssteuerung"),
    "kvp": ("kontinuierlicher verbesserungsprozess",
            "kontinuierliche verbesserung"),
    "scm": ("supply chain management",),
    "ek": ("einkauf",),
    "hr": ("personalwesen", "human resources"),
    "mes": ("manufacturing execution system",),
    "erp": ("enterprise resource planning",),
}

#: Wörter, die als Begriff zu kurz sind, aber stehen dürfen.
KURZ_ERLAUBT = frozenset(ABKUERZUNGEN)


def normieren(text: str) -> str:
    """Klein, Umlaute als ae/oe/ue/ss: "Qualitätssicherung" = "qualitaetssicherung"."""
    t = (text or "").lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        t = t.replace(a, b)
    return t


def _woerter(norm: str) -> list[str]:
    return re.findall(r"[a-z0-9+#]+", norm)


def _stamm(wort: str) -> str:
    """Schlüssel zum Vergleichen von Beugungsformen (kein Anzeigewort)."""
    from .stellen_skills import grundform
    return grundform(wort)


def _folge_in(woerter: list[str], folge: list[str]) -> bool:
    n = len(folge)
    if not n or n > len(woerter):
        return False
    return any(woerter[i:i + n] == folge for i in range(len(woerter) - n + 1))


def profil_text(profil: dict | None) -> str:
    """Alles, was der Mensch über sich aufgeschrieben hat, als ein Text."""
    teile: list[str] = []
    p = profil or {}
    for s in p.get("skills") or []:
        teile.append(str((s or {}).get("name") or ""))
    for pos in p.get("positions") or []:
        for feld in ("title", "tasks", "achievements", "technologies",
                     "description", "industry"):
            teile.append(str((pos or {}).get(feld) or ""))
        for proj in (pos or {}).get("projects") or []:
            for feld in ("name", "description", "role", "situation", "task",
                         "action", "result", "technologies"):
                teile.append(str((proj or {}).get(feld) or ""))
    for e in p.get("education") or []:
        for feld in ("degree", "field_of_study", "field"):
            teile.append(str((e or {}).get(feld) or ""))
    return "\n".join(t for t in teile if t.strip())


class Profilbegriffe:
    """Der Profiltext, einmal aufbereitet, für viele Abfragen."""

    def __init__(self, profil: dict | None):
        self.woerter = _woerter(normieren(profil_text(profil)))
        self.staemme = {_stamm(w) for w in self.woerter if len(w) > 2}
        # Namen der Kompetenzen und Stationstitel als Phrasen (Gegenrichtung)
        phrasen: list[list[str]] = []
        for s in (profil or {}).get("skills") or []:
            w = _woerter(normieren(str((s or {}).get("name") or "")))
            if w and len(" ".join(w)) >= 3:
                phrasen.append(w)
        for pos in (profil or {}).get("positions") or []:
            w = _woerter(normieren(str((pos or {}).get("title") or "")))
            if w and len(" ".join(w)) >= 4:
                phrasen.append(w)
        self.phrasen = phrasen

    @staticmethod
    def _norm(begriff: str) -> str:
        return " ".join(_woerter(normieren(begriff)))

    def formen(self, begriff: str) -> set[str]:
        """Der Begriff samt Abkürzung und Ausschreibung (beide Richtungen)."""
        b = self._norm(begriff)
        erg = {b}
        for kurz, lang in ABKUERZUNGEN.items():
            if b == kurz:
                erg.update(lang)
            elif b in lang:
                erg.add(kurz)
        return {f for f in erg if f}

    def ist_brauchbar(self, begriff: str) -> bool:
        """Zu kurze Begriffe zählen nicht, ausser sie stehen auf der Liste."""
        b = self._norm(begriff)
        return len(b) >= 3 or b in KURZ_ERLAUBT

    def ist_belegt(self, begriff: str) -> bool:
        b = self._norm(begriff)
        if not b or not self.ist_brauchbar(begriff):
            return False
        for f in self.formen(begriff):
            if _folge_in(self.woerter, f.split()):
                return True
            if " " not in f and len(f) > 2 and _stamm(f) in self.staemme:
                return True
        # Gegenrichtung: ein Profilbegriff steckt im mehrteiligen Begriff
        if " " in b:
            bw = b.split()
            for ph in self.phrasen:
                if _folge_in(bw, ph):
                    return True
        return False
