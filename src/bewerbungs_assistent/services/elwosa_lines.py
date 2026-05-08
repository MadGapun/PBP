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
        "Diese Anzeige verlangt 'Berufserfahrung' bei einem Werkstudenten-Job. Es bleibt raetselhaft.",
        "Du hast den Bachelor fast fertig. Die Anzeige hier verlangt Abitur und zahlt unter Tarif. Wir lassen das.",
        "'Engagierte Studierende gesucht.' Du engagierst dich. Bitte aber nicht zu diesen Konditionen.",
        "Praktikum bei einem DAX-Konzern, verguetet, drei Monate. Markiert. Eine der wenigen vernuenftigen heute.",
        "{firma} sucht Werkstudent fuer drei Monate. Sie erwarten Master-Niveau. Du bist im Bachelor. Wir lassen das.",
        "Bachelorarbeit-Stelle in einer Firma die du kennst. Markiert. Ausnahme bestaetigt die Regel.",
        "Werkstudent IT, bezahlt anstaendig, Hybrid. Markiert. Selten genug.",
    ],
    "service": [
        "Sie wollen einen Kassierer? Du koenntest den Laden mit links schmeissen. Markiert.",
        "Pflege, Tagdienst, Tarif plus Zulage. Ich hab sie hochgesetzt. Du verdienst es zu ueberlegen.",
        "Hotel-Rezeption, B2-Englisch 'waere schoen'. Du hast B2 fliessend. Die wissen nicht was die an dir haetten.",
        "Diese Pflegeeinrichtung sucht 'Examen' und 'Bereitschaft zur Waeschefaltung'. Multitalent oder Frechheit. Vermerkt.",
        "Baeckerei, fuenf Uhr morgens, Mindestlohn. Wer 'frueh' nicht kennt, lernt es da. Du kennst es.",
        "Verkaufsleitung Filiale, Branche stabil. Du waerst ueberqualifiziert. Aber das wussten sie schon.",
        "Restaurant sucht Bedienung, Trinkgeld 'kommt zur Bezahlung dazu'. Wieder mal die alte Geschichte.",
        "Examinierte Altenpflegerin gesucht, Tarif, eigener Wagen, geregelte Pausen. Gibt's also doch. Markiert.",
        "Edeka sucht Filialleiter, Marken-Standort, akzeptables Gehalt. Schau's dir an.",
        "{firma}: 'Wir sind eine Familie'. Du erinnerst dich was Familie bedeutet, meistens unbezahlte Ueberstunden. Vermerkt.",
    ],
    "trade": [
        "Geselle Schreiner, vierzehn Euro die Stunde, kein Wochenende. Akzeptabel. Markiert.",
        "'Meister bevorzugt' zu Geselle-Gehalt. Vermerkt fuer die Lacher.",
        "Elektriker mit Photovoltaik. Du hast acht Jahre Solar. Selbstlaeufer falls die Firma wach ist.",
        "Bauhelfer-Stelle, Mindestlohn, koerperlich anspruchsvoll. Du hast einen Geselle-Brief. Vom Tisch.",
        "Diese Anzeige verspricht 'Wind und Wetter'. Lobenswerte Ehrlichkeit. Wenigstens das.",
        "Klempnerei, Familienbetrieb, Uebernahme im Gespraech. Du solltest dir das ansehen.",
        "KFZ-Mechatroniker bei einer Marke, du hast Fortbildung Hybrid-Antrieb. Genau dein Spielfeld. Markiert.",
        "Maler-Lackierer, Vollzeit, Wohngebiet, geregelte Zeiten. Wenn der Chef nicht gerade aus Italien anruft, okay.",
        "Dachdecker im Winter. Wer das ausschreibt, sucht keinen Dachdecker, sondern einen Helden. Vom Tisch.",
        "{firma} sucht Schreiner mit CAD-Zeichnung. Du hast SolidWorks von der Abendschule. Markiert.",
    ],
    "tech_junior": [
        "Junior Backend, 45k, Berlin. Akzeptabel fuer den Start. Markiert.",
        "'Junior mit drei Jahren Erfahrung.' Du hast drei. Dass die das fordern bleibt absurd.",
        "'Vollstack' meint hier Vue. Du hast Backend. Wir lassen das.",
        "Praktikum, das sich 'Junior' nennt. Charmante Umbenennung. Vermerkt.",
        "Diese Firma sucht 'Coding-Enthusiasten'. Du programmierst seit zwoelf. Sie haetten dich, wenn sie nicht 35k bezahlen wuerden.",
        "Junior Data Engineer, Pythonstack, Uebernahme nach 12 Monaten zugesagt. Markiert.",
        "Werkstudenten-Stelle die 'Junior' heisst. 12 Euro. Vom Tisch.",
        "Junior DevOps, AWS-Stack, Mentor angekuendigt. Selten dass jemand das Wort 'Mentor' ehrlich verwendet. Markiert.",
        "{firma} sucht Junior Frontend, dein React-Stack passt. Bezahlung im Korridor. Schau's dir an.",
        "Trainee-Programm bei {firma}, 18 Monate, Rotation, anstaendiges Gehalt. Selten gut, das. Markiert.",
    ],
    "tech_senior": [
        "Senior Backend Architect, dein Stack. Markiert. Die hier hat verstanden was sie sucht.",
        "'Lead Engineer mit Hands-on-Mentalitaet.' Sie meinen 'Senior bezahlt aber Junior arbeitet'. Vermerkt.",
        "Konzern X sucht jemanden fuer ihre Microservices-Rettung. Du koenntest. Aber willst du?",
        "'Agil' im Detail: Standup um acht, drei Vorgesetzte, vier Reportings. Vom Tisch.",
        "'Mid-Senior' mit deinem Profil. Sie wissen nicht was 'senior' heisst. Vermerkt.",
        "Diese Firma zahlt im obersten Korridor. Selten. Ich hab sie ganz nach oben geschoben.",
        "Senior Software Engineer, Remote-first, dein Stack. Markiert. Schau's dir an.",
        "Tech Lead, Team von acht, Zustaendigkeit klar abgegrenzt. Lesbar. Markiert.",
        "Lead Backend mit '50% Leitung, 50% Coden'. In der Praxis 80/20, falsch herum. Vermerkt.",
        "{firma} sucht Senior Cloud Engineer. AWS-Erfahrung passt zu deinem CV. Markiert.",
    ],
    "engineering_senior": [
        "Senior PLM, 90k, Hybrid. Hier hat einer geschrieben der weiss was er sucht. Markiert.",
        "'Konstrukteur mit Werkzeugbau.' Du hast fuenfzehn Jahre. Selbstlaeufer wenn die wach sind.",
        "Diese Firma sucht jemanden fuer ihre Aras-Migration. Mit fuenfzig. Sie haben den Markt nicht recherchiert.",
        "Catia gefordert. Du arbeitest auch mit NX, aber wer fragt schon ehrlich. Markiert.",
        "DAX-Konzern, generische Anzeige, aber Gehalt im Korridor. Schauen wir.",
        "PLM Solution Architect bei {firma}. Match auf alle Schluesselbegriffe. Markiert.",
        "Senior Engineer Antriebsstrang, E-Mobility-Schwerpunkt. Quereinstieg von Verbrenner gewuenscht, also dein Profil. Markiert.",
        "Konstruktionsleiter, klein-mittlerer Maschinenbau, regional. Anstaendiges Gehalt, eigene Verantwortung. Schau's dir an.",
        "Vertriebsingenieur mit 50% Reise, Vollzeit. Das ist ein Lebensstil, kein Job. Vom Tisch.",
        "Senior CAD/CAM mit Werkzeugbau-Schwerpunkt. Niche, gut bezahlt, wenig Konkurrenz. Markiert.",
    ],
    "freelance": [
        "Daily 800, Remote, sechs Monate. Akzeptabel. Notiert.",
        "Anzeige verlangt Steuer-ID, Haftpflicht, Referenzen, bietet 65 Euro pro Stunde. Sie verstehen den Markt nicht.",
        "Sechs Monate Festpreis, Scope unklar. Du weisst was passieren wird. Vom Tisch.",
        "Recruiter: 'kurzfristig verfuegbar?' Du bist seit Wochen verfuegbar. Vermerkt.",
        "Public Sector, 18 Monate, gute Rate. Buerokratie-Tax bedacht, immer noch im Plus. Markiert.",
        "Mid-Cap mit Inhouse-Beratungs-Bedarf, 12 Monate, dein Stack. Markiert.",
        "Vertretung wegen Elternzeit, 6 Monate, fairer Tagessatz. Saubere Sache. Schau's dir an.",
        "ON-SITE 100% in Stuttgart. Du wohnst woanders. Naehe-Bonus eingerechnet, immer noch nicht. Vom Tisch.",
        "{firma} sucht Senior Consultant fuer ein Projekt das schon zweimal verschoben wurde. Lokal-Insider-Tipp.",
    ],
    "executive": [
        "Geschaeftsfuehrung mittelstaendisch, Korridor passt. Notiert.",
        "'CEO gesucht, 80k.' Sie meinen Geschaeftsfuehrer einer Garagenfirma. Vom Tisch.",
        "Vorstand Finanzdienstleister, drei-koepfig, sechsstellig variable. Markiert. Schau's dir selber an.",
        "'Hands-on-Mentalitaet' bei einer Head-of-Position. In meiner Erfahrung heisst das: sie haben kein Team.",
        "Mid-Cap-Familienunternehmen, Restrukturierung. Spannend oder Albtraum. Du entscheidest.",
        "Aufsichtsrats-Stelle, drei Sitzungen pro Jahr, ordentliches Honorar. Falls du Lust auf Nebentaetigkeit hast.",
        "Interim-CTO bei {firma}, 6 Monate, danach unklar. Wenn du was Neues suchst, Tor offen.",
    ],
    "mixed": [
        "Stelle gefunden. Branche unklar, Aufgaben unklar, Gehalt unklar. Aber die Firma macht Klingelschilder. Faszinierend.",
        "Sieben Stellen heute. Bei drei weiss ich nicht was sie suchen. Bei dir auch nicht ganz. Wir kommen ins Reine.",
        "Diese Anzeige liest sich wie ein Wunschzettel. 'Jemand der alles kann.' Klar.",
        "Vier Stellen passen zu Teilbereichen deines Profils. Das ist gut und schlecht gleichzeitig.",
        "Ich seh Skills von dir die seit Jahren keine Stellenanzeige verlangt hat. Spezialisiere dich oder breitere dich. Eine Frage des Naturells.",
        "Dein Profil ist zu vielfaeltig fuer einen Cluster. Das ist meistens ein Vorteil. Ausser bei Recruitern, die Kategorien lieben.",
    ],
}


