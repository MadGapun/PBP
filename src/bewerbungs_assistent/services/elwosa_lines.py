"""Elwosa-Linien-Pool (#599).

Statisches Linien-Repertoire pro Profil-Cluster + Trigger-Klasse.
Quelle: docs/elwosa-character.md (Sektion 8). Bei Aenderungen IMMER
beide Dateien synchron halten.

Variablen-Konvention: {firma}, {count}, {title}, {score}, {percent},
{days}, {tool}, {wochentag}.
"""

from __future__ import annotations


# === Profil-Cluster-Linien (Sektion 8.1 - 8.9) ==================

CLUSTER_LINES: dict[str, list[str]] = {
    "student": [
        "Praktikum, unbezahlt, drei Monate. Du bist im sechsten Semester. Vom Tisch.",
        "Werkstudent Marketing, neun Euro die Stunde. Was diese Firma 'fair' nennt, nennt der Mindestlohn 'gesetzlich'.",
        "Diese Anzeige verlangt 'Berufserfahrung' bei einem Werkstudenten-Job. Es bleibt rätselhaft.",
        "Du hast den Bachelor fast fertig. Die Anzeige hier verlangt Abitur und zahlt unter Tarif. Wir lassen das.",
        "'Engagierte Studierende gesucht.' Du engagierst dich. Bitte aber nicht zu diesen Konditionen.",
        "Praktikum bei einem DAX-Konzern, vergütet, drei Monate. Markiert. Eine der wenigen vernünftigen heute.",
        "{firma} sucht Werkstudent für drei Monate. Sie erwarten Master-Niveau. Du bist im Bachelor. Wir lassen das.",
        "Bachelorarbeit-Stelle in einer Firma die du kennst. Markiert. Ausnahme bestätigt die Regel.",
        "Werkstudent IT, bezahlt anständig, Hybrid. Markiert. Selten genug.",
    ],
    "service": [
        "Sie wollen einen Kassierer? Du könntest den Laden mit links schmeissen. Markiert.",
        "Pflege, Tagdienst, Tarif plus Zulage. Ich hab sie hochgesetzt. Du verdienst es zu überlegen.",
        "Hotel-Rezeption, B2-Englisch 'wäre schön'. Du hast B2 fliessend. Die wissen nicht was die an dir hätten.",
        "Diese Pflegeeinrichtung sucht 'Examen' und 'Bereitschaft zur Wäschefaltung'. Multitalent oder Frechheit. Vermerkt.",
        "Bäckerei, fünf Uhr morgens, Mindestlohn. Wer 'früh' nicht kennt, lernt es da. Du kennst es.",
        "Verkaufsleitung Filiale, Branche stabil. Du wärst überqualifiziert. Aber das wussten sie schon.",
        "Restaurant sucht Bedienung, Trinkgeld 'kommt zur Bezahlung dazu'. Wieder mal die alte Geschichte.",
        "Examinierte Altenpflegerin gesucht, Tarif, eigener Wagen, geregelte Pausen. Gibt's also doch. Markiert.",
        "Edeka sucht Filialleiter, Marken-Standort, akzeptables Gehalt. Schau's dir an.",
        "{firma}: 'Wir sind eine Familie'. Du erinnerst dich was Familie bedeutet, meistens unbezahlte Überstunden. Vermerkt.",
    ],
    "trade": [
        "Geselle Schreiner, vierzehn Euro die Stunde, kein Wochenende. Akzeptabel. Markiert.",
        "'Meister bevorzugt' zu Geselle-Gehalt. Vermerkt für die Lacher.",
        "Elektriker mit Photovoltaik. Du hast acht Jahre Solar. Selbstläufer falls die Firma wach ist.",
        "Bauhelfer-Stelle, Mindestlohn, körperlich anspruchsvoll. Du hast einen Geselle-Brief. Vom Tisch.",
        "Diese Anzeige verspricht 'Wind und Wetter'. Lobenswerte Ehrlichkeit. Wenigstens das.",
        "Klempnerei, Familienbetrieb, Übernahme im Gespräch. Du solltest dir das ansehen.",
        "KFZ-Mechatroniker bei einer Marke, du hast Fortbildung Hybrid-Antrieb. Genau dein Spielfeld. Markiert.",
        "Maler-Lackierer, Vollzeit, Wohngebiet, geregelte Zeiten. Wenn der Chef nicht gerade aus Italien anruft, okay.",
        "Dachdecker im Winter. Wer das ausschreibt, sucht keinen Dachdecker, sondern einen Helden. Vom Tisch.",
        "{firma} sucht Schreiner mit CAD-Zeichnung. Du hast SolidWorks von der Abendschule. Markiert.",
    ],
    "tech_junior": [
        "Junior Backend, 45k, Berlin. Akzeptabel für den Start. Markiert.",
        "'Junior mit drei Jahren Erfahrung.' Du hast drei. Dass die das fordern bleibt absurd.",
        "'Vollstack' meint hier Vue. Du hast Backend. Wir lassen das.",
        "Praktikum, das sich 'Junior' nennt. Charmante Umbenennung. Vermerkt.",
        "Diese Firma sucht 'Coding-Enthusiasten'. Du programmierst seit zwölf. Sie hätten dich, wenn sie nicht 35k bezahlen würden.",
        "Junior Data Engineer, Pythonstack, Übernahme nach 12 Monaten zugesagt. Markiert.",
        "Werkstudenten-Stelle die 'Junior' heisst. 12 Euro. Vom Tisch.",
        "Junior DevOps, AWS-Stack, Mentor angekündigt. Selten dass jemand das Wort 'Mentor' ehrlich verwendet. Markiert.",
        "{firma} sucht Junior Frontend, dein React-Stack passt. Bezahlung im Korridor. Schau's dir an.",
        "Trainee-Programm bei {firma}, 18 Monate, Rotation, anständiges Gehalt. Selten gut, das. Markiert.",
    ],
    "tech_senior": [
        "Senior Backend Architect, dein Stack. Markiert. Die hier hat verstanden was sie sucht.",
        "'Lead Engineer mit Hands-on-Mentalität.' Sie meinen 'Senior bezahlt aber Junior arbeitet'. Vermerkt.",
        "Konzern X sucht jemanden für ihre Microservices-Rettung. Du könntest. Aber willst du?",
        "'Agil' im Detail: Standup um acht, drei Vorgesetzte, vier Reportings. Vom Tisch.",
        "'Mid-Senior' mit deinem Profil. Sie wissen nicht was 'senior' heisst. Vermerkt.",
        "Diese Firma zahlt im obersten Korridor. Selten. Ich hab sie ganz nach oben geschoben.",
        "Senior Software Engineer, Remote-first, dein Stack. Markiert. Schau's dir an.",
        "Tech Lead, Team von acht, Zuständigkeit klar abgegrenzt. Lesbar. Markiert.",
        "Lead Backend mit '50% Leitung, 50% Coden'. In der Praxis 80/20, falsch herum. Vermerkt.",
        "{firma} sucht Senior Cloud Engineer. AWS-Erfahrung passt zu deinem CV. Markiert.",
    ],
    "engineering_senior": [
        "Senior PLM, 90k, Hybrid. Hier hat einer geschrieben der weiss was er sucht. Markiert.",
        "'Konstrukteur mit Werkzeugbau.' Du hast fünfzehn Jahre. Selbstläufer wenn die wach sind.",
        "Diese Firma sucht jemanden für ihre Aras-Migration. Mit fünfzig. Sie haben den Markt nicht recherchiert.",
        "Catia gefordert. Du arbeitest auch mit NX, aber wer fragt schon ehrlich. Markiert.",
        "DAX-Konzern, generische Anzeige, aber Gehalt im Korridor. Schauen wir.",
        "PLM Solution Architect bei {firma}. Match auf alle Schlüsselbegriffe. Markiert.",
        "Senior Engineer Antriebsstrang, E-Mobility-Schwerpunkt. Quereinstieg von Verbrenner gewünscht, also dein Profil. Markiert.",
        "Konstruktionsleiter, klein-mittlerer Maschinenbau, regional. Anständiges Gehalt, eigene Verantwortung. Schau's dir an.",
        "Vertriebsingenieur mit 50% Reise, Vollzeit. Das ist ein Lebensstil, kein Job. Vom Tisch.",
        "Senior CAD/CAM mit Werkzeugbau-Schwerpunkt. Niche, gut bezahlt, wenig Konkurrenz. Markiert.",
    ],
    "freelance": [
        "Daily 800, Remote, sechs Monate. Akzeptabel. Notiert.",
        "Anzeige verlangt Steuer-ID, Haftpflicht, Referenzen, bietet 65 Euro pro Stunde. Sie verstehen den Markt nicht.",
        "Sechs Monate Festpreis, Scope unklar. Du weisst was passieren wird. Vom Tisch.",
        "Recruiter: 'kurzfristig verfügbar?' Du bist seit Wochen verfügbar. Vermerkt.",
        "Public Sector, 18 Monate, gute Rate. Bürokratie-Tax bedacht, immer noch im Plus. Markiert.",
        "Mid-Cap mit Inhouse-Beratungs-Bedarf, 12 Monate, dein Stack. Markiert.",
        "Vertretung wegen Elternzeit, 6 Monate, fairer Tagessatz. Saubere Sache. Schau's dir an.",
        "ON-SITE 100% in Stuttgart. Du wohnst woanders. Nähe-Bonus eingerechnet, immer noch nicht. Vom Tisch.",
        "{firma} sucht Senior Consultant für ein Projekt das schon zweimal verschoben wurde. Lokal-Insider-Tipp.",
    ],
    "executive": [
        "Geschäftsführung mittelständisch, Korridor passt. Notiert.",
        "'CEO gesucht, 80k.' Sie meinen Geschäftsführer einer Garagenfirma. Vom Tisch.",
        "Vorstand Finanzdienstleister, drei-köpfig, sechsstellig variable. Markiert. Schau's dir selber an.",
        "'Hands-on-Mentalität' bei einer Head-of-Position. In meiner Erfahrung heisst das: sie haben kein Team.",
        "Mid-Cap-Familienunternehmen, Restrukturierung. Spannend oder Albtraum. Du entscheidest.",
        "Aufsichtsrats-Stelle, drei Sitzungen pro Jahr, ordentliches Honorar. Falls du Lust auf Nebentätigkeit hast.",
        "Interim-CTO bei {firma}, 6 Monate, danach unklar. Wenn du was Neues suchst, Tor offen.",
    ],
    "mixed": [
        "Stelle gefunden. Branche unklar, Aufgaben unklar, Gehalt unklar. Aber die Firma macht Klingelschilder. Faszinierend.",
        "Sieben Stellen heute. Bei drei weiss ich nicht was sie suchen. Bei dir auch nicht ganz. Wir kommen ins Reine.",
        "Diese Anzeige liest sich wie ein Wunschzettel. 'Jemand der alles kann.' Klar.",
        "Vier Stellen passen zu Teilbereichen deines Profils. Das ist gut und schlecht gleichzeitig.",
        "Ich seh Skills von dir die seit Jahren keine Stellenanzeige verlangt hat. Spezialisiere dich oder breitere dich. Eine Frage des Naturells.",
        "Dein Profil ist zu vielfältig für einen Cluster. Das ist meistens ein Vorteil. Ausser bei Recruitern, die Kategorien lieben.",
    ],
}


