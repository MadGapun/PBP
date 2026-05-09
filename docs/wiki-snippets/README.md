# PBP Wiki-Snippets (#623)

Kuratierte kurze Hinweise aus dem [PBP-Wiki](https://github.com/MadGapun/PBP/wiki).
Werden vom Backend (`services/wiki_snippets.py`) beim Start eingelesen und ueber
`POST /api/wiki/request-hint` an Elwosa geliefert. Elwosa postet sie als
`wiki_hint`-Trigger in den Sidebar-Chat — max 1x pro Page-Route pro Tag.

## Format

Jede `*.md`-Datei (außer `README.md`) ist ein Snippet:

```markdown
---
id: jobs-scoring
page_route: stellen
title: Score-Logik in 6 Dimensionen
wiki_page: Tab-Stellen
---
Jede Stelle bekommt einen Fit-Score aus 6 Kriterien — Skills, Erfahrung,
Branche, Standort, Gehalt, Arbeitsmodell. [link:wiki:Tab-Stellen|im Wiki nachlesen]
```

### Pflicht-Felder

| Feld | Bedeutung |
|---|---|
| `id` | Eindeutig (snake-case). Wird in `elwosa_messages.trigger_ref` gespeichert. |
| `page_route` | Frontend-Route — `dashboard`, `stellen`, `bewerbungen`, `dokumente`, `profil`, `einstellungen`, `kalender`, `statistiken`, oder `global` (immer relevant). Muss zur Page-ID in App.jsx (`TAB_CONFIG`) passen. |
| `wiki_page` | Wiki-Seitenname (ohne `.md`). Frontend baut daraus `https://github.com/MadGapun/PBP/wiki/{wiki_page}` als Link-Ziel. |

### Body-Regeln (Sprach-DNA)

- Max **280 Zeichen** sichtbar (Markup wird gestrippt vor Pruefung)
- Keine Ausrufezeichen, keine Emojis, keine Hoeflichkeits-Anrede (`Ihre`, `Ihnen`)
- Mind. ein `[link:wiki:PageName|Linktext]`-Markup → Klick oeffnet die Wiki-Seite
- Max **1** `**bold**`-Markierung
- Tonfall: lakonisch-britisch, wie Elwosa allgemein

Validator: `services/elwosa.py::validate_tonfall` greift auf den fertig
gerenderten Text vor dem Posten.

## Snippet-Auswahl

Beim `/api/wiki/request-hint?page=jobs` waehlt der Service:
1. Alle Snippets fuer `page_route="jobs"` plus `page_route="global"`
2. Die in den letzten 24h NICHT fuer dieses Profil gepostet wurden
3. Zufaellig einen davon
4. Wenn alle aufgebraucht: einer aus dem 24h+-Topf

Frequenz-Drosselung wie alle anderen `tip`-Trigger via Elwosa-Frequenz-Slider.

## Pflege

- Bei jeder Wiki-Aenderung pruefen ob ein Snippet aktualisiert oder neu
  angelegt werden sollte
- Bei jedem PBP-Release: Snippets gegen aktuelle Wiki-Pages abgleichen
- Bei kompletter UI-Aenderung einer Page: zugehoerige Snippets archivieren
  oder umschreiben