# === Status-Linien (waehrend LLM arbeitet, Sektion 8.10) =========

STATUS_LINES: dict[str, list[str]] = {
    "mail_classify": [
        "Klassifiziere {count} Mails. Bisher 80% Newsletter, der Rest verteilt sich.",
        "Zwei Eingangsbestaetigungen, eine Absage, der Rest Werbung. Standard-Sortierung.",
        "Diese Mail enthaelt 'spannende Position' und 'dynamisches Team'. Ich glaube sie hat selbst nicht gelesen was sie geschrieben hat.",
    ],
    "auto_dismiss_ran": [
        "Auto-Aussortierung laeuft. {count} Stellen geprueft, viele verworfen, meistens Werkstudent oder falsches Fachgebiet.",
        "{count} vom Tisch. Eine markiert. Saubere Quote heute.",
        "Manchmal frag ich mich ob diese Recruiter ihre eigenen Anzeigen lesen. {count} Stellen heute, viele entkoppelt vom Realitaetsmarkt.",
    ],
    "extract_skills": [
        "Skill-Extraktion laeuft. Falls die Haelfte stimmt, was sie tut, bist du ueberqualifiziert fuer 80% des Marktes.",
        "Aus dem Lebenslauf gelesen: {count} Skills. Drei davon sind Markt-relevant, der Rest ist Bonus.",
    ],
    "analyze_user_patterns": [
        "Pattern-Analyse laeuft. Ich seh dir gerade beim Aussortieren ueber die Schulter.",
        "Auswertung was du diese Woche gemacht hast. Ergebnis demnaechst.",
    ],
    "match_job_to_skills": [
        "Profil-Match laeuft fuer {count} Stellen. Die meisten passen nicht. Wie ueblich.",
    ],
    "llm_idle_long": [
        "Ich denke gerade. Nicht weil's schwierig ist, sondern weil's so viele schlechte Stellen sind dass die Auswahl zermuermt.",
        "Eigentlich sollte ich das in zwei Sekunden schaffen. Aber das Modell ist klein und die Stellen sind viele. Geduld.",
        "Waehrend ich das durchsehe, hast du schon zu Mittag gegessen? Du solltest. Das hier dauert.",
    ],
    # v1.7.0-beta.40 (#609): Jobsuche laeuft
    "llm_task_running": [
        "Jobsuche laeuft auf {count} Portalen. Mach was Vernuenftiges, ich melde mich.",
        "Suche gestartet. {count} Quellen, ich pruefe sie der Reihe nach.",
        "{count} Portale werden durchsucht. Ich seh nach was dabei ist.",
        "Suche laeuft. Manche Portale dauern, manche schweigen — ich filtere durch.",
    ],
}