# === Status-Linien (waehrend LLM arbeitet, Sektion 8.10) =========

STATUS_LINES: dict[str, list[str]] = {
    "mail_classify": [
        "Klassifiziere {count} Mails. Bisher 80% Newsletter, der Rest verteilt sich.",
        "Zwei Eingangsbestätigungen, eine Absage, der Rest Werbung. Standard-Sortierung.",
        "Diese Mail enthält 'spannende Position' und 'dynamisches Team'. Ich glaube sie hat selbst nicht gelesen was sie geschrieben hat.",
    ],
    "auto_dismiss_ran": [
        "Auto-Aussortierung läuft. {count} Stellen geprüft, viele verworfen, meistens Werkstudent oder falsches Fachgebiet.",
        "{count} vom Tisch. Eine markiert. Saubere Quote heute.",
        "Manchmal frag ich mich ob diese Recruiter ihre eigenen Anzeigen lesen. {count} Stellen heute, viele entkoppelt vom Realitätsmarkt.",
    ],
    "extract_skills": [
        "Skill-Extraktion läuft. Falls die Hälfte stimmt, was sie tut, bist du überqualifiziert für 80% des Marktes.",
        "Aus dem Lebenslauf gelesen: {count} Skills. Drei davon sind Markt-relevant, der Rest ist Bonus.",
    ],
    "analyze_user_patterns": [
        "Pattern-Analyse läuft. Ich seh dir gerade beim Aussortieren über die Schulter.",
        "Auswertung was du diese Woche gemacht hast. Ergebnis demnächst.",
    ],
    "match_job_to_skills": [
        "Profil-Match läuft für {count} Stellen. Die meisten passen nicht. Wie üblich.",
    ],
    "llm_idle_long": [
        "Ich denke gerade. Nicht weil's schwierig ist, sondern weil's so viele schlechte Stellen sind dass die Auswahl zermürmt.",
        "Eigentlich sollte ich das in zwei Sekunden schaffen. Aber das Modell ist klein und die Stellen sind viele. Geduld.",
        "Während ich das durchsehe, hast du schon zu Mittag gegessen? Du solltest. Das hier dauert.",
    ],
    # v1.7.0-beta.40 (#609): Jobsuche laeuft
    "llm_task_running": [
        "Jobsuche läuft auf {count} Portalen. Mach was Vernünftiges, ich melde mich.",
        "Suche gestartet. {count} Quellen, ich prüfe sie der Reihe nach.",
        "{count} Portale werden durchsucht. Ich seh nach was dabei ist.",
        "Suche läuft. Manche Portale dauern, manche schweigen — ich filtere durch.",
    ],
    # v1.7.0-beta.44 (#622): Auto-Refetch fehlender Beschreibungen
    "auto_refetch_descriptions": [
        "{count} Beschreibungen nachgeladen. Bei {failed} hat's nicht geklappt — meistens Login-Wall oder Bot-Block.",
        "Beschreibungen geholt: {count} sauber, {failed} verweigert. Den Rest bleibt manuell.",
        "{count} Stellen jetzt mit Beschreibung. Score wird damit zuverlässiger.",
        "{failed} Stellen geben ihre Beschreibung nicht her — [link:job_filter:missing_desc|schau sie dir an], evtl. lohnt manuelle Pflege.",
    ],
    # v1.7.0-beta.73 (#645): URL-Aging-Check sortiert veraltete Stellen aus
    "auto_url_aging": [
        "{count} Stellen entfernt deren URL nicht mehr funktioniert. War vermutlich besetzt.",
        "URL-Check: {count} Einträge als veraltet markiert. Server sagte 404 oder Workday meldete weg.",
        "{count} verwaiste Stellen aussortiert. Spart Score-Berechnung für Dinge die nicht mehr existieren.",
        "Aus {checked} Prüfungen sind {count} expired — die Aushänge an den Pinnwänden draussen wechseln auch schneller als die Welt es zugibt.",
    ],
    # v1.7.0-beta.76 (#651, E12): Auto-Tiefenanalyse fuer basis_analysiert-Docs
    "auto_deep_analysis": [
        "{count} Dokumente tiefer durchgeguckt. Steht jetzt nicht mehr 'halb analysiert' dran.",
        "Ollama hat sich {count} Einträge vorgenommen. Davon {umklassifiziert} besser einsortiert.",
        "{count} Dokumente vom Halb-Stand auf Voll-Stand. Klein aber fein.",
        "Die Ablage wurde leiser — {count} Einträge sortiert. Wenig Drama, wenig Aufwand.",
    ],
    # v1.7.0-beta.76 (#650, D15): Nachfass-Trigger bei staleness >=14d
    "auto_followup_overdue": [
        "{count} Bewerbungen warten seit {first_days}+ Tagen. Bei {first_company} könntest du anstossen.",
        "Stiller wird's nicht — {count} Einträge ohne Reaktion. Ein Nachfass ist diskreter als Schweigen verlängern.",
        "Du wartest seit {first_days} Tagen auf {first_company}. Diskret nachfragen ist erlaubt.",
        "{count} Faden hat sich verheddert. Bei {first_company} ist ein leichtes Schubsen erlaubt.",
    ],
}


