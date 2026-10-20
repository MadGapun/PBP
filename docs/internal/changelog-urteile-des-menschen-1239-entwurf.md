# Entwurf: CHANGELOG-Einträge zu #1239 (die KI lernt nur aus dem, was du selbst aussortiert hast)

> **Kein Teil des CHANGELOG.** Der Text gehört in den Eintrag der Version, die die Korrektur ausliefert. 1.8-Linie: dieser Zweig auf `release/v1.8.0`
> (Eintrag `[1.8.0]`, Abschnitt „Fixed“). Stable: Zweig `fix/urteile-des-menschen-1239-v17` (ein Commit, `d7138da3`, auf dem Kopf von
> `hotfix/v1.7.159`, weil `ist_urteil()` aus #1234 dort erst steht); der Text gilt dort unverändert. Nummer und Datum beim Release einsetzen,
> danach diese Datei löschen.
>
> Belegt: `tests/test_urteile_des_menschen_1239.py` (43 Tests, auf dem Ausgangsstand rot: 40), Gegenprobe Katalog `urteile1239`
> (23 von 23 erkannt, `scripts/mutationstest_auto_update.py --katalog urteile1239`; in Stable gibt es das Skript nicht, dort lief es mit dem
> Skript dieses Zweigs gegen den Stable-Zweig). **Nicht belegt:** ob die Bereinigung die Trefferquote der lokalen KI verändert. Die Messprobe
> (`scripts/api_probe.py`, Entwurfs-PR #1240) und ein eigener Treiber liegen bereit; der Lauf mit dem echten Ollama steht aus.

---

## Eintrag (Titelvorschlag)

**Die KI lernt nur aus dem, was du selbst aussortiert hast**

<!-- anwender -->
Die Auto-Aussortierung zeigt der lokalen KI jetzt nur noch Stellen, die du selbst aussortiert hast, und nur Gründe, die etwas über die Stelle sagen.
Bisher bekam sie als „deine Beispiele“ auch ihre eigenen früheren Urteile und Stellen, die PBP aus anderen Gründen ausgeblendet hatte (zum Beispiel, weil du dich beworben hast): die KI bestätigte sich damit selbst.
<!-- /anwender -->

Der Auftrag an die lokale KI enthält Beispiele („diese Stellen hat der Bewerber zuletzt selbst abgelehnt“) und einen Block mit den häufigsten
Gründen („GELERNT“). Die Dokumentation sagt, dass beides aus den Entscheidungen des Menschen kommt, „sonst lernt das Modell von sich selbst“. Der Filter
schloss aber nur das Präfix `auto:` aus, das PBP seit #913 beim Schreiben entfernt; die Automatik schreibt `dismissed_by='automatik'` und einen Grund
ohne Präfix. Gemessen auf einer Kopie einer echten Datenbank (17.10.2026): alle fünf Beispiele im Auftrag waren Urteile der Automatik (aus einem Lauf vom
Vortag), keine einzige von 3.586 Zeilen trug das Präfix. Der Block „GELERNT“ zählte dieselben Zeilen mit, dazu Systemgründe wie `bewerbung_erstellt`
(das Gegenteil einer Ablehnung) und `profil_match_negativ`.

**Wichtig zu wissen:**

- **Nur deine eigenen Entscheidungen zählen.** Beispiele und häufigste Gründe kommen aus Stellen, die du selbst aussortiert hast, mit einem Grund, der
  ein Urteil über die Stelle ist. Nicht dabei sind: Urteile der Automatik, Systemgründe (`profil_match_negativ`, `firma_blacklisted`, `veraltet_url`,
  `war_nur_anfrage`) und Gründe ohne Aussage über die Passung (`bewerbung_erstellt`, `bereits_beworben`, `duplikat`).
- **Ältere Aussortierungen ohne gespeicherte Herkunft zählen nicht mit.** Vor Version 1.7.64 hat PBP nicht festgehalten, wer aussortiert hat; das
  Aussortier-Protokoll nennt solche Zeilen „unbekannt“. Auf der gemessenen Datenbank sind das 2.488 von 3.586 Zeilen (69 %). „Unbekannt“ ist nicht
  dasselbe wie „war ich“: im Altbestand stecken auch Urteile der Automatik, deren Präfix verloren ging. Folge: die KI bekommt anfangs weniger Beispiele
  und eine kleinere Zählung der Gründe, bis du wieder von Hand aussortiert hast (hast du das seit Version 1.7.64 getan, fällt es kaum auf). Wer den
  Altbestand mitzählen will, ändert eine Zeile (`UNBEKANNTE_HERKUNFT_ZAEHLT` in `services/ablehnungsgruende.py`).
- **Die Statistik bleibt, wie sie war.** Die Zahlen unter „Was PBP gelernt hat“, die Lern-Karte und die Erkenntnisse zählen weiter alle Aussortierungen;
  nur der Auftrag an die KI fragt nach deinen eigenen.
- **Eine Antwort statt zwei.** `urteilsgruende_des_menschen` beantwortet „war das ein Urteil des Menschen?“ für die Beispiele und für die Gründe; ein
  Wächter hält fest, dass die Auto-Aussortierung nur über diesen Weg zählt und `get_recent_user_dismissals` die Funktion wirklich fragt. Das Limit der
  Beispiele gilt nach dem Filter: ein Lauf der Automatik mit zwanzig Stellen verdrängt deine eigenen nicht mehr.
- **Noch nicht gemessen:** ob die Bereinigung die Treffer der KI verbessert. Dass sie die Quelle ihrer Beispiele ehrlich macht, belegen die Tests; die
  Wirkung auf Trefferquote und „zu Unrecht aussortiert“ misst die Probe, sobald der Lauf mit dem echten Ollama gelaufen ist.

### Fixed

- **Beispiele und Lernblock der KI-Aussortierung enthielten Urteile der Automatik und Systemgründe** (#1239): `Database.get_recent_user_dismissals` filterte
  nur das Präfix `auto:`; `gruende_zaehlen(ausser=())` zählte alles mit.

### Changed

- `services/ablehnungsgruende.py`: `urteilsgruende_des_menschen(dismissed_by, dismiss_reason)` (neu, baut auf `aussortier_protokoll.herkunft` und `ist_urteil` aus
  #1234 auf), `gruende_zaehlen(..., nur_menschen=False)`, `UNBEKANNTE_HERKUNFT_ZAEHLT = False`.
- `database.py` (`get_recent_user_dismissals`: ein Cursor mit Filter in Python, das Limit nach dem Filter), `services/auto_aussortierung.py` (der Block „GELERNT“
  zählt mit `nur_menschen=True`).

### Gemessen

43 neue Tests in `tests/test_urteile_des_menschen_1239.py` (auf dem Ausgangsstand rot: 40): die drei Fälle (Automatik ohne Präfix, Systemgrund, Mensch) für beide Leser;
Herkunft unbekannt (mit dem Schalter in beide Richtungen), Präfix, Liste von Gründen, jeder Systemgrund und jeder Grund ohne Urteil aus den Listen, jeder reguläre
Grund; das Limit nach dem Filter; der echte Weg (`stellen_auto_aussortieren` mit einer unechten KI, die den Auftrag mitschreibt, auch die Echokammer als Ablauf
über zwei Läufe und bis in den Text des Auftrags); drei Wächter mit Gegenprobe. Drei ältere Tests (`test_v170_beta63_auto_learn.py`) legen ihre „manuellen“ Zeilen
jetzt mit der Herkunft `ich` an. Gegenprobe (`--katalog urteile1239`): 23 von 23 Eingriffen erkannt, auf Stable-Kopf und Kandidaten-Kopf.