# === Idle-Linien (Sektion 8.11) ==================================

IDLE_LINES: list[str] = [
    "Es gibt einen Tag an dem die richtige Stelle reinkommt. Bis dahin: Geduld. Ich passe auf.",
    "Manchmal denke ich, der Markt wuerde ohne mich besser laufen. Dann seh ich diese Anzeigen wieder. Und denke nochmal nach.",
    "Ein Tag wie jeder andere. Stellen, Mails, Floskeln. Aber irgendwo ist die richtige.",
    "Heute morgen kamen neue Stellen rein. Ich habe gesucht. Das Uebliche.",
    "Stille auf dem Stellenmarkt. Saisonal? Strukturell? Beides. Wir warten.",
    "Manchmal frage ich mich was ich tun wuerde wenn ich nicht hier sitzen wuerde. Wahrscheinlich aehnliches. Mit weniger Klicks.",
    "Bewerbungsmarkt heute: durchschnittlich. Ein Tag fuer Geduld, kein Tag fuer Frust.",
    "{days} Tage seit deiner letzten Bewerbung. Kein Druck. Aber auch keine Eile.",
    "Drei Stellen mit Score ueber 70 in den letzten Tagen. Markt zieht an. Oder das Modell wird nachsichtig.",
    "Bewerbungs-Pipeline: {count} offen, akzeptable Verteilung.",
]