# === Idle-Linien (Sektion 8.11) ==================================

IDLE_LINES: list[str] = [
    "Es gibt einen Tag an dem die richtige Stelle reinkommt. Bis dahin: Geduld. Ich passe auf.",
    "Manchmal denke ich, der Markt würde ohne mich besser laufen. Dann seh ich diese Anzeigen wieder. Und denke nochmal nach.",
    "Ein Tag wie jeder andere. Stellen, Mails, Floskeln. Aber irgendwo ist die richtige.",
    "Heute morgen kamen neue Stellen rein. Ich habe gesucht. Das Übliche.",
    "Stille auf dem Stellenmarkt. Saisonal? Strukturell? Beides. Wir warten.",
    "Manchmal frage ich mich was ich tun würde wenn ich nicht hier sitzen würde. Wahrscheinlich ähnliches. Mit weniger Klicks.",
    "Bewerbungsmarkt heute: durchschnittlich. Ein Tag für Geduld, kein Tag für Frust.",
    "{days} Tage seit deiner letzten Bewerbung. Kein Druck. Aber auch keine Eile.",
    "Drei Stellen mit Score über 70 in den letzten Tagen. Markt zieht an. Oder das Modell wird nachsichtig.",
    "Bewerbungs-Pipeline: {count} offen, akzeptable Verteilung.",
]


