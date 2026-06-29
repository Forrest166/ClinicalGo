from __future__ import annotations

import html
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer


DISEASE_RULES: list[tuple[str, str]] = [
    ("Treatment-resistant depression", r"treatment-resistant|\btrd\b"),
    ("Peripartum/postpartum depression", r"peripartum|postpartum|postnatal|perinatal"),
    ("Bipolar depression", r"bipolar"),
    ("MDD", r"\bmajor depressive disorder\b|\bmdd\b|unipolar depressive disorder"),
    ("Depression generic", r"\bdepression\b|\bdepressive symptoms?\b|depressive disorder"),
    ("Anxiety/comorbid anxiety", r"anxiety"),
    ("PTSD/trauma", r"post-traumatic|posttraumatic|\bptsd\b|trauma"),
    ("Cancer-related", r"cancer|oncology|tumou?r|chemotherapy"),
    ("Pain/fibromyalgia", r"fibromyalgia|chronic pain|\bpain\b"),
    ("Sleep/insomnia", r"insomnia|\bsleep\b"),
    ("Neurocognitive/neurodegenerative", r"dementia|parkinson|alzheimer|cognitive"),
    ("Metabolic/cardiopulmonary", r"diabetes|obesity|copd|cardiac|heart|cardiovascular"),
    ("HIV/infectious", r"\bhiv\b|aids|infectious"),
    ("Psychosis/schizophrenia", r"schizophrenia|psychosis"),
    ("Substance use", r"substance|alcohol|methamphetamine|opioid|cocaine|smoking"),
]

OUTCOME_ORDER = ["Positive", "Neutral", "Mixed or Unknown", "Negative"]
POPULATION_FIELDS = ["Age", "Gender", "Ethnicity", "Occupation", "Social Status", "Treatment History"]
PLOT_DPI = 170


@dataclass
class AnalysisResult:
    output_dir: Path
    report_path: Path
    summary_path: Path
    dataset_path: Path
    cluster_path: Path
    figures: Dict[str, Path]
    metrics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "output_dir": str(self.output_dir.resolve()),
            "report_path": str(self.report_path.resolve()),
            "summary_path": str(self.summary_path.resolve()),
            "dataset_path": str(self.dataset_path.resolve()),
            "cluster_path": str(self.cluster_path.resolve()),
            "figures": {key: str(path.resolve()) for key, path in self.figures.items()},
            "metrics": self.metrics,
        }


def clean_text(value: Any) -> str:
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return " ".join(str(value or "").strip().split())


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")
    return cleaned or "file"


def read_table(path: str | Path) -> pd.DataFrame:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(str(source))
    if source.suffix.lower() in {".csv", ".tsv"}:
        sep = "\t" if source.suffix.lower() == ".tsv" else ","
        df = pd.read_csv(source, sep=sep)
    else:
        df = pd.read_excel(source, sheet_name=0, engine="openpyxl")
    df.columns = [clean_text(column) for column in df.columns]
    for column in df.columns:
        if df[column].dtype == object:
            df[column] = df[column].map(clean_text)
    df["Source File"] = source.name
    return df


def load_inputs(input_paths: Sequence[str | Path]) -> pd.DataFrame:
    frames = [read_table(path) for path in input_paths]
    if not frames:
        raise ValueError("At least one input file is required.")
    return pd.concat(frames, ignore_index=True, sort=False)


def find_column(df: pd.DataFrame, exact: str, startswith: str | None = None) -> str | None:
    if exact in df.columns:
        return exact
    if startswith:
        for column in df.columns:
            if column.startswith(startswith):
                return column
    return None


def to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace(",", "", regex=False), errors="coerce")


def parse_vector_nonzero(value: Any) -> bool:
    text = clean_text(value)
    if not text.startswith("[") or not text.endswith("]"):
        return False
    numbers = []
    for part in text.strip("[]").split(","):
        try:
            numbers.append(float(part.strip()))
        except Exception:
            numbers.append(0.0)
    return any(abs(number) > 1e-12 for number in numbers)


