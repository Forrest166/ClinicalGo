import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from common.paths import data_path, ensure_standard_dirs


DEFAULT_INPUT = str(data_path("clinical_extraction_output.xlsx"))
DEFAULT_OUTPUT = str(data_path("clinical_frequency_summary.xlsx"))
PLOT_FILE = "sample_size_ranked_curve.png"


def normalize_column_name(name: str) -> str:
    """Normalize column names for robust matching."""
    text = str(name).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def resolve_columns(df: pd.DataFrame) -> dict:
    """Resolve required columns by exact/normalized matching."""
    normalized_to_raw = {normalize_column_name(c): c for c in df.columns}

    target_aliases = {
        "journal": ["journal"],
        "indication": ["indication"],
        "intervention_type": ["interventiontype", "intervention"],
        "outcome": ["outcomedirection", "outcome", "outcomes"],
        "sample_size": ["samplesize", "sample"],
    }

    resolved = {}
    missing = []

    for key, aliases in target_aliases.items():
        found = None
        for alias in aliases:
            if alias in normalized_to_raw:
                found = normalized_to_raw[alias]
                break
        if found is None:
            missing.append(key)
        else:
            resolved[key] = found

    if missing:
        raise ValueError(
            "缺少必要列：" + ", ".join(missing) + "。\n"
            "请确认表头中包含 Journal / indication / Intervention Type / outcome / sample size。"
        )

    return resolved


def frequency_table(series: pd.Series, column_name: str) -> pd.DataFrame:
    clean = series.fillna("(Missing)").astype(str).str.strip()
    clean = clean.replace("", "(Missing)")
    freq = clean.value_counts(dropna=False)
    out = freq.rename_axis(column_name).reset_index(name="Frequency")
    out["Percentage"] = out["Frequency"] / out["Frequency"].sum()
    return out


def parse_sample_size(series: pd.Series) -> pd.Series:
    def extract_numeric(value) -> float:
        if pd.isna(value):
            return np.nan

        text = str(value).strip()
        if not text:
            return np.nan

        # Normalize comma-separated numbers first (e.g., "12,345").
        normalized = re.sub(r"(?<=\d),(?=\d)", "", text)
        matches = re.findall(r"-?\d+(?:\.\d+)?", normalized)
        if not matches:
            return np.nan

        # Use the first detected numeric token; avoid concatenating multiple values.
        try:
            return float(matches[0])
        except ValueError:
            return np.nan

    values = series.apply(extract_numeric)
    values = pd.to_numeric(values, errors="coerce").dropna()
    values = values[values >= 0]
    return values


def make_smooth_distribution_plot(sample_sizes: pd.Series, output_dir: str) -> str:
    if sample_sizes.empty:
        return ""

    plot_path = os.path.join(output_dir, PLOT_FILE)
    bin_start = 0
    bin_end = 3000
    bin_step = 30
    bin_edges = np.arange(bin_start, bin_end + bin_step, bin_step)

    in_range = sample_sizes[(sample_sizes >= bin_start) & (sample_sizes <= bin_end)]
    counts, _ = np.histogram(in_range, bins=bin_edges)
    x_left = bin_edges[:-1]

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(x_left, counts, width=bin_step * 0.9, align="edge", color="#4C78A8", alpha=0.85, edgecolor="white")
    ax.set_title("Sample Size Interval Counts (0-3000, step=30)")
    ax.set_xlabel("Sample Size Interval Start")
    ax.set_ylabel("Count")
    ax.set_xlim(bin_start, bin_end)
    ax.set_xticks(np.arange(bin_start, bin_end + 1, 300))
    ax.grid(axis="y", alpha=0.25)

    fig.tight_layout()
    fig.savefig(plot_path, dpi=220)
    plt.close(fig)

    return plot_path


def build_sample_size_tables(sample_sizes: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame]:
    n = len(sample_sizes)
    if n == 0:
        threshold_df = pd.DataFrame(columns=["Threshold", "Count", "Percentage"])
        summary_df = pd.DataFrame(columns=["Metric", "Value"])
        return threshold_df, summary_df

    thresholds = [50, 200, 500, 2000]
    threshold_rows = []
    for t in thresholds:
        count = int((sample_sizes <= t).sum())
        threshold_rows.append(
            {
                "Threshold": f"<= {t}",
                "Count": count,
                "Percentage": count / n,
            }
        )

    interval_rows = [
        {"Threshold": "0-50", "Count": int(((sample_sizes >= 0) & (sample_sizes <= 50)).sum())},
        {"Threshold": "51-200", "Count": int(((sample_sizes > 50) & (sample_sizes <= 200)).sum())},
        {"Threshold": "201-500", "Count": int(((sample_sizes > 200) & (sample_sizes <= 500)).sum())},
        {"Threshold": "501-2000", "Count": int(((sample_sizes > 500) & (sample_sizes <= 2000)).sum())},
        {"Threshold": "> 2000", "Count": int((sample_sizes > 2000).sum())},
    ]
    for row in interval_rows:
        row["Percentage"] = row["Count"] / n

    threshold_df = pd.DataFrame(threshold_rows + interval_rows)

    summary_df = pd.DataFrame(
        [
            {"Metric": "Valid sample size count", "Value": int(n)},
            {"Metric": "Mean", "Value": sample_sizes.mean()},
            {"Metric": "Median", "Value": sample_sizes.median()},
            {"Metric": "Std", "Value": sample_sizes.std(ddof=1) if n > 1 else 0},
            {"Metric": "Min", "Value": sample_sizes.min()},
            {"Metric": "Max", "Value": sample_sizes.max()},
        ]
    )

    return threshold_df, summary_df


