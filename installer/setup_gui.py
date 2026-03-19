#!/usr/bin/env python3
"""PBP Bewerbungs-Assistent — GUI-Installer für Windows.

Dieses Script kann mit PyInstaller in eine Setup.exe umgewandelt werden:
    pip install pyinstaller
    pyinstaller --onefile --windowed --name "PBP Setup" --icon installer/icon.ico installer/setup_gui.py

Features:
- Grafische Oberfläche (tkinter, bei Python dabei)
- Verzeichniswahl für Installation
- Automatische Python-Erkennung und venv-Erstellung
- Fortschrittsanzeige
- Claude Desktop Konfiguration
- Keine Kommandozeile sichtbar
"""

import os
import sys
import json
import shutil
import subprocess
import threading
import tempfile
import hashlib
from pathlib import Path

# --- Embedded Python Check ---
# If running from PyInstaller bundle, we have Python embedded
IS_FROZEN = getattr(sys, 'frozen', False)
BUNDLE_DIR = Path(sys._MEIPASS) if IS_FROZEN else Path(__file__).parent.parent

# --- GUI ---
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
except ImportError:
    # If tkinter not available (shouldn't happen on Windows)
    print("FEHLER: tkinter nicht verfügbar. Bitte Python mit tkinter installieren.")
    sys.exit(1)


# ============================================================
# Constants
# ============================================================
APP_NAME = "Bewerbungs-Assistent"
APP_VERSION = "0.1.0"
DEFAULT_INSTALL_DIR = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'BewerbungsAssistent')
DATA_DIR_NAME = "BewerbungsAssistent"
PYTHON_MIN_VERSION = (3, 11)
VENV_NAME = ".venv"

# Colors (dark theme matching ELWOSA style)
BG = "#1a1a2e"
BG_CARD = "#16213e"
FG = "#e0e0e0"
ACCENT = "#e94560"
GREEN = "#2ecc71"
YELLOW = "#f1c40f"
DIM = "#7f8c8d"


