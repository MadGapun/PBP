import { Component } from "react";

// v1.7.0-beta.93: App-weites Sicherheitsnetz. Ohne diese Grenze blankt ein
// einzelner Render-Fehler (z.B. eine undefinierte Komponente) den GANZEN
// React-Baum — der User sah nur noch den blauen Shell-Hintergrund und kam
// an keine Einstellung mehr (auch nicht, um die Ursache rueckgaengig zu
// machen). Mit dieser Boundary bleibt die Sidebar bedienbar und der
// betroffene Bereich zeigt eine Fehlerkarte statt alles mitzureissen.
//
// Bewusst OHNE Abhaengigkeit von @/components/ui — die Fallback-UI muss
// auch dann rendern, wenn an anderer Stelle etwas kaputt ist.
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    if (typeof console !== "undefined" && console.error) {
      console.error("PBP-Render-Fehler abgefangen:", error, info);
    }
  }

  handleRetry = () => this.setState({ error: null });

  handleReload = () => {
    if (typeof window !== "undefined") window.location.reload();
  };

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="p-6">
        <div className="glass-card-strong max-w-2xl rounded-2xl border border-coral/25 p-6">
          <h2 className="text-lg font-semibold text-ink">
            Dieser Bereich ist abgestuerzt
          </h2>
          <p className="mt-2 text-sm leading-snug text-muted/70">
            In diesem Tab ist ein Anzeigefehler aufgetreten. Der Rest von PBP
            laeuft weiter — du kannst links einen anderen Bereich waehlen oder
            es hier nochmal versuchen. Deine Daten sind davon nicht betroffen.
          </p>
          <pre className="mt-3 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-black/20 p-2 font-mono text-[11px] text-coral/80">
            {String(error?.message || error)}
          </pre>
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={this.handleRetry}
              className="rounded-lg border border-white/10 px-3 py-1.5 text-sm text-ink transition hover:bg-white/5"
            >
              Nochmal versuchen
            </button>
            <button
              type="button"
              onClick={this.handleReload}
              className="rounded-lg border border-white/10 px-3 py-1.5 text-sm text-ink transition hover:bg-white/5"
            >
              Seite neu laden
            </button>
          </div>
        </div>
      </div>
    );
  }
}