def disease_subtypes(indication: Any) -> list[str]:
    text = clean_text(indication).lower()
    if not text:
        return ["Unclassified"]
    hits = [label for label, pattern in DISEASE_RULES if re.search(pattern, text, flags=re.I)]
    return hits or ["Unclassified"]


def primary_disease(indication: Any) -> str:
    return disease_subtypes(indication)[0]


def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    prepared = df.copy()
    for column in [
        "Indication",
        "Intervention",
        "Intervention Type",
        "Comparator",
        "Outcome Direction",
        "Severity",
        "Occupation",
        "Social Status",
        "Treatment History",
    ]:
        if column not in prepared.columns:
            prepared[column] = ""
        prepared[column] = prepared[column].map(clean_text)

    if "Sample Size" not in prepared.columns:
        prepared["Sample Size"] = ""
    follow_col = find_column(prepared, "Follow-up Time (Months)") or find_column(prepared, "Follow-up Months")
    if follow_col is None:
        prepared["Follow-up Time (Months)"] = ""
        follow_col = "Follow-up Time (Months)"

    age_col = find_column(prepared, "Age [Mean_Age,SD_Age,Min_Age,Max_Age,N]", startswith="Age [")
    if age_col is None:
        prepared["Age [Mean_Age,SD_Age,Min_Age,Max_Age,N]"] = ""
        age_col = "Age [Mean_Age,SD_Age,Min_Age,Max_Age,N]"
    ethnicity_col = find_column(prepared, "Ethnicity Vector", startswith="Ethnicity [")
    if ethnicity_col is None:
        prepared["Ethnicity [A,B,C,D,E,F]"] = ""
        ethnicity_col = "Ethnicity [A,B,C,D,E,F]"

    prepared["Sample Size Numeric"] = to_numeric(prepared["Sample Size"])
    prepared["Follow-up Months Numeric"] = to_numeric(prepared[follow_col])
    prepared["Disease Subtypes"] = prepared["Indication"].map(disease_subtypes)
    prepared["Primary Disease Subtype"] = prepared["Indication"].map(primary_disease)
    prepared["Intervention Text"] = (
        prepared["Intervention"].fillna("").map(clean_text)
        + " "
        + prepared["Comparator"].fillna("").map(clean_text)
    ).str.strip()
    prepared["Has Age"] = prepared[age_col].map(parse_vector_nonzero)
    prepared["Has Gender"] = prepared.get("Gender Male Proportion", pd.Series("", index=prepared.index)).map(clean_text).astype(bool)
    prepared["Has Ethnicity"] = prepared[ethnicity_col].map(parse_vector_nonzero)
    prepared["Has Occupation"] = prepared["Occupation"].map(clean_text).astype(bool)
    prepared["Has Social Status"] = prepared["Social Status"].map(clean_text).astype(bool)
    prepared["Has Treatment History"] = prepared["Treatment History"].map(clean_text).astype(bool)
    prepared["Severity Is Mapped"] = prepared["Severity"].map(lambda value: bool(re.fullmatch(r"\d|\[\d(?:,\d)*\]", clean_text(value))))
    return prepared


def explode_disease(df: pd.DataFrame) -> pd.DataFrame:
    return df.explode("Disease Subtypes").rename(columns={"Disease Subtypes": "Disease Subtype"})


