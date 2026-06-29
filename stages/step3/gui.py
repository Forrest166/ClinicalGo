from __future__ import annotations

import json
import threading
import traceback
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from .config import APP_TITLE, default_input_path, default_output_dir
from .pipeline import run_step3_analysis


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1040x720")
        self.root.minsize(900, 560)
        self.input_paths: list[str] = [default_input_path()]
        self.output_dir = tk.StringVar(value=default_output_dir())
        self.cluster_count = tk.IntVar(value=8)
        self.network_min_edge = tk.IntVar(value=10)
        self.status = tk.StringVar(value="Ready.")
        self.is_running = False

        self._build_ui()
        self._refresh_input_list()

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        top = ttk.Frame(self.root, padding=12)
        top.grid(row=0, column=0, sticky="nsew")
        top.columnconfigure(0, weight=1)
        top.rowconfigure(0, weight=1)

        files = ttk.LabelFrame(top, text="Input files", padding=10)
        files.grid(row=0, column=0, sticky="nsew")
        files.columnconfigure(0, weight=1)
        files.rowconfigure(0, weight=1)
        self.input_list = tk.Listbox(files, height=8)
        self.input_list.grid(row=0, column=0, sticky="nsew")
        file_buttons = ttk.Frame(files)
        file_buttons.grid(row=0, column=1, sticky="ns", padx=(8, 0))
        ttk.Button(file_buttons, text="Add", command=self._add_files).pack(fill="x")
        ttk.Button(file_buttons, text="Remove", command=self._remove_selected).pack(fill="x", pady=(6, 0))
        ttk.Button(file_buttons, text="Clear", command=self._clear_files).pack(fill="x", pady=(6, 0))

        settings = ttk.LabelFrame(self.root, text="Output and settings", padding=12)
        settings.grid(row=1, column=0, sticky="ew", padx=12)
        settings.columnconfigure(1, weight=1)
        ttk.Label(settings, text="Output folder").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(settings, textvariable=self.output_dir).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Button(settings, text="Browse", command=self._browse_output_dir).grid(row=0, column=2, padx=(8, 0), pady=4)
        ttk.Label(settings, text="Cluster count").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Spinbox(settings, from_=2, to=14, textvariable=self.cluster_count, width=8).grid(row=1, column=1, sticky="w", pady=4)
        ttk.Label(settings, text="Network min edge").grid(row=1, column=1, sticky="w", padx=(110, 8), pady=4)
        ttk.Spinbox(settings, from_=1, to=200, textvariable=self.network_min_edge, width=8).grid(row=1, column=1, sticky="w", padx=(250, 0), pady=4)

        actions = ttk.Frame(settings)
        actions.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        self.run_button = ttk.Button(actions, text="Run Step3 Analysis", command=self._start)
        self.run_button.pack(side="left")
        ttk.Label(actions, textvariable=self.status).pack(side="left", padx=(12, 0))

        log_frame = ttk.LabelFrame(self.root, text="Log", padding=12)
        log_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=12)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_box = ScrolledText(log_frame, wrap="word", font=("Consolas", 10))
        self.log_box.grid(row=0, column=0, sticky="nsew")
        self.log_box.configure(state="disabled")

    def _refresh_input_list(self) -> None:
        self.input_list.delete(0, "end")
        for path in self.input_paths:
            self.input_list.insert("end", path)

    def _add_files(self) -> None:
        selected = filedialog.askopenfilenames(
            title="Choose Step2C files",
            filetypes=[("Data files", "*.xlsx *.csv *.tsv"), ("All files", "*.*")],
        )
        for path in selected:
            if path not in self.input_paths:
                self.input_paths.append(path)
        self._refresh_input_list()

    def _remove_selected(self) -> None:
        selected = set(self.input_list.curselection())
        self.input_paths = [path for index, path in enumerate(self.input_paths) if index not in selected]
        self._refresh_input_list()

    def _clear_files(self) -> None:
        self.input_paths = []
        self._refresh_input_list()

    def _browse_output_dir(self) -> None:
        selected = filedialog.askdirectory(title="Choose output folder")
        if selected:
            self.output_dir.set(selected)

    def _append_log(self, message: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message.rstrip() + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _set_running(self, running: bool) -> None:
        self.is_running = running
        self.run_button.configure(state="disabled" if running else "normal")
        if running:
            self.status.set("Running...")

    def _start(self) -> None:
        if self.is_running:
            return
        if not self.input_paths:
            messagebox.showwarning("Step3", "Choose at least one input file.")
            return
        self._set_running(True)
        self._append_log("Starting Step3 analysis...")
        threading.Thread(target=self._run_worker, daemon=True).start()

    def _run_worker(self) -> None:
        try:
            summary = run_step3_analysis(
                input_paths=self.input_paths,
                output_dir=self.output_dir.get(),
                cluster_count=int(self.cluster_count.get()),
                network_min_edge=int(self.network_min_edge.get()),
            )
            rendered = json.dumps(summary, ensure_ascii=False, indent=2)
            self.root.after(0, lambda: self._append_log(rendered))
            self.root.after(0, lambda: self.status.set("Completed."))
            self.root.after(0, lambda: messagebox.showinfo("Step3 Completed", f"Report written to:\n{summary['report_path']}"))
        except Exception as exc:
            message = str(exc)
            details = traceback.format_exc()
            self.root.after(0, lambda: self._append_log(details))
            self.root.after(0, lambda: self.status.set("Error."))
            self.root.after(0, lambda: messagebox.showerror("Step3 Error", message))
        finally:
            self.root.after(0, lambda: self._set_running(False))


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()