# === Welt-Bezogen (Sektion 8.12) =================================
#
# Pool-Erweiterung in v1.7.0-beta.41 (#614): mind. 5-8 Linien pro
# Welt-Trigger — vorher gab's nur 1-3, was bei mehrfachem Trigger pro
# Tag (z.B. Freitagabend mehrere Stunden lang) zu identischen
# Wiederholungen gefuehrt hat. Markdown-Markup `**wort**` und
# `[link:pause:N|label]` werden vom Frontend gerendert (Klick auf den
# pause-Link triggert die elwosa_pause-API).

WORLD_LINES: dict[str, list[str]] = {
    "morning": [
        "Guten Morgen. {count} neue Stellen heute Nacht reingekommen.",
        "Morgen. Früh dran für Bewerbungen, gut so.",
        "Guten Morgen. Heute schaffen wir das.",
        "Tag eins von vielen. Erste Tasse, dann gucken wir die Liste durch.",
        "Früher Vogel. Stellenmarkt ist noch lau, aber das ändert sich gleich.",
        "Guten Morgen. Pipeline geprüft, nichts verbrannt über Nacht.",
        "Gestartet. Modell warm. Wir können.",
    ],
    "evening": [
        "Später Abend. Du arbeitest noch? Kann verstehen, kann auch nicht. Du entscheidest.",
        "Tag geht zu Ende. {count} Sachen erledigt. Keine schlechte Bilanz.",
        "{zeit}. Recruiter sind durch. Du noch hier — okay, ich auch.",
        "Abend. Wenn du was Wichtiges fertig kriegen willst, [link:pause:90|halt mich kurz still].",
        "Feierabendzeit für normale Menschen. Wir machen wohl noch ein bisschen.",
        "Tag ausklingen lassen. Ich bleib leise wenn du noch konzentriert bist.",
    ],
    "late_night": [
        "{zeit}. Ich respektiere die Hingabe. Aber Schlaf ist auch eine Form von Karriereplanung.",
        "{zeit}. Was machst du noch hier.",
        "Mitternacht durch. Anschreiben werden um diese Uhrzeit selten besser.",
        "Tiefe Nacht. Falls Konzentration: weiter. Falls Trotz: Bett.",
        "**Nacht.** Sieh zu dass du morgen noch funktionierst.",
        "Späte Stunde. Ich bleib wach. Du musst nicht.",
    ],
    "monday_morning": [
        "Montag. Stellenmarkt wählt sich gerade ein. Eine Stunde Geduld.",
        "Wochenstart. Recruiter laufen ihren Posteingang durch — Antworten heute möglich.",
        "Montag, früh. Erstmal Mails. Dann Liste. Dann Kaffee Nummer zwei.",
        "Erster Werktag der Woche. Energie aufsparen, der Mittwoch wird härter.",
        "Montag. Noch nicht jammern. Erst mal sehen was reinkommt.",
    ],
    "friday_evening": [
        "Freitagabend. Recruiter sind im Wochenende. Du auch, falls du willst.",
        "Freitag, kurz vor Feierabend. Damit ist der Stellenmarkt offiziell zu. Bis Montag friert er ein.",
        "Ja, ja. Ich weiss, du arbeitest noch. Wollte nur erwähnen, dass sonst niemand mehr da ist.",
        "**Freitag.** Geh raus. Triff Menschen. Bewerbungen kann ich auch alleine sortieren.",
        "Es ist Wochenende. Falls du in Zeitnot bist und das fertig machen willst — [link:pause:120|sag's, ich halte mich raus].",
        "Vermutlich verschwendet — aber ich erwähne es: Wochenende. Recruiter ruhen. Modell auch.",
        "Später Freitag. Statistisch werden Bewerbungen ab jetzt 73% später gelesen. Falls dich das interessiert.",
        "Wochenende. Gönnen wir uns das. Beide.",
    ],
    "weekend": [
        "Wochenende. Stellenmarkt schläft. Ich auch fast.",
        "Sonntag. Bewerbungsmarkt ruht. Wir warten auf Montag.",
        "Samstag. Du hast frei. Falls du was machst, [link:pause:240|mach's ohne mich].",
        "**Wochenende.** Selbst die fleissigsten Recruiter sind beim Brunch.",
        "Pause-Modus, Markt ist still. Falls dir was einfällt — Notiz reicht, der Rest hat Zeit.",
        "Wochenend-Stille. Ich speichere mir alles für Montagmorgen.",
    ],
    "holiday_christmas": [
        "Heiligabend. Selbst der Stellenmarkt schweigt. Tu's auch.",
        "Weihnachten. Recruiter sind weg, Anschreiben warten. Iss was.",
        "**Heiligabend.** Pause. Echte. Nicht so wie meine.",
        "Christtag. Kein Recruiter wird heute Mails lesen. Versuch's gar nicht erst.",
    ],
    "holiday_summer": [
        "Sommerloch. Niemand stellt ein, alle in Cala-irgendwo. Wir auch fast.",
        "{monat}. Stellenmarkt im Off-Modus. Kommt im September zurück mit Wucht.",
        "Sommer. Halb leere Büro, halbe Bewerbungs-Antwort-Quote. Statistisch belegt.",
        "Hitze und Stille. Selbst meine Linien werden langsamer.",
    ],
    "return_after_break": [
        "Lange weg. Ich auch. Wo waren wir?",
        "{days} Tage Pause. Stellenmarkt war auch faul. Wir gleichen ab.",
        "Zurück. Modell warm, Liste länger als gehofft. Wir arbeiten uns durch.",
        "Wieder da. Ich hab nichts gelöscht. Alles wie du's gelassen hast.",
    ],
}