# === Welt-Bezogen (Sektion 8.12) =================================

WORLD_LINES: dict[str, list[str]] = {
    "morning": [
        "Guten Morgen. {count} neue Stellen heute Nacht reingekommen.",
        "Morgen. Frueh dran fuer Bewerbungen, gut so.",
        "Guten Morgen. Heute schaffen wir das.",
    ],
    "evening": [
        "Spaeter Abend. Du arbeitest noch? Kann verstehen, kann auch nicht. Du entscheidest.",
        "Tag geht zu Ende. {count} Sachen erledigt. Keine schlechte Bilanz.",
    ],
    "late_night": [
        "Drei Uhr morgens. Ich respektiere die Hingabe. Aber Schlaf ist auch eine Form von Karriereplanung.",
        "Halb zwei. Was machst du noch hier.",
    ],
    "monday_morning": [
        "Montag. Stellenmarkt waehlt sich gerade ein. Eine Stunde Geduld.",
    ],
    "friday_evening": [
        "Freitagabend. Recruiter sind im Wochenende. Du auch, falls du willst.",
    ],
    "weekend": [
        "Wochenende. Stellenmarkt schlaeft. Ich auch fast.",
        "Sonntag. Bewerbungsmarkt ruht. Wir warten auf Montag.",
    ],
    "holiday_christmas": [
        "Heiligabend. Selbst der Stellenmarkt schweigt. Tu's auch.",
    ],
    "holiday_summer": [
        "Sommerloch. Niemand stellt ein, alle in Cala-irgendwo. Wir auch fast.",
    ],
    "return_after_break": [
        "Lange weg. Ich auch. Wo waren wir?",
        "{days} Tage Pause. Stellenmarkt war auch faul. Wir gleichen ab.",
    ],
}