class InstallerApp:
    """Main installer GUI application."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} — Setup")
        self.root.geometry("640x520")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)

        # Try to center window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - 320
        y = (self.root.winfo_screenheight() // 2) - 260
        self.root.geometry(f"640x520+{x}+{y}")

        # State
        self.install_dir = tk.StringVar(value=DEFAULT_INSTALL_DIR)
        self.install_claude_config = tk.BooleanVar(value=True)
        self.install_scraper = tk.BooleanVar(value=True)
        self.install_docs = tk.BooleanVar(value=True)
        self.current_step = 0
        self.total_steps = 5
        self.python_cmd = None
        self._claude_already_configured = self._detect_claude_config()

        # Build UI
        self._build_header()
        self._build_pages()
        self._show_page("welcome")

    def _build_header(self):
        """Build the header bar."""
        header = tk.Frame(self.root, bg=ACCENT, height=60)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text=f"📋 {APP_NAME}", font=("Segoe UI", 16, "bold"),
                 bg=ACCENT, fg="white").pack(side="left", padx=20, pady=10)
        tk.Label(header, text=f"v{APP_VERSION}", font=("Segoe UI", 10),
                 bg=ACCENT, fg="#ffcccc").pack(side="right", padx=20)

    def _build_pages(self):
        """Build all pages (stacked frames)."""
        self.container = tk.Frame(self.root, bg=BG)
        self.container.pack(fill="both", expand=True, padx=20, pady=10)

        self.pages = {}
        self._build_welcome_page()
        self._build_options_page()
        self._build_install_page()
        self._build_done_page()
        self._build_error_page()

    def _show_page(self, name):
        """Show a specific page, hide others."""
        for pname, frame in self.pages.items():
            if pname == name:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()

    # ---- Welcome Page ----
    def _build_welcome_page(self):
        page = tk.Frame(self.container, bg=BG)
        self.pages["welcome"] = page

        tk.Label(page, text="Willkommen!", font=("Segoe UI", 18, "bold"),
                 bg=BG, fg=FG).pack(pady=(20, 10))

        info = (
            "Der Bewerbungs-Assistent hilft dir bei der Jobsuche.\n"
            "Er läuft als Plugin in Claude Desktop und hat\n"
            "ein eigenes Browser-Dashboard.\n\n"
            "Dieses Setup installiert alles Nötige:\n"
            "  • Python-Umgebung (isoliert, ändert nichts am System)\n"
            "  • Bewerbungs-Assistent mit allen Modulen\n"
            "  • Verbindung zu Claude Desktop (optional)\n"
        )
        tk.Label(page, text=info, font=("Segoe UI", 10), bg=BG, fg=DIM,
                 justify="left").pack(pady=5)

        btn_frame = tk.Frame(page, bg=BG)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text="Weiter →", font=("Segoe UI", 11, "bold"),
                  bg=ACCENT, fg="white", padx=30, pady=8, bd=0, cursor="hand2",
                  command=self._go_to_options).pack()

    # ---- Options Page ----
    def _build_options_page(self):
        page = tk.Frame(self.container, bg=BG)
        self.pages["options"] = page

        tk.Label(page, text="Einstellungen", font=("Segoe UI", 16, "bold"),
                 bg=BG, fg=FG).pack(pady=(15, 10))

        # Install directory
        dir_frame = tk.LabelFrame(page, text=" Installationsverzeichnis ",
                                   font=("Segoe UI", 10), bg=BG_CARD, fg=FG,
                                   padx=10, pady=10)
        dir_frame.pack(fill="x", pady=5)

        dir_row = tk.Frame(dir_frame, bg=BG_CARD)
        dir_row.pack(fill="x")
        tk.Entry(dir_row, textvariable=self.install_dir, font=("Consolas", 9),
                 bg="#0f3460", fg=FG, insertbackground=FG, bd=1,
                 relief="solid").pack(side="left", fill="x", expand=True, ipady=4)
        tk.Button(dir_row, text="Durchsuchen...", font=("Segoe UI", 9),
                  bg="#0f3460", fg=FG, bd=1, cursor="hand2",
                  command=self._browse_dir).pack(side="right", padx=(8, 0))

        # Options
        opt_frame = tk.LabelFrame(page, text=" Komponenten ",
                                   font=("Segoe UI", 10), bg=BG_CARD, fg=FG,
                                   padx=10, pady=10)
        opt_frame.pack(fill="x", pady=10)

        claude_label = "Claude Desktop verbinden (MCP Plugin)"
        if self._claude_already_configured:
            claude_label += "  ✓ bereits konfiguriert"
            self.install_claude_config.set(False)
        tk.Checkbutton(opt_frame, text=claude_label,
                       variable=self.install_claude_config, font=("Segoe UI", 10),
                       bg=BG_CARD, fg=FG, selectcolor=BG,
                       activebackground=BG_CARD, activeforeground=FG
                       ).pack(anchor="w", pady=2)
        tk.Checkbutton(opt_frame, text="Job-Scraper (StepStone, Indeed, freelance.de, ...)",
                       variable=self.install_scraper, font=("Segoe UI", 10),
                       bg=BG_CARD, fg=FG, selectcolor=BG,
                       activebackground=BG_CARD, activeforeground=FG
                       ).pack(anchor="w", pady=2)
        tk.Checkbutton(opt_frame, text="PDF/DOCX-Export (Lebenslauf, Anschreiben)",
                       variable=self.install_docs, font=("Segoe UI", 10),
                       bg=BG_CARD, fg=FG, selectcolor=BG,
                       activebackground=BG_CARD, activeforeground=FG
                       ).pack(anchor="w", pady=2)

        # Buttons
        btn_frame = tk.Frame(page, bg=BG)
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="← Zurück", font=("Segoe UI", 10),
                  bg="#333", fg=FG, padx=20, pady=6, bd=0, cursor="hand2",
                  command=lambda: self._show_page("welcome")).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Installieren →", font=("Segoe UI", 11, "bold"),
                  bg=GREEN, fg="white", padx=30, pady=8, bd=0, cursor="hand2",
                  command=self._start_install).pack(side="left", padx=5)

    # ---- Install Page (Progress) ----
    def _build_install_page(self):
        page = tk.Frame(self.container, bg=BG)
        self.pages["install"] = page

        tk.Label(page, text="Installation läuft...", font=("Segoe UI", 16, "bold"),
                 bg=BG, fg=FG).pack(pady=(20, 10))

        # Progress bar
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Custom.Horizontal.TProgressbar",
                        troughcolor=BG_CARD, background=GREEN,
                        thickness=20)
        self.progress = ttk.Progressbar(page, length=500, mode='determinate',
                                         style="Custom.Horizontal.TProgressbar")
        self.progress.pack(pady=10)

        # Step label
        self.step_label = tk.Label(page, text="Vorbereitung...",
                                    font=("Segoe UI", 10), bg=BG, fg=DIM)
        self.step_label.pack(pady=5)

        # Log area
        log_frame = tk.Frame(page, bg=BG_CARD, bd=1, relief="solid")
        log_frame.pack(fill="both", expand=True, pady=10)

        self.log_text = tk.Text(log_frame, bg=BG_CARD, fg=DIM,
                                 font=("Consolas", 9), wrap="word",
                                 state="disabled", bd=0, padx=10, pady=10)
        self.log_text.pack(fill="both", expand=True)

        # Tags for colored log
        self.log_text.tag_configure("ok", foreground=GREEN)
        self.log_text.tag_configure("warn", foreground=YELLOW)
        self.log_text.tag_configure("error", foreground=ACCENT)
        self.log_text.tag_configure("info", foreground=FG)

    # ---- Done Page ----
    def _build_done_page(self):
        page = tk.Frame(self.container, bg=BG)
        self.pages["done"] = page

        tk.Label(page, text="✓ Installation abgeschlossen!",
                 font=("Segoe UI", 18, "bold"), bg=BG, fg=GREEN).pack(pady=(30, 10))

        self.done_info = tk.Label(page, text="", font=("Segoe UI", 10),
                                   bg=BG, fg=DIM, justify="left")
        self.done_info.pack(pady=10)

        btn_frame = tk.Frame(page, bg=BG)
        btn_frame.pack(pady=15)

        tk.Button(btn_frame, text="Dashboard öffnen",
                  font=("Segoe UI", 11, "bold"),
                  bg=ACCENT, fg="white", padx=20, pady=8, bd=0, cursor="hand2",
                  command=self._open_dashboard).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Schließen", font=("Segoe UI", 10),
                  bg="#333", fg=FG, padx=20, pady=6, bd=0, cursor="hand2",
                  command=self.root.quit).pack(side="left", padx=5)

    # ---- Error Page ----
    def _build_error_page(self):
        page = tk.Frame(self.container, bg=BG)
        self.pages["error"] = page

        tk.Label(page, text="✗ Fehler bei der Installation",
                 font=("Segoe UI", 16, "bold"), bg=BG, fg=ACCENT).pack(pady=(30, 10))

        self.error_info = tk.Label(page, text="", font=("Segoe UI", 10),
                                    bg=BG, fg=DIM, justify="left", wraplength=550)
        self.error_info.pack(pady=10)

        btn_frame = tk.Frame(page, bg=BG)
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="Erneut versuchen", font=("Segoe UI", 10),
                  bg=ACCENT, fg="white", padx=20, pady=6, bd=0, cursor="hand2",
                  command=lambda: self._show_page("options")).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Schließen", font=("Segoe UI", 10),
                  bg="#333", fg=FG, padx=20, pady=6, bd=0, cursor="hand2",
                  command=self.root.quit).pack(side="left", padx=5)

    # ============================================================
    # Actions
    # ============================================================

    def _browse_dir(self):
        """Open folder picker dialog."""
        d = filedialog.askdirectory(title="Installationsverzeichnis wählen",
                                     initialdir=self.install_dir.get())
        if d:
            self.install_dir.set(d)

    def _go_to_options(self):
        """Switch to options page."""
        self._show_page("options")

    def _log(self, msg, tag="info"):
        """Append to install log."""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n", tag)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_step(self, step, text):
        """Update progress bar and step label."""
        self.current_step = step
        pct = int((step / self.total_steps) * 100)
        self.progress['value'] = pct
        self.step_label.configure(text=f"[{step}/{self.total_steps}] {text}")
        self.root.update_idletasks()

    def _start_install(self):
        """Start installation in background thread."""
        self._show_page("install")
        thread = threading.Thread(target=self._run_install, daemon=True)
        thread.start()

    def _run_install(self):
        """Main installation logic (runs in background thread)."""
        install_dir = self.install_dir.get()

        try:
            # Step 1: Find or check Python
            self._set_step(1, "Prüfe Python...")
            python_cmd = self._find_python()
            if not python_cmd:
                self._show_error(
                    "Python 3.11+ wurde nicht gefunden.\n\n"
                    "Bitte installiere Python von python.org\n"
                    "und aktiviere 'Add Python to PATH'.\n\n"
                    "Danach Setup erneut starten."
                )
                return
            self._log(f"✓ Python gefunden: {python_cmd}", "ok")

            # Step 2: Create install directory + venv
            self._set_step(2, "Erstelle Programmumgebung...")
            os.makedirs(install_dir, exist_ok=True)

            # Copy project files if running from bundle
            project_dir = self._prepare_project_files(install_dir)
            self._log(f"✓ Projektverzeichnis: {project_dir}", "ok")

            venv_dir = os.path.join(install_dir, VENV_NAME)
            venv_python = os.path.join(venv_dir, "Scripts", "python.exe")

            if not os.path.exists(venv_python):
                self._log("Erstelle virtuelle Umgebung...", "info")
                r = subprocess.run(
                    [python_cmd, "-m", "venv", venv_dir],
                    capture_output=True, text=True, timeout=120
                )
                if r.returncode != 0 or not os.path.exists(venv_python):
                    self._show_error(
                        "Virtuelle Umgebung konnte nicht erstellt werden.\n\n"
                        f"Fehler: {r.stderr[:300]}\n\n"
                        "Tipp: Versuche das Setup als Administrator auszuführen."
                    )
                    return
            self._log("✓ Virtuelle Umgebung bereit", "ok")

            # Step 3: Install packages
            self._set_step(3, "Installiere Pakete...")

            # Upgrade pip
            self._run_pip(venv_python, ["install", "--upgrade", "pip"], "pip aktualisiert")

            # Install core
            self._log("Installiere Kernpakete...", "info")
            ok = self._run_pip(venv_python, ["install", "-e", project_dir + "/."],
                                "Kernpakete installiert")
            if not ok:
                self._show_error(
                    "Kernpakete konnten nicht installiert werden.\n\n"
                    "Prüfe deine Internetverbindung und\n"
                    "versuche es erneut."
                )
                return

            # Install optional packages
            extras = []
            if self.install_scraper.get():
                extras.append("scraper")
            if self.install_docs.get():
                extras.append("docs")

            if extras:
                extra_str = ",".join(extras)
                self._log(f"Installiere Zusatzpakete ({extra_str})...", "info")
                ok = self._run_pip(venv_python,
                                    ["install", "-e", f"{project_dir}/.[{extra_str}]"],
                                    "Zusatzpakete installiert")
                if not ok:
                    self._log("⚠ Einige Zusatzpakete konnten nicht installiert werden", "warn")
                    self._log("  Kernfunktionen sind trotzdem verfügbar.", "warn")

            # Step 4: Create data directories
            self._set_step(4, "Erstelle Datenverzeichnisse...")
            data_dir = os.path.join(os.environ.get('LOCALAPPDATA', install_dir), DATA_DIR_NAME)
            for sub in ['dokumente', 'export', 'logs']:
                os.makedirs(os.path.join(data_dir, sub), exist_ok=True)
            self._log(f"✓ Datenverzeichnis: {data_dir}", "ok")

            # Step 5: Configure Claude Desktop
            self._set_step(5, "Konfiguriere Claude Desktop...")
            if self.install_claude_config.get():
                self._configure_claude(venv_python, data_dir)

            # Run quick test
            self._log("\nPrüfe Installation...", "info")
            test_ok = self._run_test(venv_python)
            if test_ok:
                self._log("✓ Alle Tests bestanden!", "ok")
            else:
                self._log("⚠ Tests teilweise fehlgeschlagen — prüfe die Installation", "warn")

            # Done!
            self.root.after(0, lambda: self._show_done(install_dir, data_dir, venv_python))

        except Exception as e:
            self._show_error(f"Unerwarteter Fehler:\n\n{str(e)}")

    def _find_python(self) -> str | None:
        """Find a suitable Python installation."""
        for cmd in ["python", "py -3", "python3"]:
            try:
                r = subprocess.run(
                    cmd.split() + ["-c", "import sys; print(sys.version_info[:2])"],
                    capture_output=True, text=True, timeout=10
                )
                if r.returncode == 0:
                    version = eval(r.stdout.strip())
                    if version >= PYTHON_MIN_VERSION:
                        self.python_cmd = cmd
                        return cmd
                    else:
                        self._log(f"Python {version} zu alt (min {PYTHON_MIN_VERSION})", "warn")
            except Exception:
                continue
        return None

    def _prepare_project_files(self, install_dir: str) -> str:
        """Copy project files to install directory.

        If running from PyInstaller bundle, extract embedded files.
        If running from source, use the parent directory.
        """
        if IS_FROZEN:
            # Running from .exe — copy bundled project files
            src = os.path.join(BUNDLE_DIR, "bewerbungs-assistent")
            dst = os.path.join(install_dir, "bewerbungs-assistent")
            if not os.path.exists(dst):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            return dst
        else:
            # Running from source — project is in parent directory
            return str(BUNDLE_DIR)

    def _run_pip(self, venv_python: str, args: list, success_msg: str) -> bool:
        """Run pip command and log result."""
        try:
            full_cmd = [venv_python, "-m", "pip"] + args + ["-q"]
            r = subprocess.run(full_cmd, capture_output=True, text=True, timeout=300)
            if r.returncode == 0:
                self._log(f"✓ {success_msg}", "ok")
                return True
            else:
                err = r.stderr.strip()[:200] if r.stderr else "Unbekannter Fehler"
                self._log(f"✗ Fehler: {err}", "error")
                return False
        except subprocess.TimeoutExpired:
            self._log("✗ Zeitüberschreitung bei Installation", "error")
            return False
        except Exception as e:
            self._log(f"✗ {str(e)}", "error")
            return False

    def _detect_claude_config(self) -> bool:
        """Check if Claude Desktop is already configured with PBP."""
        try:
            config_path = os.path.join(os.environ.get('APPDATA', ''), 'Claude', 'claude_desktop_config.json')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                return 'bewerbungs-assistent' in config.get('mcpServers', {})
        except Exception:
            pass
        return False

    def _configure_claude(self, venv_python: str, data_dir: str):
        """Configure Claude Desktop to use PBP as MCP server."""
        try:
            config_dir = os.path.join(os.environ.get('APPDATA', ''), 'Claude')
            os.makedirs(config_dir, exist_ok=True)
            config_path = os.path.join(config_dir, 'claude_desktop_config.json')

            # Load existing config
            config = {"mcpServers": {}}
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    if 'mcpServers' not in config:
                        config['mcpServers'] = {}
                except Exception:
                    pass

            # Add MCP server entry
            config['mcpServers']['bewerbungs-assistent'] = {
                'command': venv_python,
                'args': ['-m', 'bewerbungs_assistent'],
                'env': {'BA_DATA_DIR': data_dir}
            }

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            self._log("✓ Claude Desktop konfiguriert", "ok")
        except Exception as e:
            self._log(f"⚠ Claude-Konfiguration fehlgeschlagen: {e}", "warn")
            self._log("  Du kannst das später manuell nachholen.", "warn")

    def _run_test(self, venv_python: str) -> bool:
        """Quick functional test."""
        try:
            test_code = (
                "from bewerbungs_assistent.database import Database, _gen_id; "
                "from bewerbungs_assistent.job_scraper import calculate_score; "
                "import tempfile, os, shutil; "
                "d = tempfile.mkdtemp(); "
                "os.environ['BA_DATA_DIR'] = d; "
                "db = Database(); db.initialize(); "
                "db.save_profile({'name': 'Test'}); "
                "assert db.get_profile()['name'] == 'Test'; "
                "db.close(); shutil.rmtree(d); "
                "print('OK')"
            )
            r = subprocess.run([venv_python, "-c", test_code],
                               capture_output=True, text=True, timeout=30)
            return r.returncode == 0 and "OK" in r.stdout
        except Exception:
            return False

    def _show_done(self, install_dir, data_dir, venv_python):
        """Show the done page."""
        info = (
            f"Installiert in: {install_dir}\n"
            f"Datenverzeichnis: {data_dir}\n\n"
            "Nächste Schritte:\n"
            "  1. Claude Desktop neu starten\n"
            "  2. In Claude eintippen: \"Ersterfassung starten\"\n\n"
            f"Browser-Dashboard: http://localhost:8200\n"
            f"(verfügbar wenn Claude Desktop läuft)"
        )
        self.done_info.configure(text=info)
        self._venv_python = venv_python
        self._show_page("done")

    def _show_error(self, message):
        """Show error page."""
        self.root.after(0, lambda: self._do_show_error(message))

    def _do_show_error(self, message):
        self.error_info.configure(text=message)
        self._show_page("error")

    def _open_dashboard(self):
        """Start the demo dashboard."""
        try:
            project_dir = os.path.join(self.install_dir.get(), "bewerbungs-assistent")
            demo_script = os.path.join(project_dir, "test_demo.py")
            if os.path.exists(demo_script):
                subprocess.Popen([self._venv_python, demo_script],
                                  creationflags=subprocess.CREATE_NO_WINDOW
                                  if sys.platform == 'win32' else 0)
                import time
                time.sleep(3)
            # Open browser
            import webbrowser
            webbrowser.open("http://localhost:8200")
        except Exception as e:
            messagebox.showinfo("Hinweis",
                                f"Dashboard konnte nicht gestartet werden.\n"
                                f"Starte Claude Desktop und öffne dann\n"
                                f"http://localhost:8200 im Browser.\n\n{e}")

    def run(self):
        """Start the installer GUI."""
        self.root.mainloop()


# ============================================================
# Entry point
# ============================================================
if __name__ == "__main__":
    app = InstallerApp()
    app.run()