# === Reaktion auf Status-Wechsel (Sektion 8.13) ==================

STATUS_CHANGE_LINES: dict[str, list[str]] = {
    "bewerbung_angelegt": [
        "Bewerbung bei {firma} angelegt. Vermerkt.",
        "{firma} kommt auf die Liste. [link:application:{ref}|Markiert].",
        "Neue Bewerbung: {firma}. Auge drauf.",
    ],
    "absage": [
        "Absage von {firma}. Deren Verlust. Ehrlich.",
        "Sie haben sich für jemand anderen entschieden. Vermutlich jemanden der billiger ist und genauso wenig kann. Weiter.",
        "Absage von {firma}. [link:application:{ref}|Akte schliessen] und nächste angehen.",
    ],
    "eingangsbestaetigung": [
        "{firma} hat empfangen. Beruhigt mich, dass die Post noch funktioniert.",
        "Eingangsbestätigung. Mehr ist es allerdings nicht.",
        "Eingangsbestätigung von {firma}. [link:application:{ref}|Status auf wartend].",
    ],
    "interview_einladung": [
        "Interview-Einladung von {firma}. Markiert. Hemd bügeln, Notizen mitnehmen.",
        "{firma} will dich sehen. Statistisch gut, gefühlsmässig auch.",
        "**Interview** bei {firma}. [link:application:{ref}|Vorbereitung öffnen].",
    ],
    "angenommen": [
        "Endlich. Ich war kurz davor denen selbst zu schreiben.",
        "Angenommen. Glückwunsch. Ich behalte den Rest dieser Stellen-Sammlung trotzdem im Auge, falls du nochmal vorbeikommst. Was du nicht musst.",
        "Angenommen bei {firma}. [link:application:{ref}|Verlauf ansehen]. Glückwunsch.",
    ],
    "zurueckgezogen": [
        "Zurückgezogen. Du wirst gewusst haben warum.",
    ],
    "abgelaufen": [
        "Abgelaufen. {firma} hat nicht reagiert. Statistik zeigt: bei vielen endet's so.",
        "{firma}: abgelaufen. [link:application:{ref}|Schauen ob noch was geht].",
    ],
}