def save_figure(fig: plt.Figure, output_dir: Path, name: str) -> Path:
    path = output_dir / f"{name}.png"
    fig.tight_layout()
    fig.savefig(path, dpi=PLOT_DPI, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_disease_intervention_heatmap(df: pd.DataFrame, output_dir: Path) -> Path:
    exploded = explode_disease(df)
    table = pd.crosstab(exploded["Disease Subtype"], exploded["Intervention Type"])
    if "Unclassified" in table.index and len(table.index) > 1:
        table = table.drop(index="Unclassified")
    table = table.loc[table.sum(axis=1).sort_values(ascending=False).index]
    table = table[table.sum(axis=0).sort_values(ascending=False).index]
    fig, ax = plt.subplots(figsize=(13, max(6, 0.42 * len(table.index))))
    sns.heatmap(table, cmap="YlGnBu", linewidths=0.4, linecolor="#f0f0f0", ax=ax)
    ax.set_title("Disease Subtype x Intervention Type")
    ax.set_xlabel("Intervention Type")
    ax.set_ylabel("Disease Subtype")
    return save_figure(fig, output_dir, "01_disease_intervention_heatmap")


def plot_intervention_outcome_stacked(df: pd.DataFrame, output_dir: Path) -> Path:
    table = pd.crosstab(df["Intervention Type"], df["Outcome Direction"])
    table = table.reindex(columns=[col for col in OUTCOME_ORDER if col in table.columns] + [col for col in table.columns if col not in OUTCOME_ORDER])
    table = table.loc[table.sum(axis=1).sort_values(ascending=False).index]
    fig, ax = plt.subplots(figsize=(12, 7))
    colors = ["#3f7f5f", "#d0a33f", "#8a8f9e", "#bf5b5b", "#6a9fb5"]
    table.plot(kind="bar", stacked=True, ax=ax, color=colors[: len(table.columns)], width=0.82)
    ax.set_title("Intervention Type x Outcome Direction")
    ax.set_xlabel("Intervention Type")
    ax.set_ylabel("Study rows")
    ax.legend(title="Outcome", bbox_to_anchor=(1.02, 1), loc="upper left")
    ax.tick_params(axis="x", rotation=35)
    return save_figure(fig, output_dir, "02_intervention_outcome_stacked_bar")


def plot_bipartite_network(df: pd.DataFrame, output_dir: Path, min_edge: int) -> Path:
    exploded = explode_disease(df)
    edge_counts = (
        exploded.groupby(["Disease Subtype", "Intervention Type"], dropna=False)
        .size()
        .reset_index(name="count")
        .query("`Disease Subtype` != 'Unclassified' and `Intervention Type` != ''")
    )
    edge_counts = edge_counts[edge_counts["count"] >= int(min_edge)]
    if edge_counts.empty:
        edge_counts = (
            exploded.groupby(["Disease Subtype", "Intervention Type"], dropna=False)
            .size()
            .reset_index(name="count")
            .query("`Disease Subtype` != 'Unclassified' and `Intervention Type` != ''")
            .sort_values("count", ascending=False)
            .head(40)
        )

    graph = nx.Graph()
    disease_nodes = sorted(edge_counts["Disease Subtype"].unique())
    intervention_nodes = sorted(edge_counts["Intervention Type"].unique())
    graph.add_nodes_from(disease_nodes, bipartite=0)
    graph.add_nodes_from(intervention_nodes, bipartite=1)
    for row in edge_counts.itertuples(index=False):
        graph.add_edge(row[0], row[1], weight=int(row[2]))

    pos: dict[str, tuple[float, float]] = {}
    for index, node in enumerate(disease_nodes):
        pos[node] = (0, -index)
    for index, node in enumerate(intervention_nodes):
        pos[node] = (1, -index * max(1, len(disease_nodes) / max(1, len(intervention_nodes))))

    weighted_degree = dict(graph.degree(weight="weight"))
    node_sizes = [180 + 8 * math.sqrt(weighted_degree.get(node, 1)) for node in graph.nodes]
    node_colors = ["#4f7d95" if node in disease_nodes else "#a86f3f" for node in graph.nodes]
    edge_widths = [0.4 + math.log1p(graph.edges[edge]["weight"]) * 0.55 for edge in graph.edges]

    fig, ax = plt.subplots(figsize=(14, max(8, 0.55 * max(len(disease_nodes), len(intervention_nodes)))))
    nx.draw_networkx_edges(graph, pos, ax=ax, width=edge_widths, alpha=0.38, edge_color="#777777")
    nx.draw_networkx_nodes(graph, pos, ax=ax, node_size=node_sizes, node_color=node_colors, alpha=0.92)
    nx.draw_networkx_labels(graph, pos, ax=ax, font_size=9)
    ax.set_title(f"Disease-Intervention Bipartite Network (edge >= {min_edge})")
    ax.axis("off")
    return save_figure(fig, output_dir, "03_disease_intervention_bipartite_network")


def intervention_cluster(df: pd.DataFrame, output_dir: Path, cluster_count: int) -> tuple[Path, pd.DataFrame, list[dict[str, Any]]]:
    subset = df[df["Intervention Text"].map(clean_text).astype(bool)].copy()
    if subset.empty:
        empty = output_dir / "intervention_cluster_assignments.csv"
        pd.DataFrame().to_csv(empty, index=False)
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.text(0.5, 0.5, "No intervention text available", ha="center", va="center")
        ax.axis("off")
        return save_figure(fig, output_dir, "04_intervention_text_clusters"), pd.DataFrame(), []

    stop_words = sorted(set(ENGLISH_STOP_WORDS) | {"study", "trial", "group", "patients", "participants", "treatment"})
    vectorizer = TfidfVectorizer(max_features=2500, min_df=3, ngram_range=(1, 2), stop_words=stop_words)
    matrix = vectorizer.fit_transform(subset["Intervention Text"])
    n_samples, n_features = matrix.shape
    k = max(2, min(int(cluster_count), n_samples, 14))
    reduced_dims = max(2, min(50, n_features - 1, n_samples - 1))
    svd = TruncatedSVD(n_components=reduced_dims, random_state=42)
    reduced = svd.fit_transform(matrix)
    labels = KMeans(n_clusters=k, random_state=42, n_init=20).fit_predict(reduced)
    coords = reduced[:, :2] if reduced.shape[1] >= 2 else np.column_stack([reduced[:, 0], np.zeros(len(reduced))])

    terms = np.array(vectorizer.get_feature_names_out())
    cluster_rows: list[dict[str, Any]] = []
    for cluster_id in range(k):
        member_mask = labels == cluster_id
        cluster_matrix = matrix[member_mask]
        mean_weights = np.asarray(cluster_matrix.mean(axis=0)).ravel()
        top_terms = terms[np.argsort(mean_weights)[-10:][::-1]]
        cluster_rows.append(
            {
                "cluster": int(cluster_id),
                "row_count": int(member_mask.sum()),
                "top_terms": ", ".join(top_terms),
            }
        )

    assignments = subset[["Source File", "Record ID", "Indication", "Intervention", "Comparator", "Intervention Type", "Outcome Direction"]].copy()
    assignments["Intervention Cluster"] = labels
    assignments["Cluster X"] = coords[:, 0]
    assignments["Cluster Y"] = coords[:, 1]
    cluster_path = output_dir / "intervention_cluster_assignments.csv"
    assignments.to_csv(cluster_path, index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(11, 8))
    palette = sns.color_palette("tab10", n_colors=k)
    for cluster_id in range(k):
        mask = labels == cluster_id
        ax.scatter(coords[mask, 0], coords[mask, 1], s=14, alpha=0.42, color=palette[cluster_id], label=f"C{cluster_id}")
        centroid = coords[mask].mean(axis=0)
        ax.text(centroid[0], centroid[1], f"C{cluster_id}", fontsize=11, weight="bold", ha="center", va="center")
    ax.set_title("Intervention Text Clusters (TF-IDF + SVD + KMeans)")
    ax.set_xlabel("SVD component 1")
    ax.set_ylabel("SVD component 2")
    ax.legend(title="Cluster", ncol=2, fontsize=8)
    figure_path = save_figure(fig, output_dir, "04_intervention_text_clusters")
    return figure_path, assignments, cluster_rows


def plot_sample_size(df: pd.DataFrame, output_dir: Path) -> Path:
    values = df["Sample Size Numeric"].dropna()
    values = values[values > 0]
    fig, ax = plt.subplots(figsize=(11, 6))
    if values.empty:
        ax.text(0.5, 0.5, "No sample size values available", ha="center", va="center")
        ax.axis("off")
    else:
        bins = np.logspace(np.log10(max(1, values.min())), np.log10(values.max()), 45)
        ax.hist(values, bins=bins, color="#4f7d95", alpha=0.86)
        ax.set_xscale("log")
        ax.axvline(values.median(), color="#bf5b5b", linestyle="--", linewidth=2, label=f"Median {values.median():.0f}")
        ax.set_title("Sample Size Distribution (log scale)")
        ax.set_xlabel("Sample size")
        ax.set_ylabel("Study rows")
        ax.legend()
    return save_figure(fig, output_dir, "05_sample_size_log_distribution")


def plot_follow_up(df: pd.DataFrame, output_dir: Path) -> Path:
    values = df["Follow-up Months Numeric"].dropna()
    values = values[values > 0]
    fig, ax = plt.subplots(figsize=(11, 6))
    if values.empty:
        ax.text(0.5, 0.5, "No follow-up values available", ha="center", va="center")
        ax.axis("off")
    else:
        p99 = values.quantile(0.99)
        clipped = values[values <= p99]
        ax.hist(clipped, bins=40, color="#7a9d58", alpha=0.86)
        ax.axvline(values.median(), color="#bf5b5b", linestyle="--", linewidth=2, label=f"Median {values.median():.2f} months")
        ax.axvline(values.quantile(0.75), color="#6f6f6f", linestyle=":", linewidth=2, label=f"Q3 {values.quantile(0.75):.2f} months")
        ax.set_title(f"Follow-up Time Distribution (values <= p99={p99:.2f} months)")
        ax.set_xlabel("Follow-up time (months)")
        ax.set_ylabel("Study rows")
        ax.legend()
    return save_figure(fig, output_dir, "06_follow_up_distribution")


def severity_digits(value: str) -> list[int]:
    text = clean_text(value)
    if re.fullmatch(r"\d", text):
        return [int(text)]
    if re.fullmatch(r"\[\d(?:,\d)*\]", text):
        return [int(part) for part in text.strip("[]").split(",")]
    return []


def plot_severity(df: pd.DataFrame, output_dir: Path) -> Path:
    severity = df[df["Severity"].map(clean_text).astype(bool)].copy()
    mapped_count = int(severity["Severity Is Mapped"].sum())
    retained_count = int(len(severity) - mapped_count)
    code_counts = {1: 0, 2: 0, 3: 0}
    for value in severity["Severity"]:
        for digit in severity_digits(value):
            if digit in code_counts:
                code_counts[digit] += 1

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].bar(["Mapped", "Retained text"], [mapped_count, retained_count], color=["#4f7d95", "#d0a33f"])
    axes[0].set_title("Severity Mapping Coverage")
    axes[0].set_ylabel("Study rows")
    axes[1].bar(["Mild (1)", "Moderate (2)", "Severe (3)"], [code_counts[1], code_counts[2], code_counts[3]], color=["#7a9d58", "#d0a33f", "#bf5b5b"])
    axes[1].set_title("Mapped Severity Code Mentions")
    axes[1].set_ylabel("Code mentions")
    return save_figure(fig, output_dir, "07_severity_distribution")