def analyze_file(input_path: str, output_path: str) -> tuple[str, str]:
    header_df = pd.read_excel(input_path, nrows=0)
    cols = resolve_columns(header_df)
    selected_cols = list(dict.fromkeys(cols.values()))
    df = pd.read_excel(input_path, usecols=selected_cols)

    journal_freq = frequency_table(df[cols["journal"]], "Journal")
    indication_freq = frequency_table(df[cols["indication"]], "Indication")
    intervention_type_freq = frequency_table(df[cols["intervention_type"]], "Intervention Type")
    outcome_freq = frequency_table(df[cols["outcome"]], "Outcome")

    sample_sizes = parse_sample_size(df[cols["sample_size"]])
    threshold_df, sample_summary = build_sample_size_tables(sample_sizes)
    plot_path = make_smooth_distribution_plot(sample_sizes, os.path.dirname(output_path) or ".")

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        journal_freq.to_excel(writer, sheet_name="Journal_Frequency", index=False)
        indication_freq.to_excel(writer, sheet_name="Indication_Frequency", index=False)
        intervention_type_freq.to_excel(writer, sheet_name="InterventionType_Frequency", index=False)
        outcome_freq.to_excel(writer, sheet_name="Outcome_Frequency", index=False)
        threshold_df.to_excel(writer, sheet_name="SampleSize_Thresholds", index=False)
        sample_summary.to_excel(writer, sheet_name="SampleSize_Summary", index=False)

    return output_path, plot_path


class AnalyzerGUI:
    def __init__(self, root: tk.Tk):
        ensure_standard_dirs()
        self.root = root
        self.root.title("Clinical Extraction Frequency Analyzer")
        self.root.geometry("740x240")

        self.input_var = tk.StringVar(value=self.get_default_input_path())
        self.output_var = tk.StringVar(value=self.get_default_output_path())

        self.build_ui()

    def get_default_input_path(self) -> str:
        default_path = os.path.abspath(DEFAULT_INPUT)
        return default_path if os.path.exists(default_path) else ""

    def get_default_output_path(self) -> str:
        return os.path.abspath(DEFAULT_OUTPUT)

    def build_ui(self):
        pad_x = 12

        tk.Label(self.root, text="Input Excel:", anchor="w").pack(fill="x", padx=pad_x, pady=(15, 4))

        input_frame = tk.Frame(self.root)
        input_frame.pack(fill="x", padx=pad_x)
        tk.Entry(input_frame, textvariable=self.input_var).pack(side="left", fill="x", expand=True)
        tk.Button(input_frame, text="Browse", command=self.pick_input).pack(side="left", padx=(8, 0))

        tk.Label(self.root, text="Output Excel:", anchor="w").pack(fill="x", padx=pad_x, pady=(12, 4))

        output_frame = tk.Frame(self.root)
        output_frame.pack(fill="x", padx=pad_x)
        tk.Entry(output_frame, textvariable=self.output_var).pack(side="left", fill="x", expand=True)
        tk.Button(output_frame, text="Browse", command=self.pick_output).pack(side="left", padx=(8, 0))

        tip_text = (
            "默认会识别当前工作目录下的 clinical_extraction_output.xlsx；\n"
            "输出结果包括：4类频次统计、sample size阈值占比，以及sample size分布曲线图(PNG)。"
        )
        tk.Label(self.root, text=tip_text, fg="#444", justify="left").pack(fill="x", padx=pad_x, pady=(14, 10))

        self.run_btn = tk.Button(self.root, text="Start Analysis", height=2, command=self.run_analysis)
        self.run_btn.pack(fill="x", padx=pad_x, pady=(0, 12))

    def pick_input(self):
        path = filedialog.askopenfilename(
            title="Select input Excel file",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")],
        )
        if path:
            self.input_var.set(path)

    def pick_output(self):
        path = filedialog.asksaveasfilename(
            title="Save output Excel file",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
        )
        if path:
            self.output_var.set(path)

    def run_analysis(self):
        input_path = self.input_var.get().strip()
        output_path = self.output_var.get().strip()

        if not input_path:
            messagebox.showerror("Error", "请选择输入文件。")
            return
        if not os.path.exists(input_path):
            messagebox.showerror("Error", f"输入文件不存在：\n{input_path}")
            return
        if not output_path:
            messagebox.showerror("Error", "请选择输出文件路径。")
            return

        self.run_btn.config(state="disabled", text="Analyzing...")
        self.root.update_idletasks()

        try:
            out_excel, out_plot = analyze_file(input_path, output_path)
            msg = f"分析完成！\n\nExcel输出：\n{out_excel}"
            if out_plot:
                msg += f"\n\n曲线图输出：\n{out_plot}"
            else:
                msg += "\n\n未生成曲线图（sample size列无有效数值）。"
            messagebox.showinfo("Success", msg)
        except Exception as e:
            messagebox.showerror("Error", f"分析失败：\n{e}")
        finally:
            self.run_btn.config(state="normal", text="Start Analysis")


def main():
    root = tk.Tk()
    app = AnalyzerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