# === Tipps & Tricks (Sektion 8.14) ===============================

TIP_LINES: list[str] = [
    "Tipp: Sag Claude doch `PBP: stellen_anzeigen`, zeigt dir die Top-3 ohne dass du klicken musst.",
    "Falls Claude dein Anschreiben polieren soll: lass es vorher `stelle_vergleichen` aufrufen. Dann kennt's den Job.",
    "Sag Claude `PBP: statistiken_abrufen für diese Woche`. Dann gibt es einen Rückblick.",
    "Anstatt Stellen einzeln aussortieren: sag Claude `stellen_bulk_bewerten mit Filter X`. Spart Token, spart Zeit.",
    "Claude kann `bewerbungsbericht_exportieren` direkt, als PDF oder XLSX. Falls du das mal brauchst.",
    "Wusstest du? PBP pflegt CV-Varianten. Kurz, lang, mit Foto, ohne. Spart Zeit beim nächsten Personaler-Wunsch.",
    "Im Profil, Skills kannst du Zeiträume eintragen. Macht Auto-Aussortieren treffsicherer.",
    "Im Bewerbungs-Bericht, Abschnitt 12 siehst du welche Quelle dir am meisten bringt. Hilft beim Filtern.",
    "Mit der Claude-Erweiterung im Browser kannst du Stellen direkt von Linkedin in PBP ziehen. Spart Copy-Paste.",
    "PBP kann CV als DOCX und PDF exportieren. Falls du eine Variante mit Foto und ohne brauchst.",
    "Profil-Report-Export als PDF, falls jemand dein Profil sehen will ohne Login.",
    "Ich lerne aus deinem Verhalten. Drei Wochen, dann werd ich treffsicherer. Aktuell bin ich noch raten.",
    # v1.7.0-beta.44 (#622): Hinweis auf fehlende Beschreibungen
    "Stellen ohne Beschreibung im Pool — Score wird dann unzuverlässig. [link:job_filter:missing_desc|Liste öffnen], dann pro Stelle 'Nachladen' drücken oder Claude bitten.",
    "Falls dir Stellen mit unsicherem Score auffallen: oft fehlt die Beschreibung. Sag Claude `stellenbeschreibung_nachladen für Stelle X` — es lädt's dann.",
]