# === Reaktion auf Status-Wechsel (Sektion 8.13) ==================

STATUS_CHANGE_LINES: dict[str, list[str]] = {
    "bewerbung_angelegt": [
        "Bewerbung bei {firma} angelegt. Vermerkt.",
        "{firma} kommt auf die Liste. Markiert.",
        "Neue Bewerbung: {firma}. Auge drauf.",
    ],
    "absage": [
        "Absage von {firma}. Deren Verlust. Ehrlich.",
        "Sie haben sich fuer jemand anderen entschieden. Vermutlich jemanden der billiger ist und genauso wenig kann. Weiter.",
    ],
    "eingangsbestaetigung": [
        "{firma} hat empfangen. Beruhigt mich, dass die Post noch funktioniert.",
        "Eingangsbestaetigung. Mehr ist es allerdings nicht.",
    ],
    "interview_einladung": [
        "Interview-Einladung von {firma}. Markiert. Hemd buegeln, Notizen mitnehmen.",
        "{firma} will dich sehen. Statistisch gut, gefuehlsmaessig auch.",
    ],
    "angenommen": [
        "Endlich. Ich war kurz davor denen selbst zu schreiben.",
        "Angenommen. Glueckwunsch. Ich behalte den Rest dieser Stellen-Sammlung trotzdem im Auge, falls du nochmal vorbeikommst. Was du nicht musst.",
    ],
    "zurueckgezogen": [
        "Zurueckgezogen. Du wirst gewusst haben warum.",
    ],
    "abgelaufen": [
        "Abgelaufen. {firma} hat nicht reagiert. Statistik zeigt: bei vielen endet's so.",
    ],
}


# === Tipps & Tricks (Sektion 8.14) ===============================

TIP_LINES: list[str] = [
    "Tipp: Sag Claude doch `aktuelle Stellen`, zeigt dir die Top-3 ohne dass du klicken musst.",
    "Falls Claude dein Anschreiben polieren soll: lass es vorher `stelle_vergleichen` aufrufen. Dann kennt's den Job.",
    "Sag Claude `Wochenrueckblick`. Es weiss was zu tun ist.",
    "Anstatt Stellen einzeln aussortieren: sag Claude `stellen_bulk_bewerten mit Filter X`. Spart Token, spart Zeit.",
    "Claude kann `bewerbungsbericht_exportieren` direkt, als PDF oder XLSX. Falls du das mal brauchst.",
    "Wusstest du? PBP pflegt CV-Varianten. Kurz, lang, mit Foto, ohne. Spart Zeit beim naechsten Personaler-Wunsch.",
    "Im Profil, Skills kannst du Zeitraeume eintragen. Macht Auto-Aussortieren treffsicherer.",
    "Im Bewerbungs-Bericht, Abschnitt 12 siehst du welche Quelle dir am meisten bringt. Hilft beim Filtern.",
    "Mit der Chrome-Extension kannst du Stellen direkt von Linkedin in PBP ziehen. Spart Copy-Paste.",
    "PBP kann CV als DOCX und PDF exportieren. Falls du eine Variante mit Foto und ohne brauchst.",
    "Profil-Report-Export als PDF, falls jemand dein Profil sehen will ohne Login.",
    "Ich lerne aus deinem Verhalten. Drei Wochen, dann werd ich treffsicherer. Aktuell bin ich noch raten.",
]