def plot_population_coverage(df: pd.DataFrame, output_dir: Path) -> Path:
    coverage = {
        "Age": int(df["Has Age"].sum()),
        "Gender": int(df["Has Gender"].sum()),
        "Ethnicity": int(df["Has Ethnicity"].sum()),
        "Occupation": int(df["Has Occupation"].sum()),
        "Social Status": int(df["Has Social Status"].sum()),
        "Treatment History": int(df["Has Treatment History"].sum()),
    }
    labels = list(coverage.keys())
    values = np.array([coverage[label] for label in labels])
    pct = values / max(1, len(df)) * 100
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.bar(labels, pct, color="#6a8caf")
    for index, value in enumerate(pct):
        ax.text(index, value + 1, f"{value:.1f}%", ha="center", va="bottom", fontsize=9)
    ax.set_ylim(0, max(12, min(100, pct.max() + 10)))
    ax.set_title("Population Feature Availability")
    ax.set_ylabel("Rows with available feature (%)")
    ax.tick_params(axis="x", rotation=25)
    return save_figure(fig, output_dir, "08_population_coverage_missingness")


def write_summary_tables(df: pd.DataFrame, output_dir: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    exploded = explode_disease(df)
    tables = {
        "disease_intervention_counts.csv": pd.crosstab(exploded["Disease Subtype"], exploded["Intervention Type"]),
        "intervention_outcome_counts.csv": pd.crosstab(df["Intervention Type"], df["Outcome Direction"]),
        "disease_counts.csv": exploded["Disease Subtype"].value_counts().rename_axis("Disease Subtype").reset_index(name="count"),
        "intervention_type_counts.csv": df["Intervention Type"].value_counts().rename_axis("Intervention Type").reset_index(name="count"),
    }
    for filename, table in tables.items():
        path = output_dir / filename
        table.to_csv(path, encoding="utf-8-sig")
        paths[filename] = path
    return paths


def compute_metrics(df: pd.DataFrame, cluster_rows: list[dict[str, Any]]) -> Dict[str, Any]:
    sample = df["Sample Size Numeric"].dropna()
    follow = df["Follow-up Months Numeric"].dropna()
    metrics: Dict[str, Any] = {
        "row_count": int(len(df)),
        "source_files": sorted(df["Source File"].dropna().unique().tolist()),
        "non_empty_indication": int(df["Indication"].map(clean_text).astype(bool).sum()),
        "non_empty_intervention": int(df["Intervention"].map(clean_text).astype(bool).sum()),
        "non_empty_comparator": int(df["Comparator"].map(clean_text).astype(bool).sum()) if "Comparator" in df else 0,
        "non_empty_severity": int(df["Severity"].map(clean_text).astype(bool).sum()),
        "sample_size_median": float(sample.median()) if not sample.empty else None,
        "sample_size_max": float(sample.max()) if not sample.empty else None,
        "follow_up_median_months": float(follow.median()) if not follow.empty else None,
        "follow_up_q3_months": float(follow.quantile(0.75)) if not follow.empty else None,
        "follow_up_max_months": float(follow.max()) if not follow.empty else None,
        "severity_mapped_rows": int(df["Severity Is Mapped"].sum()),
        "severity_retained_text_rows": int((df["Severity"].map(clean_text).astype(bool) & ~df["Severity Is Mapped"]).sum()),
        "population_coverage": {
            "age": int(df["Has Age"].sum()),
            "gender": int(df["Has Gender"].sum()),
            "ethnicity": int(df["Has Ethnicity"].sum()),
            "occupation": int(df["Has Occupation"].sum()),
            "social_status": int(df["Has Social Status"].sum()),
            "treatment_history": int(df["Has Treatment History"].sum()),
        },
        "intervention_clusters": cluster_rows,
    }
    return metrics


def html_img(path: Path, output_dir: Path, title: str) -> str:
    rel = path.relative_to(output_dir).as_posix()
    return f'<section><h2>{html.escape(title)}</h2><img src="{html.escape(rel)}" alt="{html.escape(title)}"></section>'


def write_html_report(output_dir: Path, figures: Dict[str, Path], metrics: Dict[str, Any], cluster_rows: list[dict[str, Any]]) -> Path:
    report_path = output_dir / "Step3_analysis_report.html"
    source_files = ", ".join(html.escape(name) for name in metrics.get("source_files", []))
    cards = [
        ("Rows", metrics.get("row_count")),
        ("Sample median", metrics.get("sample_size_median")),
        ("Sample max", metrics.get("sample_size_max")),
        ("Follow-up median", metrics.get("follow_up_median_months")),
        ("Follow-up Q3", metrics.get("follow_up_q3_months")),
        ("Severity mapped", metrics.get("severity_mapped_rows")),
        ("Severity retained", metrics.get("severity_retained_text_rows")),
    ]
    card_html = "\n".join(
        f"<div class='card'><span>{html.escape(label)}</span><strong>{'' if value is None else html.escape(str(round(value, 2) if isinstance(value, float) else value))}</strong></div>"
        for label, value in cards
    )
    cluster_html = "".join(
        f"<tr><td>{row['cluster']}</td><td>{row['row_count']}</td><td>{html.escape(row['top_terms'])}</td></tr>"
        for row in cluster_rows
    )
    sections = [
        html_img(figures["heatmap"], output_dir, "Disease Subtype x Intervention Type"),
        html_img(figures["stacked_outcome"], output_dir, "Intervention Type x Outcome Direction"),
        html_img(figures["network"], output_dir, "Disease-Intervention Bipartite Network"),
        html_img(figures["clusters"], output_dir, "Intervention Text Clusters"),
        html_img(figures["sample_size"], output_dir, "Sample Size Distribution"),
        html_img(figures["follow_up"], output_dir, "Follow-up Time Distribution"),
        html_img(figures["severity"], output_dir, "Severity Distribution"),
        html_img(figures["population"], output_dir, "Population Coverage Missingness"),
    ]
    html_text = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Step3 Analysis Report</title>
<style>
body {{ font-family: Segoe UI, Arial, sans-serif; margin: 0; background: #f5f7f8; color: #1e2529; }}
header {{ padding: 28px 34px; background: #24343c; color: white; }}
main {{ max-width: 1280px; margin: 0 auto; padding: 24px 28px 48px; }}
h1 {{ margin: 0 0 8px; font-size: 28px; }}
h2 {{ margin: 0 0 14px; font-size: 20px; }}
.sources {{ opacity: .8; font-size: 13px; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin: 20px 0 24px; }}
.card {{ background: white; border: 1px solid #dde4e8; border-radius: 6px; padding: 14px 16px; }}
.card span {{ display: block; color: #607078; font-size: 12px; margin-bottom: 6px; }}
.card strong {{ font-size: 22px; }}
section {{ background: white; border: 1px solid #dde4e8; border-radius: 6px; padding: 18px; margin: 18px 0; }}
img {{ max-width: 100%; height: auto; display: block; }}
table {{ border-collapse: collapse; width: 100%; background: white; }}
td, th {{ border-bottom: 1px solid #dde4e8; padding: 8px; text-align: left; vertical-align: top; }}
th {{ color: #475860; font-size: 13px; }}
</style>
</head>
<body>
<header>
<h1>Step3 Analysis Report</h1>
<div class="sources">Sources: {source_files}</div>
</header>
<main>
<div class="cards">{card_html}</div>
{''.join(sections)}
<section>
<h2>Intervention Cluster Top Terms</h2>
<table>
<thead><tr><th>Cluster</th><th>Rows</th><th>Top terms</th></tr></thead>
<tbody>{cluster_html}</tbody>
</table>
</section>
</main>
</body>
</html>
"""
    report_path.write_text(html_text, encoding="utf-8")
    return report_path


def run_step3_analysis(
    *,
    input_paths: Sequence[str | Path],
    output_dir: str | Path,
    cluster_count: int = 8,
    network_min_edge: int = 10,
) -> Dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    df = prepare_dataframe(load_inputs(input_paths))

    dataset_path = output / "analysis_dataset.csv"
    df.to_csv(dataset_path, index=False, encoding="utf-8-sig")
    write_summary_tables(df, output)

    figures: Dict[str, Path] = {}
    figures["heatmap"] = plot_disease_intervention_heatmap(df, output)
    figures["stacked_outcome"] = plot_intervention_outcome_stacked(df, output)
    figures["network"] = plot_bipartite_network(df, output, network_min_edge)
    figures["clusters"], _assignments, cluster_rows = intervention_cluster(df, output, cluster_count)
    figures["sample_size"] = plot_sample_size(df, output)
    figures["follow_up"] = plot_follow_up(df, output)
    figures["severity"] = plot_severity(df, output)
    figures["population"] = plot_population_coverage(df, output)

    cluster_path = output / "intervention_cluster_assignments.csv"
    metrics = compute_metrics(df, cluster_rows)
    summary_path = output / "Step3_analysis_summary.json"
    summary_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path = write_html_report(output, figures, metrics, cluster_rows)

    return AnalysisResult(
        output_dir=output,
        report_path=report_path,
        summary_path=summary_path,
        dataset_path=dataset_path,
        cluster_path=cluster_path,
        figures=figures,
        metrics=metrics,
    ).to_dict()
