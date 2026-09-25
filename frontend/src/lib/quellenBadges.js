/**
 * Die Etiketten einer Quellen-Karte (#1059, v1.7.120).
 *
 * Gemeldet am 18.09.2026: vier Quellen gehen denselben Weg (ueber die
 * Claude-Erweiterung im eigenen Browser), und jede Karte sagte es anders.
 * Die alte Kette mischte vier verschiedene Dinge:
 *
 *   - TEMPO        (`geschwindigkeit`) — und `langsam` hiess "Browser",
 *                   gelesen wurde das als Wegweiser
 *   - ZUGANGSWEG   (`zugriffsart`)
 *   - EIGENSCHAFT  (`veraltet`, `beta`, Konto)
 *   - ZUSTAND      (Login-Status) — sah neben Eigenschaften aus wie eine
 *
 * XING trug dadurch zweimal "Manuell" (einmal aus `veraltet`, einmal aus
 * dem Tempo). Zwei Regeln loesen das:
 *
 *   1. Der WEG schlaegt das Tempo. Eine Browser-Quelle bekommt EIN
 *      Etikett fuer ihren Weg — kein Tempo, kein "Manuell": beides sagt
 *      dasselbe schlechter.
 *   2. Jeder Text steht hoechstens einmal auf der Karte.
 */

export const WEG_BROWSER = "Im eigenen Browser";

export const WEG_BROWSER_TITEL =
  "Läuft nicht von selbst, sondern über die Claude-Erweiterung in deinem "
  + "Browser — Chrome, Brave, Edge oder Vivaldi. Das kostet mehr Token als "
  + "eine automatische Quelle.";

export function istBrowserQuelle(quelle) {
  return String(quelle?.zugriffsart || "").startsWith("browser");
}

const TEMPO = {
  schnell: { text: "Schnell", tone: "success", symbol: "zap" },
  // "Browser" stand hier — ein Tempo, das sich wie ein Wegweiser las.
  langsam: { text: "Langsam", tone: "amber", symbol: "clock",
             titel: "Dauert länger als die schnellen Quellen" },
  manuell: { text: "Manuell", tone: "neutral" },
};

function loginText(status) {
  if (status === "running") return "Login läuft";
  if (status === "fertig") return "Login: Session bereit";
  if (status === "fehler") return "Login fehlgeschlagen";
  return "Login offen";
}

/**
 * @returns {{text:string,tone:string,art:string,titel?:string,symbol?:string}[]}
 */
export function quellenBadges(quelle, loginStatus = null) {
  const q = quelle || {};
  const liste = [];
  const browser = istBrowserQuelle(q);

  if (q.defekt) {
    liste.push({ text: "Defekt", tone: "danger", art: "status", symbol: "ban" });
  } else {
    liste.push({ text: q.active ? "Aktiv" : "Inaktiv",
                 tone: q.active ? "success" : "neutral", art: "status" });
  }

  if (!q.defekt && browser) {
    liste.push({ text: WEG_BROWSER, tone: "sky", art: "weg", titel: WEG_BROWSER_TITEL });
    if (q.active) {
      liste.push({ text: "Wartet auf dich", tone: "sky", art: "weg",
                   titel: "Eine Browser-Quelle läuft nie im Hintergrund — du startest sie über Claude." });
    }
  } else if (!q.defekt) {
    if (q.veraltet) {
      liste.push({ text: "Nicht automatisiert", tone: "neutral", art: "eigenschaft",
                   titel: "Keine automatische Suche mehr" });
    }
    const tempo = TEMPO[q.geschwindigkeit];
    if (tempo) liste.push({ ...tempo, art: "tempo" });
  }

  if (q.beta) liste.push({ text: "Beta", tone: "amber", art: "eigenschaft" });

  // Konto: noetig oder empfohlen — vorher "Login noetig" gegen "Konto +
  // Chrome", und der Unterschied war aus der Karte nicht zu erkennen.
  if (q.defekt) {
    // Eine defekte Quelle sagt nur das — ein Konto-Hinweis daneben laedt
    // dazu ein, es trotzdem zu versuchen.
  } else if (q.login_erforderlich) {
    liste.push({ text: "Konto nötig", tone: "amber", art: "eigenschaft",
                 titel: q.login_hinweis || "" });
  } else if (q.zugriffsart === "browser_login") {
    liste.push({ text: "Konto empfohlen", tone: "neutral", art: "eigenschaft",
                 titel: q.login_hinweis || "" });
  }

  // Der Login-Status ist ein ZUSTAND, keine Eigenschaft — er steht zuletzt
  // und sagt es im Text.
  if (loginStatus) {
    liste.push({ text: loginText(loginStatus), art: "zustand",
                 tone: loginStatus === "fertig" ? "success" : loginStatus === "fehler" ? "danger" : "amber" });
  }

  const gesehen = new Set();
  return liste.filter((b) => (gesehen.has(b.text) ? false : gesehen.add(b.text)));
}