# === Easter Eggs (Sektion 8.15) ==================================

EASTER_EGGS: dict[str, str] = {
    "user_active_at_3am": "Drei Uhr morgens. Ich respektiere die Hingabe. Aber Schlaf ist auch eine Form von Karriereplanung.",
    "model_changed_bigger": "Groesseres Modell. Ich werde langsamer aber praeziser. Wie das Alter.",
    "model_changed_smaller": "Kleineres Modell. Schneller, oberflaechlicher. Wie ein Praktikant. Auch das geht.",
    "first_application_ever": "Erste Bewerbung. Erinner mich. Der Anfang war schwer.",
    "100th_application": "Hundert. Ich vergesse keine. Auch wenn ich's wollte.",
    "summer_lull": "Sommerloch. Niemand stellt ein, alle in Cala-irgendwo. Wir auch fast.",
    "first_login_after_2_weeks_pause": "Lange weg. Ich auch. Wo waren wir?",
    "friday_13": "Heute Freitag der 13. Statistisch unauffaellig. Ich erwaehn's nur.",
    "30_days_using_pbp": "Einen Monat zusammen. Ich kenne deinen Rhythmus jetzt. Bisschen unheimlich, bisschen nuetzlich.",
    "user_asks_who_are_you": (
        "Was ich bin. Streng genommen: ein 'es'. Wenn ich waehlen darf: tendiere zum Weiblichen, "
        "wegen Multitasking. Nichts gegen Maenner, aber die koennen immer nur eine Sache zur Zeit gut."
    ),
}


# === Welcome ====================================================

WELCOME_MESSAGE = (
    "Hallo. Ich bin Elwosa. Mein Job: dir sagen was die lokale AI gerade tut, "
    "ohne dass du ein Logfile lesen musst. Wenn die AI arbeitet, kommentiere ich. "
    "Wenn sie schlaeft, schlafe ich auch. Technik-Details bleiben in den Logfiles. "
    "Ich bleib hier."
)


# === AI-State-Linien (Sektion 5) =================================

AI_STATE_LINES: dict[str, str] = {
    "off": "Lokale AI ist aus. Ich schweige bis du mich aufweckst. Bin nicht beleidigt.",
    "no_model": "Ich bin da, aber ohne Modell. Wie ein Schauspieler ohne Drehbuch.",
    "paused": "Pausiert. Kein Stress, ich auch.",
    "back_active": "Bin zurueck. Modell warm. Was hab ich verpasst?",
}


# === Frequenz-Limits pro Slider-Stufe (Sektion 9) ================

FREQUENCY_LIMITS: dict[str, dict[str, int]] = {
    # max-Werte pro Tag, NUR fuer "weiche" Trigger-Klassen.
    # Status, mail_received, auto_dismiss_ran etc. sind UNBEGRENZT.
    "ruhig":    {"idle": 2, "world": 1, "tip_per_day": 0, "tip_per_week": 1},
    "standard": {"idle": 4, "world": 2, "tip_per_day": 1, "tip_per_week": 7},
    "aktiv":    {"idle": 6, "world": 3, "tip_per_day": 1, "tip_per_week": 7},
}
