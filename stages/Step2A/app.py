from __future__ import annotations

import sys
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.api_keys import load_api_key_bundle
from common.provider_catalog import get_models, recommended_summary, resolve_model_name
from config import (
    APP_TITLE,
    checkpoint_path_for_output,
    default_output_path,
    default_source_path,
    ensure_output_prefix,
)
from pipeline import (
    Step2AError,
    UserCancelledError,
    load_checkpoint_progress,
    process_file,
    rebuild_excel_from_checkpoint,
    run_population_rescue_stage,
)
from population_rescue_manifest import population_rescue_manifest_path_for_output
from prompt_templates import DEFAULT_PROMPT_TEMPLATE


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1260x860")
        self.root.minsize(1120, 760)
        self.ui_alive = True

        default_source = default_source_path()
        initial_output_source = default_source if Path(default_source).is_file() else ""
        self.source_path = tk.StringVar(value=default_source)
        self.output_path = tk.StringVar(value=default_output_path(initial_output_source))
        self.provider = tk.StringVar(value="Gemini")
        self.model = tk.StringVar(value="gemini-2.5-flash")
        self.custom_model = tk.StringVar()
        self.api_key = tk.StringVar()
        self.base_url = tk.StringVar()
        self.batch_size = tk.IntVar(value=8)
        self.timeout_seconds = tk.IntVar(value=120)
        self.retries = tk.IntVar(value=2)
        self.concurrency = tk.IntVar(value=1)
        self.status_text = tk.StringVar(value="Ready.")
        self.progress_text = tk.StringVar(value="Records: 0/0")
        self.rows_text = tk.StringVar(value="Rows: 0")
        self.success_text = tk.StringVar(value="Success: 0")
        self.failure_text = tk.StringVar(value="Failed: 0")
        self.token_text = tk.StringVar(value="Tokens: 0 / 0 / 0")
        self.checkpoint_text = tk.StringVar(value="Checkpoint: -")
        self.recommendation_text = tk.StringVar()
        self.progress_value = tk.DoubleVar(value=0.0)
        self.provider_keys = {}
        self.base_urls = {}
        self.is_running = False
        self.stop_requested = False

        self._build_ui()
        self._load_api_keys()
        self._refresh_models()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    @staticmethod
    def _default_base_url_for_provider(provider: str) -> str:
        if provider == "OpenAI-Compatible":
            return "https://api.openai.com/v1"
        if provider == "NVIDIA NIM":
            return "https://integrate.api.nvidia.com/v1"
        if provider == "GitHub Models":
            return "https://models.github.ai/inference"
        if provider == "Mistral":
            return "https://api.mistral.ai/v1"
        return ""

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        viewport = ttk.Frame(self.root)
        viewport.grid(sticky="nsew")
        viewport.columnconfigure(0, weight=1)
        viewport.rowconfigure(0, weight=1)

        self.page_canvas = tk.Canvas(viewport, highlightthickness=0)
        self.page_canvas.grid(row=0, column=0, sticky="nsew")
        self.page_scrollbar = ttk.Scrollbar(viewport, orient="vertical", command=self.page_canvas.yview)
        self.page_scrollbar.grid(row=0, column=1, sticky="ns")
        self.page_canvas.configure(yscrollcommand=self.page_scrollbar.set)

        outer = ttk.Frame(self.page_canvas, padding=12)
        self.page_canvas_window = self.page_canvas.create_window((0, 0), window=outer, anchor="nw")
        outer.bind("<Configure>", self._on_page_frame_configure)
        self.page_canvas.bind("<Configure>", self._on_page_canvas_configure)
        self.root.bind_all("<MouseWheel>", self._on_global_mousewheel, add="+")
        self.root.bind_all("<Button-4>", self._on_global_mousewheel, add="+")
        self.root.bind_all("<Button-5>", self._on_global_mousewheel, add="+")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(5, weight=1)

        files = ttk.LabelFrame(outer, text="Files", padding=10)
        files.grid(row=0, column=0, sticky="ew")
        files.columnconfigure(1, weight=1)
        ttk.Label(files, text="TXT input").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(files, textvariable=self.source_path).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Button(files, text="Browse", command=self._browse_source).grid(row=0, column=2, padx=(8, 0), pady=4)
        ttk.Label(files, text="Excel output").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(files, textvariable=self.output_path).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(files, text="Save As", command=self._browse_output).grid(row=1, column=2, padx=(8, 0), pady=4)

        config = ttk.LabelFrame(outer, text="LLM Settings", padding=10)
        config.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        for index in range(6):
            config.columnconfigure(index, weight=1)
        ttk.Label(config, text="Provider").grid(row=0, column=0, sticky="w")
        provider_box = ttk.Combobox(
            config,
            textvariable=self.provider,
            values=["Gemini", "Groq", "NVIDIA NIM", "GitHub Models", "Mistral", "OpenAI-Compatible"],
            state="readonly",
        )
        provider_box.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(4, 8))
        provider_box.bind("<<ComboboxSelected>>", lambda _event: self._refresh_models())
        ttk.Label(config, text="Model").grid(row=0, column=1, sticky="w")
        self.model_box = ttk.Combobox(config, textvariable=self.model, state="readonly")
        self.model_box.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(4, 8))
        ttk.Label(config, text="Custom model").grid(row=0, column=2, sticky="w")
        ttk.Entry(config, textvariable=self.custom_model).grid(row=1, column=2, sticky="ew", padx=(0, 8), pady=(4, 8))
        ttk.Label(config, text="Records / request").grid(row=0, column=3, sticky="w")
        ttk.Spinbox(config, from_=1, to=500, textvariable=self.batch_size, width=8).grid(row=1, column=3, sticky="w", pady=(4, 8))
        ttk.Label(config, text="Timeout (sec)").grid(row=0, column=4, sticky="w")
        ttk.Spinbox(config, from_=30, to=1800, textvariable=self.timeout_seconds, width=8).grid(row=1, column=4, sticky="w", pady=(4, 8))
        ttk.Label(config, text="Concurrency").grid(row=0, column=5, sticky="w")
        ttk.Spinbox(config, from_=1, to=100, textvariable=self.concurrency, width=8).grid(row=1, column=5, sticky="w", pady=(4, 8))
        ttk.Label(config, text="API key").grid(row=2, column=0, sticky="w")
        ttk.Entry(config, textvariable=self.api_key, show="*").grid(row=3, column=0, sticky="ew", padx=(0, 8), pady=(4, 8))
        ttk.Label(config, text="Base URL").grid(row=2, column=1, sticky="w")
        ttk.Entry(config, textvariable=self.base_url).grid(row=3, column=1, sticky="ew", padx=(0, 8), pady=(4, 8))
        ttk.Label(config, text="Retries").grid(row=2, column=2, sticky="w")
        ttk.Spinbox(config, from_=0, to=8, textvariable=self.retries, width=8).grid(row=3, column=2, sticky="w", pady=(4, 8))
        ttk.Label(config, text="Model recommendation").grid(row=2, column=3, sticky="w")
        ttk.Label(config, textvariable=self.recommendation_text, wraplength=520, justify="left").grid(row=3, column=3, columnspan=3, sticky="w")

        prompt_frame = ttk.LabelFrame(outer, text="Prompt", padding=10)
        prompt_frame.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        prompt_frame.columnconfigure(0, weight=1)
        prompt_frame.rowconfigure(0, weight=1)
        self.prompt_box = tk.Text(prompt_frame, wrap="word", height=15, font=("Consolas", 10))
        self.prompt_box.grid(row=0, column=0, sticky="nsew")
        prompt_scroll = ttk.Scrollbar(prompt_frame, orient="vertical", command=self.prompt_box.yview)
        prompt_scroll.grid(row=0, column=1, sticky="ns")
        self.prompt_box.configure(yscrollcommand=prompt_scroll.set)
        self.prompt_box.insert("1.0", DEFAULT_PROMPT_TEMPLATE)

        runtime = ttk.LabelFrame(outer, text="Runtime", padding=10)
        runtime.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        for index in range(4):
            runtime.columnconfigure(index, weight=1)
        ttk.Label(runtime, textvariable=self.status_text).grid(row=0, column=0, sticky="w")
        ttk.Label(runtime, textvariable=self.progress_text).grid(row=0, column=1, sticky="w")
        ttk.Label(runtime, textvariable=self.rows_text).grid(row=0, column=2, sticky="w")
        ttk.Label(runtime, textvariable=self.token_text).grid(row=0, column=3, sticky="w")
        ttk.Label(runtime, textvariable=self.checkpoint_text).grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Label(runtime, textvariable=self.success_text).grid(row=1, column=2, sticky="w", pady=(6, 0))
        ttk.Label(runtime, textvariable=self.failure_text).grid(row=1, column=3, sticky="w", pady=(6, 0))
        self.progressbar = ttk.Progressbar(
            runtime,
            orient="horizontal",
            mode="determinate",
            maximum=100.0,
            variable=self.progress_value,
        )
        self.progressbar.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(10, 0))

        actions = ttk.Frame(outer)
        actions.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        self.run_button = ttk.Button(actions, text="Start", command=lambda: self._start_run(False))
        self.run_button.pack(side="left")
        self.continue_button = ttk.Button(actions, text="Continue", command=lambda: self._start_run(True))
        self.continue_button.pack(side="left", padx=(8, 0))
        self.population_rescue_button = ttk.Button(actions, text="Population Rescue", command=self._start_population_rescue)
        self.population_rescue_button.pack(side="left", padx=(8, 0))
        self.stop_button = ttk.Button(actions, text="Stop", command=self._request_stop, state="disabled")
        self.stop_button.pack(side="left", padx=(8, 0))

        log_frame = ttk.LabelFrame(outer, text="Log", padding=10)
        log_frame.grid(row=5, column=0, sticky="nsew", pady=(10, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_box = ScrolledText(log_frame, wrap="word", height=18, font=("Consolas", 10))
        self.log_box.grid(row=0, column=0, sticky="nsew")
        self.log_box.configure(state="disabled")

    def _on_page_frame_configure(self, _event=None) -> None:
        if not self.ui_alive or not hasattr(self, "page_canvas"):
            return
        try:
            self.page_canvas.configure(scrollregion=self.page_canvas.bbox("all"))
        except Exception:
            pass

    def _on_page_canvas_configure(self, event) -> None:
        if not self.ui_alive or not hasattr(self, "page_canvas_window"):
            return
        try:
            self.page_canvas.itemconfigure(self.page_canvas_window, width=event.width)
        except Exception:
            pass

    @staticmethod
    def _widget_blocks_page_scroll(widget) -> bool:
        blocked_classes = {
            "Text",
            "Treeview",
            "TCombobox",
            "Combobox",
            "Spinbox",
            "TSpinbox",
            "Scrollbar",
        }
        current = widget
        while current is not None:
            try:
                if current.winfo_class() in blocked_classes:
                    return True
                parent_name = current.winfo_parent()
                if not parent_name:
                    break
                current = current._nametowidget(parent_name)
            except Exception:
                break
        return False

    def _on_global_mousewheel(self, event) -> None:
        if not self.ui_alive or not hasattr(self, "page_canvas"):
            return
        if self._widget_blocks_page_scroll(getattr(event, "widget", None)):
            return
        delta_units = 0
        if getattr(event, "delta", 0):
            delta_units = -int(event.delta / 120) if event.delta % 120 == 0 else (-1 if event.delta > 0 else 1)
        elif getattr(event, "num", None) == 4:
            delta_units = -1
        elif getattr(event, "num", None) == 5:
            delta_units = 1
        if delta_units:
            try:
                self.page_canvas.yview_scroll(delta_units, "units")
            except Exception:
                pass

    def _load_api_keys(self) -> None:
        provider_keys, base_urls, _ = load_api_key_bundle([PROJECT_ROOT])
        self.provider_keys = provider_keys
        self.base_urls = base_urls
        self._apply_provider_key()

    def _append_log(self, message: str) -> None:
        def writer() -> None:
            self.log_box.configure(state="normal")
            self.log_box.insert("end", message.rstrip() + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

        self.root.after(0, writer)

    def _dispatch_state(self, state: Dict[str, Any]) -> None:
        def writer() -> None:
            processed = int(state.get("processed_records", 0) or 0)
            total = max(0, int(state.get("total_records", 0) or 0))
            failed = max(0, int(state.get("failed_records", 0) or 0))
            output_rows = int(state.get("output_rows", 0) or 0)
            records_with_rows = int(state.get("records_with_rows", 0) or 0)
            prompt_tokens = int(state.get("prompt_tokens", 0) or 0)
            completion_tokens = int(state.get("completion_tokens", 0) or 0)
            total_tokens = int(state.get("total_tokens", 0) or 0)
            checkpoint_path = str(state.get("checkpoint_path", "") or "-")
            self.progress_text.set(f"Records: {processed}/{total}")
            self.rows_text.set(f"Rows: {output_rows} | Row-records: {records_with_rows}")
            self.success_text.set(f"Success: {processed}")
            self.failure_text.set(f"Failed: {failed}")
            self.token_text.set(f"Tokens: {prompt_tokens} / {completion_tokens} / {total_tokens}")
            self.checkpoint_text.set(f"Checkpoint: {checkpoint_path}")
            self.progressbar.configure(maximum=max(1, total))
            self.progress_value.set(min(processed, max(1, total)))

        self.root.after(0, writer)

    def _browse_source(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose TXT input",
            initialdir=self._default_source_directory(),
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            self.source_path.set(path)
            self.output_path.set(ensure_output_prefix(path, self.output_path.get()))

    def _browse_output(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save Step2A output",
            defaultextension=".xlsx",
            filetypes=[("Excel workbook", "*.xlsx")],
            initialfile=Path(self.output_path.get()).name or "Step2A_output.xlsx",
        )
        if path:
            self.output_path.set(ensure_output_prefix(self.source_path.get(), path))

    def _refresh_models(self) -> None:
        provider = self.provider.get().strip()
        models = get_models(provider)
        self.model_box.configure(values=models)
        if models and self.model.get().strip() not in models:
            self.model.set(models[0])
        self.recommendation_text.set(recommended_summary(provider))
        self._apply_provider_key()

    def _apply_provider_key(self) -> None:
        provider = self.provider.get().strip()
        self.api_key.set(self.provider_keys.get(provider, ""))
        default_url = self._default_base_url_for_provider(provider)
        if provider == "OpenAI-Compatible":
            self.base_url.set(self.base_urls.get("openai_base_url", default_url) or default_url)
        elif provider == "NVIDIA NIM":
            self.base_url.set(self.base_urls.get("nvidia_nim_base_url", default_url) or default_url)
        elif provider == "GitHub Models":
            self.base_url.set(self.base_urls.get("github_models_base_url", default_url) or default_url)
        elif provider == "Mistral":
            self.base_url.set(self.base_urls.get("mistral_base_url", default_url) or default_url)
        else:
            self.base_url.set(default_url)

    def _selected_model(self) -> str:
        return self.custom_model.get().strip() or self.model.get().strip()

    def _request_stop(self) -> None:
        if self.is_running:
            self.stop_requested = True
            self.status_text.set("Stopping...")
            self._append_log("Stop requested. Waiting for in-flight requests.")

    def _set_running(self, running: bool) -> None:
        self.is_running = running
        self.run_button.configure(state="disabled" if running else "normal")
        self.continue_button.configure(state="disabled" if running else "normal")
        self.population_rescue_button.configure(state="disabled" if running else "normal")
        self.stop_button.configure(state="normal" if running else "disabled")
        if not running and self.status_text.get() == "Ready.":
            self.progress_value.set(0.0)

    def _start_run(self, resume_only: bool) -> None:
        if self.is_running:
            return
        source_path = self.source_path.get().strip()
        if not source_path:
            messagebox.showerror(APP_TITLE, "Please choose a TXT input file.")
            return
        if not Path(source_path).is_file():
            messagebox.showerror(APP_TITLE, "Please choose a TXT input file.")
            return
        self.output_path.set(ensure_output_prefix(source_path, self.output_path.get()))
        checkpoint_path = checkpoint_path_for_output(self.output_path.get())
        self.checkpoint_text.set(f"Checkpoint: {checkpoint_path}")
        self.stop_requested = False
        self.status_text.set("Running...")
        self.progress_value.set(0.0)
        self._set_running(True)
        threading.Thread(target=self._run_worker, args=(resume_only, checkpoint_path), daemon=True).start()

    def _start_population_rescue(self) -> None:
        if self.is_running:
            return
        output_path = self.output_path.get().strip()
        if not output_path:
            messagebox.showerror(APP_TITLE, "Please choose an Excel output file first.")
            return
        manifest_path = population_rescue_manifest_path_for_output(output_path)
        if not Path(manifest_path).exists():
            messagebox.showerror(APP_TITLE, "No pending population rescue manifest was found for this output file.")
            return
        self.stop_requested = False
        self.status_text.set("Running Population Rescue...")
        self.progress_value.set(0.0)
        self.checkpoint_text.set(f"Checkpoint: {manifest_path}")
        self._set_running(True)
        threading.Thread(target=self._run_population_rescue_worker, args=(manifest_path,), daemon=True).start()

    def _run_worker(self, resume_only: bool, checkpoint_path: str) -> None:
        try:
            if resume_only and not Path(checkpoint_path).exists():
                raise Step2AError("Continue requested, but no checkpoint file exists for this output path.")
            self._append_log(
                f"Starting {'continue' if resume_only else 'fresh'} run with model `{resolve_model_name(self._selected_model())}`."
            )
            result = process_file(
                source_path=self.source_path.get().strip(),
                output_path=self.output_path.get().strip(),
                checkpoint_path=checkpoint_path,
                provider=self.provider.get().strip(),
                model=self._selected_model(),
                api_key=self.api_key.get().strip(),
                base_url=self.base_url.get().strip(),
                batch_size=max(1, int(self.batch_size.get() or 1)),
                prompt_template=self.prompt_box.get("1.0", "end").strip(),
                timeout_seconds=max(30, int(self.timeout_seconds.get() or 30)),
                retries=max(0, int(self.retries.get() or 0)),
                concurrency=max(1, int(self.concurrency.get() or 1)),
                progress=self._append_log,
                on_state=self._dispatch_state,
                should_stop=lambda: self.stop_requested,
                resume_only=resume_only,
            )
            failed_batches = int(result.get("failed_batches", 0) or 0)
            failed_records = int(result.get("failed_records", 0) or 0)
            recovered_batches = int(result.get("recovered_failed_batches", 0) or 0)
            recovered_records = int(result.get("recovered_failed_records", 0) or 0)
            manifest_path = str(result.get("failure_manifest_path", "") or "")
            records_with_rows = int(result.get("records_with_rows", 0) or 0)
            second_pass_candidates = int(result.get("second_pass_candidate_records", 0) or 0)
            second_pass_recovered = int(result.get("second_pass_recovered_records", 0) or 0)
            confirmed_no_row = int(result.get("second_pass_confirmed_no_row_records", 0) or 0)
            remaining_unresolved = int(result.get("remaining_unresolved_records", 0) or 0)
            population_manifest = str(result.get("population_rescue_manifest_path", "") or "")
            population_candidates = int(result.get("population_rescue_candidate_records", 0) or 0)
            resolved_all_records = int(result.get("processed_records", 0) or 0) >= int(result.get("total_records", 0) or 0)
            if failed_records > 0 or remaining_unresolved > 0 or not resolved_all_records:
                self.root.after(0, lambda: self.status_text.set("Completed with gaps."))
                self._append_log(
                    f"Completed with gaps. Records resolved: {result['processed_records']}/{result['total_records']}. "
                    f"Records with rows: {records_with_rows}. Output rows: {result['output_rows']}. "
                    f"Remaining failed batches: {failed_batches} ({failed_records} records). "
                    f"Unresolved after second pass: {remaining_unresolved}."
                )
                if recovered_batches > 0:
                    self._append_log(
                        f"Replay recovered {recovered_batches} failed batches covering {recovered_records} records."
                    )
                if manifest_path:
                    self._append_log(f"Failure manifest: {manifest_path}")
                self.root.after(
                    0,
                    lambda msg=(
                        f"Run completed with remaining gaps.\n\n"
                        f"Failed batches: {failed_batches}\n"
                        f"Failed records: {failed_records}\n"
                        f"Unresolved after second pass: {remaining_unresolved}\n"
                        f"{'Failure manifest: ' + manifest_path if manifest_path else ''}"
                    ).strip(): messagebox.showwarning(APP_TITLE, msg),
                )
            else:
                self.root.after(0, lambda: self.status_text.set("Completed."))
                self._append_log(
                    f"Completed. Records resolved: {result['processed_records']}/{result['total_records']}. "
                    f"Records with rows: {records_with_rows}. Output rows: {result['output_rows']}."
                )
                if recovered_batches > 0:
                    self._append_log(
                        f"Replay recovered {recovered_batches} failed batches covering {recovered_records} records."
                    )
            if second_pass_candidates > 0:
                self._append_log(
                    f"Second-pass row recovery checked {second_pass_candidates} records absent after the main pass, "
                    f"recovered {second_pass_recovered} into workbook rows, and confirmed {confirmed_no_row} as no-row."
                )
            if population_manifest and population_candidates > 0:
                self._append_log(
                    f"Population rescue manifest: {population_manifest} "
                    f"(records={population_candidates}). Click `Population Rescue` to run the second stage."
                )
            else:
                self._append_log("Population rescue manifest was not created because no rescue candidates were detected.")
        except UserCancelledError:
            row_count, _ = rebuild_excel_from_checkpoint(checkpoint_path, self.output_path.get().strip())
            self.root.after(0, lambda: self.status_text.set(f"Stopped. Partial rows rebuilt: {row_count}."))
            self._append_log(f"Run stopped by user. Rebuilt partial workbook with {row_count} rows.")
        except Exception as exc:
            error_message = str(exc)
            row_count, _ = rebuild_excel_from_checkpoint(checkpoint_path, self.output_path.get().strip())
            self.root.after(0, lambda: self.status_text.set("Failed."))
            self._append_log(f"[ERROR] {exc}")
            self._append_log(traceback.format_exc())
            self._append_log(f"Checkpoint rebuild completed with {row_count} rows.")
            self.root.after(0, lambda msg=error_message: messagebox.showerror(APP_TITLE, msg))
        finally:
            if Path(checkpoint_path).exists():
                completed_ids, row_count, usage_count = load_checkpoint_progress(checkpoint_path)
                self._append_log(
                    f"Checkpoint status: completed_records={len(completed_ids)}, rows={row_count}, usage_entries={usage_count}."
                )
            self.root.after(0, lambda: self._set_running(False))

    def _run_population_rescue_worker(self, manifest_path: str) -> None:
        try:
            self._append_log(
                f"Starting population rescue with model `{resolve_model_name(self._selected_model())}`."
            )
            result = run_population_rescue_stage(
                manifest_path=manifest_path,
                provider=self.provider.get().strip(),
                model=self._selected_model(),
                api_key=self.api_key.get().strip(),
                base_url=self.base_url.get().strip(),
                batch_size=max(1, int(self.batch_size.get() or 1)),
                timeout_seconds=max(30, int(self.timeout_seconds.get() or 30)),
                retries=max(0, int(self.retries.get() or 0)),
                concurrency=max(1, int(self.concurrency.get() or 1)),
                progress=self._append_log,
                on_state=self._dispatch_state,
                should_stop=lambda: self.stop_requested,
            )
            self.root.after(0, lambda: self.status_text.set("Population Rescue Completed."))
            self._append_log(
                f"Population rescue completed. Records processed: {result['processed_records']}/{result['total_records']}. "
                f"Workbook rows: {result['output_rows']}."
            )
        except UserCancelledError:
            self.root.after(0, lambda: self.status_text.set("Population Rescue Stopped."))
            self._append_log("Population rescue stopped by user request.")
        except Exception as exc:
            error_message = str(exc)
            self.root.after(0, lambda: self.status_text.set("Population Rescue Failed."))
            self._append_log(f"[ERROR] {exc}")
            self._append_log(traceback.format_exc())
            self.root.after(0, lambda msg=error_message: messagebox.showerror(APP_TITLE, msg))
        finally:
            self.root.after(0, lambda: self._set_running(False))

    def _on_close(self) -> None:
        if self.is_running:
            if not messagebox.askyesno(APP_TITLE, "A run is still active. Request stop and close the window?"):
                return
            self.stop_requested = True
        self.ui_alive = False
        self.root.destroy()

    @staticmethod
    def _default_source_directory() -> str:
        source_path = Path(default_source_path())
        if source_path.is_dir():
            return str(source_path)
        if source_path.parent.is_dir():
            return str(source_path.parent)
        return str(Path(__file__).resolve().parents[2] / "pipeline_output" / "Step1")


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
