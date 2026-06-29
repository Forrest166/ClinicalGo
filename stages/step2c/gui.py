from __future__ import annotations

import json
import threading
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from pathlib import Path

from .config import (
    APP_TITLE,
    default_normalized_output,
    default_raw_output,
    default_step2a_input,
    default_step2a_output,
    default_step2b_input,
    default_step2b_output,
    default_summary_output,
    ensure_rules_dir,
)
from .pipeline import run_step2c


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("980x620")
        self.root.minsize(860, 520)
        self.is_running = False

        self.step2a_input = tk.StringVar(value=default_step2a_input())
        self.step2b_input = tk.StringVar(value=default_step2b_input())
        self.step2a_output = tk.StringVar(value=default_step2a_output())
        self.step2b_output = tk.StringVar(value=default_step2b_output())
        self.raw_output = tk.StringVar(value=default_raw_output())
        self.normalized_output = tk.StringVar(value=default_normalized_output())
        self.summary_output = tk.StringVar(value=default_summary_output())
        self.status = tk.StringVar(value="Ready.")

        self._build_ui()

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        files = ttk.LabelFrame(self.root, text="Files", padding=12)
        files.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        files.columnconfigure(1, weight=1)

        rows = [
            ("Step2A input", self.step2a_input, self._browse_open_xlsx),
            ("Step2B input", self.step2b_input, self._browse_open_xlsx),
            ("Step2A output", self.step2a_output, self._browse_save_xlsx),
            ("Step2B output", self.step2b_output, self._browse_save_xlsx),
            ("Raw merged output", self.raw_output, self._browse_save_xlsx),
            ("Standardized output", self.normalized_output, self._browse_save_xlsx),
            ("Summary JSON", self.summary_output, self._browse_save_json),
        ]
        for row_index, (label, variable, browse_func) in enumerate(rows):
            ttk.Label(files, text=label).grid(row=row_index, column=0, sticky="w", padx=(0, 8), pady=4)
            ttk.Entry(files, textvariable=variable).grid(row=row_index, column=1, sticky="ew", pady=4)
            ttk.Button(files, text="Browse", command=lambda var=variable, func=browse_func: func(var)).grid(
                row=row_index,
                column=2,
                padx=(8, 0),
                pady=4,
            )

        actions = ttk.Frame(self.root, padding=(12, 0, 12, 0))
        actions.grid(row=1, column=0, sticky="ew")
        self.run_button = ttk.Button(actions, text="Run Step2C", command=self._start)
        self.run_button.pack(side="left")
        ttk.Label(actions, textvariable=self.status).pack(side="left", padx=(12, 0))

        log_frame = ttk.LabelFrame(self.root, text="Log", padding=12)
        log_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=12)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_box = ScrolledText(log_frame, wrap="word", font=("Consolas", 10))
        self.log_box.grid(row=0, column=0, sticky="nsew")
        self.log_box.configure(state="disabled")

    def _browse_open_xlsx(self, variable: tk.StringVar) -> None:
        selected = filedialog.askopenfilename(
            title="Choose Excel input",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
        )
        if selected:
            variable.set(selected)

    def _browse_save_xlsx(self, variable: tk.StringVar) -> None:
        selected = filedialog.asksaveasfilename(
            title="Choose Excel output",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            initialfile=Path(variable.get() or "output.xlsx").name,
        )
        if selected:
            variable.set(selected)

    def _browse_save_json(self, variable: tk.StringVar) -> None:
        selected = filedialog.asksaveasfilename(
            title="Choose JSON output",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=Path(variable.get() or "summary.json").name,
        )
        if selected:
            variable.set(selected)

    def _append_log(self, message: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message.rstrip() + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _set_running(self, running: bool) -> None:
        self.is_running = running
        self.run_button.configure(state="disabled" if running else "normal")
        self.status.set("Running..." if running else "Ready.")

    def _start(self) -> None:
        if self.is_running:
            return
        self._set_running(True)
        self._append_log("Starting Step2C...")
        threading.Thread(target=self._run_worker, daemon=True).start()

    def _run_worker(self) -> None:
        try:
            ensure_rules_dir()
            summary = run_step2c(
                step2a_input=self.step2a_input.get(),
                step2b_input=self.step2b_input.get(),
                step2a_output=self.step2a_output.get(),
                step2b_output=self.step2b_output.get(),
                raw_output=self.raw_output.get(),
                normalized_output=self.normalized_output.get(),
                summary_output=self.summary_output.get(),
            )
            rendered = json.dumps(summary, ensure_ascii=False, indent=2)
            self.root.after(0, lambda: self._append_log(rendered))
            self.root.after(0, lambda: self.status.set("Completed."))
            self.root.after(0, lambda: messagebox.showinfo("Step2C Completed", "Step2C outputs were written successfully."))
        except Exception as exc:
            message = str(exc)
            details = traceback.format_exc()
            self.root.after(0, lambda: self._append_log(details))
            self.root.after(0, lambda: self.status.set("Error."))
            self.root.after(0, lambda: messagebox.showerror("Step2C Error", message))
        finally:
            self.root.after(0, lambda: self._set_running(False))


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()
