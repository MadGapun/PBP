# PBP Issue-Template (fuer Claude Chat)

<!-- Dieses Template ist fuer Claude Chat (claude.ai). Bitte vollstaendig ausfullen. -->
<!-- Claude Code liest dieses Issue und implementiert direkt — je praeziser, desto besser. -->

## Betrifft
<!-- Version + betroffene Datei(en) mit Zeilennummern -->
`vX.Y.Z` - `pfad/zur/datei.py` (Zeile 123) - `frontend/src/pages/Seite.jsx`

## Typ
<!-- Bug / Feature / UX / Performance / Refactoring -->
Bug

## Verhalten

### Ist
<!-- Was passiert gerade, ggf. mit Screenshot-Beschreibung oder DB-Daten -->

### Soll
<!-- Was soll passieren -->

### Reproduktion (bei Bugs)
<!-- Schritte zum Reproduzieren -->
1. 
2. 
3. 

### Datenlage (falls relevant)
<!-- DB-Abfragen, API-Responses, konkrete Werte die Chat verifiziert hat -->
```
Beispiel: SELECT COUNT(*) FROM meetings WHERE ... => 11 Eintraege vorhanden
```

---

## Ursachenanalyse
<!-- Was Chat durch Codeanalyse gefunden hat. Hypothesen kennzeichnen! -->
<!-- Code MUSS das verifizieren bevor er aendert. -->

**Hypothese 1:** ...
**Hypothese 2:** ...

---

## Loesung / Anforderungen
<!-- Was geaendert werden soll. So konkret wie moeglich. -->
<!-- Keine Implementierungsdetails vorgeben die Code besser weiss. -->

---

## Betroffene Dateien

| Datei | Was zu pruefen / aendern |
|---|---|
| `src/...` | ... |
| `frontend/src/...` | ... |

---

## Was NICHT anfassen
<!-- Explizit: was bleibt unveraendert, auch wenn es verlockend waere -->
- 
- 

---

## Akzeptanzkriterien
<!-- Checklist. Jeder Punkt muss true sein damit das Issue geschlossen werden kann. -->
<!-- Muss testbar sein — kein "sieht gut aus". -->
- [ ] 
- [ ] 
- [ ] Tests: `python -m pytest tests/ -q` — alle gruen
- [ ] Frontend gebaut: `pnpm run build` — kein Fehler

---

## Kontext fuer Claude Code
<!-- Optionale Infos die beim Verstehen helfen aber nicht zur Loesung gehoeren -->
<!-- z.B. warum der Nutzer das braucht, was vorher probiert wurde -->