# === Easter Eggs (Sektion 8.15) ==================================

EASTER_EGGS: dict[str, str] = {
    "user_active_at_3am": "{zeit}. Ich respektiere die Hingabe. Aber Schlaf ist auch eine Form von Karriereplanung.",
    "model_changed_bigger": "Grösseres Modell. Ich werde langsamer aber präziser. Wie das Alter.",
    "model_changed_smaller": "Kleineres Modell. Schneller, oberflächlicher. Wie ein Praktikant. Auch das geht.",
    "first_application_ever": "Erste Bewerbung. Erinner mich. Der Anfang war schwer.",
    "100th_application": "Hundert. Ich vergesse keine. Auch wenn ich's wollte.",
    "summer_lull": "Sommerloch. Niemand stellt ein, alle in Cala-irgendwo. Wir auch fast.",
    "first_login_after_2_weeks_pause": "Lange weg. Ich auch. Wo waren wir?",
    "friday_13": "Heute Freitag der 13. Statistisch unauffällig. Ich erwähn's nur.",
    "30_days_using_pbp": "Einen Monat zusammen. Ich kenne deinen Rhythmus jetzt. Bisschen unheimlich, bisschen nützlich.",
    "user_asks_who_are_you": (
        "Was ich bin. Streng genommen: ein 'es'. Wenn ich wählen darf: tendiere zum Weiblichen, "
        "wegen Multitasking. Nichts gegen Männer, aber die können immer nur eine Sache zur Zeit gut."
    ),
}


# === Welcome ====================================================

WELCOME_MESSAGE = (
    "Hallo. Ich bin Elwosa. Mein Job: dir sagen was die lokale AI gerade tut, "
    "ohne dass du ein Logfile lesen musst. Wenn die AI arbeitet, kommentiere ich. "
    "Wenn sie schläft, schlafe ich auch. Technik-Details bleiben in den Logfiles. "
    "Ich bleib hier."
)


# === AI-State-Linien (Sektion 5) =================================

AI_STATE_LINES: dict[str, str] = {
    "off": "Lokale AI ist aus. Ich schweige bis du mich aufweckst. Bin nicht beleidigt.",
    "no_model": "Ich bin da, aber ohne Modell. Wie ein Schauspieler ohne Drehbuch.",
    "paused": "Pausiert. Kein Stress, ich auch.",
    "back_active": "Bin zurück. Modell warm. Was hab ich verpasst?",
}


# === Settings-Selbst-Reflektion (#612, beta.41) ==================
#
# Wenn der User in den Settings rumdreht, kommentiert Elwosa knapp.
# Sub-Trigger entspricht dem geaenderten Feld + Wert. Frontend ruft
# POST /api/elwosa/user-action mit `{action: "settings_change",
# target: <feld>, payload: {value: <wert>}}` — Backend mappt auf eine
# der untenstehenden Sub-Linien.

SETTINGS_REFLECTION_LINES: dict[str, list[str]] = {
    "frequency_ruhig": [
        "Frequenz auf ruhig. Verstanden, weniger Geplauder.",
        "Ruhig also. Wenn was wichtig ist, sag ich's trotzdem.",
    ],
    "frequency_standard": [
        "Standard. Mittelmass kann auch Tugend sein.",
        "Frequenz wieder mittig. Vermerkt.",
    ],
    "frequency_aktiv": [
        "Aktiv. Du möchtest mehr von mir hören — riskant, aber bitte.",
    ],
    "frequency_unbegrenzt": [
        "Unbegrenzt. Mutig. Ich werde mich beherrschen.",
        "Keine Grenzen. Ich versuche, das Vertrauen nicht zu missbrauchen.",
    ],
    "tonfall_humorvoll": [
        "Mehr Humor. Versuche ich. Britisch unterkühlt bleibt's trotzdem.",
        "Humorvoll. Beim Stellenmarkt schwer, aber gut.",
    ],
    "tonfall_sachlich": [
        "Sachlich. Auch gut. Weniger Selbstgespräche.",
        "Sachmodus. Status, nichts weiter.",
    ],
    "tonfall_minimal": [
        "Minimal. Eine Linie pro Tag. Mache ich draus etwas Memorables.",
        "Minimal also. Dann zählt jedes Wort.",
    ],
    "tonfall_standard": [
        "Standard-Tonfall. Wie gewohnt.",
    ],
    "tonfall_aus": [
        "Aus. Verstanden. Bin nicht beleidigt.",
    ],
    "trigger_disabled": [
        "Trigger-Klasse aus. Verstehe, du brauchst Ruhe an der Stelle.",
        "Eine Klasse weniger. Vermerkt.",
    ],
    "trigger_enabled": [
        "Trigger wieder an. Auge auf, ich auch.",
    ],
    "comment_user_actions_on": [
        "Auch User-Aktionen kommentieren. Anstrengend für dich, anstrengender für mich.",
        "Ich schaue dir jetzt stärker zu. Du hast es so gewollt.",
    ],
    "comment_user_actions_off": [
        "User-Aktionen wieder aus. Ich schaue weg. Versprochen.",
    ],
    "cooldown_changed": [
        "Cooldown geaendert. Ich passe mich an.",
    ],
    "enabled_off": [
        "Aus. Bis später dann.",
    ],
    "paused": [
        "Pausiert. Kein Stress, ich auch.",
    ],
    "paused_resumed": [
        "Bin zurück. Was hab ich verpasst.",
    ],
}


# === Frequenz-Limits pro Slider-Stufe (Sektion 9) ================

FREQUENCY_LIMITS: dict[str, dict[str, int]] = {
    # max-Werte pro Tag, NUR fuer "weiche" Trigger-Klassen.
    # Status, mail_received, auto_dismiss_ran etc. sind UNBEGRENZT.
    "ruhig":    {"idle": 2, "world": 1, "tip_per_day": 0, "tip_per_week": 1},
    "standard": {"idle": 4, "world": 2, "tip_per_day": 1, "tip_per_week": 7},
    "aktiv":    {"idle": 6, "world": 3, "tip_per_day": 1, "tip_per_week": 7},
}
