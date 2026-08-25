"""
Scores dev.to articles for Green Software Engineering (GSE) adoption signals
across five dimensions, then aggregates results into a composite GSEAS score.
"""

import re
import math
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Per-dimension extraction patterns. "weight" here is a per-signal extraction
# weight (kept uniform — relative dimension importance lives in GSEAS_WEIGHTS
# below, applied once at aggregation, not duplicated here).
GSE_SIGNALS = {
    "energy_efficiency": {
        "label": "Energy Efficiency",
        "patterns": [
            r"\b(energy[- ]efficient|power consumption|energy usage|watt(?:s|age)?|"
            r"kilowatt[- ]?hours?|kWh|joule|cpu[- ]power|power[- ]draw|"
            r"energy[- ]monitoring|profiling[- ]energy|low[- ]power)\b",
        ],
        "weight": 1.0,
    },
    "carbon_awareness": {
        "label": "Carbon Awareness",
        "patterns": [
            r"\b(carbon[- ]footprint|carbon[- ]emission|CO2|gCO2|carbon[- ]intensity|"
            r"scope [123]|net[- ]zero|carbon[- ]neutral|decarboni[sz]|greenhouse[- ]gas|"
            r"carbon[- ]offset|carbon[- ]aware|green[- ]grid)\b",
        ],
        "weight": 1.0,
    },
    "hardware_efficiency": {
        "label": "Hardware Efficiency",
        "patterns": [
            r"\b(hardware[- ]lifecycle|embodied[- ]carbon|e[- ]?waste|"
            r"server[- ]utilisation|right[- ]siz|hardware[- ]efficiency|"
            r"data[- ]center[- ]efficiency|PUE|power[- ]usage[- ]effectiveness|"
            r"hardware[- ]lifespan|circular[- ]economy)\b",
        ],
        "weight": 1.0,
    },
    "green_practices": {
        "label": "Green Software Practices",
        "patterns": [
            r"\b(green[- ]software|sustainable[- ]software|eco[- ]design|"
            r"software[- ]sustainability|green[- ]coding|carbon[- ]efficient[- ]code|"
            r"SCI|software[- ]carbon[- ]intensity|green[- ]metrics[- ]tool|"
            r"CodeCarbon|Scaphandre|cloud[- ]carbon[- ]footprint|"
            r"Green[- ]Software[- ]Foundation|GSF)\b",
        ],
        "weight": 1.0,
    },
    "measurement_tooling": {
        "label": "Measurement & Tooling",
        "patterns": [
            r"\b(measure[- ]carbon|carbon[- ]measurement|energy[- ]measurement|"
            r"RAPL|perf[- ]stat|prometheus|carbon[- ]dashboard|"
            r"sustainability[- ]metrics|green[- ]KPI|carbon[- ]tracking|"
            r"Kepler|Scaphandre|PowerAPI|carbon[- ]monitor)\b",
        ],
        "weight": 1.0,
    },
}

# Composite score weights — Energy Efficiency and Green Practices weighted
# highest as the two GSF core pillars; Hardware and Tooling as supporting
# dimensions. Must sum to 1.0.
GSEAS_WEIGHTS = {
    "energy_efficiency":    0.25,
    "carbon_awareness":     0.20,
    "hardware_efficiency":  0.15,
    "green_practices":      0.25,
    "measurement_tooling":  0.15,
}

# Tag-based corpus collection ("sustainability", "carbon") pulls in off-topic
# content — agriculture, climate policy, etc — that happens to mention "carbon
# footprint" once. An article counts as relevant if it matches generic
# software vocabulary OR a green_practices/measurement_tooling signal (those
# vocabularies, e.g. CodeCarbon/RAPL, are software-specific on their own).
SOFTWARE_CONTEXT_PATTERNS = [
    re.compile(
        r"\b(software|application|microservice|back[- ]?end|front[- ]?end|"
        r"web app|mobile app|server|cloud[- ]?native|deploy(?:ment)?|devops|"
        r"infrastructure|database|container|kubernetes|docker|source code|"
        r"codebase|developer|programming|software engineer\w*|repository|"
        r"github|python|javascript|typescript|framework|library|algorithm|"
        r"runtime|compiler|pipeline|endpoint|rest api|open[- ]source|"
        r"tech stack|production environment|api\b)\b",
        re.IGNORECASE,
    )
]


@dataclass
class GSESignal:
    dimension:  str
    match_text: str
    context:    str
    position:   int
    weight:     float


@dataclass
class ArticleAnalysis:
    article_id:        int
    title:             str
    url:               str
    author:            str
    published_at:      str
    tags:              list[str]
    clean_text:        str
    word_count:        int
    signals:           list[GSESignal]  = field(default_factory=list)

    energy_score:      float = 0.0
    carbon_score:      float = 0.0
    hardware_score:    float = 0.0
    practices_score:   float = 0.0
    tooling_score:     float = 0.0

    gse_adoption_score: float = 0.0    # GSEAS, 0–100
    gse_level:          str   = "Low"  # Low / Emerging / Moderate / Strong
    is_software_relevant: bool = True

    @property
    def signal_count(self) -> int:
        return len(self.signals)

    @property
    def dominant_dimension(self) -> str:
        scores = {
            "Energy Efficiency":    self.energy_score,
            "Carbon Awareness":     self.carbon_score,
            "Hardware Efficiency":  self.hardware_score,
            "Green Practices":      self.practices_score,
            "Measurement & Tooling": self.tooling_score,
        }
        return max(scores, key=scores.get)

    def to_dict(self) -> dict:
        return {
            "article_id":         self.article_id,
            "title":              self.title,
            "url":                self.url,
            "author":             self.author,
            "published_at":       self.published_at,
            "tags":               self.tags,
            "word_count":         self.word_count,
            "signal_count":       self.signal_count,
            "energy_score":       round(self.energy_score, 4),
            "carbon_score":       round(self.carbon_score, 4),
            "hardware_score":     round(self.hardware_score, 4),
            "practices_score":    round(self.practices_score, 4),
            "tooling_score":      round(self.tooling_score, 4),
            "gse_adoption_score": round(self.gse_adoption_score, 2),
            "gse_level":          self.gse_level,
            "dominant_dimension": self.dominant_dimension,
            "is_software_relevant": self.is_software_relevant,
            "signals": [
                {"dimension": s.dimension, "match_text": s.match_text, "context": s.context}
                for s in self.signals[:10]
            ],
        }


@dataclass
class CorpusReport:
    total_articles:      int       # full corpus, including off-topic articles
    gse_articles:        int       # relevant articles with adoption_score > 0
    mean_adoption_score: float     # computed over relevant articles only
    level_distribution:  dict[str, int]
    dimension_means:     dict[str, float]
    top_articles:        list[dict]
    tag_frequency:       dict[str, int]
    timeline:            list[dict]
    excluded_off_topic:  int = 0


class GSEAnalyser:
    """Rule-based GSE signal extraction with length-normalised scoring."""

    _compiled_patterns: dict[str, list[re.Pattern]] = {}

    def __init__(self):
        if not GSEAnalyser._compiled_patterns:
            GSEAnalyser._compiled_patterns = {
                dim: [re.compile(p, re.IGNORECASE) for p in cfg["patterns"]]
                for dim, cfg in GSE_SIGNALS.items()
            }
        self._software_patterns = SOFTWARE_CONTEXT_PATTERNS

    def analyse_article(self, article: dict) -> ArticleAnalysis:
        """Score a single dev.to article (dict from DevToFetcher) across all dimensions."""
        clean = self._clean_text(
            article.get("body_markdown", "") + " " + article.get("title", "")
        )
        word_count = len(clean.split()) if clean else 1

        result = ArticleAnalysis(
            article_id   = article.get("id", 0),
            title        = article.get("title", ""),
            url          = article.get("url", ""),
            author       = article.get("author", ""),
            published_at = article.get("published_at", ""),
            tags         = article.get("tag_list", []),
            clean_text   = clean[:2000],
            word_count   = word_count,
        )

        dim_raw_scores: dict[str, float] = {}
        dim_signal_counts: dict[str, int] = {}

        for dim, cfg in GSE_SIGNALS.items():
            signals, raw = self._extract_dimension(dim, cfg, clean, word_count)
            result.signals.extend(signals)
            dim_raw_scores[dim] = raw
            dim_signal_counts[dim] = len(signals)

        has_software_vocab = any(p.search(clean) for p in self._software_patterns)
        has_tool_specific_signal = (
            dim_signal_counts["green_practices"] > 0
            or dim_signal_counts["measurement_tooling"] > 0
        )
        result.is_software_relevant = has_software_vocab or has_tool_specific_signal

        result.energy_score    = self._sigmoid(dim_raw_scores["energy_efficiency"])
        result.carbon_score    = self._sigmoid(dim_raw_scores["carbon_awareness"])
        result.hardware_score  = self._sigmoid(dim_raw_scores["hardware_efficiency"])
        result.practices_score = self._sigmoid(dim_raw_scores["green_practices"])
        result.tooling_score   = self._sigmoid(dim_raw_scores["measurement_tooling"])

        weighted = (
            result.energy_score    * GSEAS_WEIGHTS["energy_efficiency"] +
            result.carbon_score    * GSEAS_WEIGHTS["carbon_awareness"] +
            result.hardware_score  * GSEAS_WEIGHTS["hardware_efficiency"] +
            result.practices_score * GSEAS_WEIGHTS["green_practices"] +
            result.tooling_score   * GSEAS_WEIGHTS["measurement_tooling"]
        )

        result.gse_adoption_score = round(weighted * 100, 2)
        result.gse_level = self._adoption_level(result.gse_adoption_score)

        return result

    def analyse_corpus(self, articles: list[dict]) -> tuple[list[ArticleAnalysis], CorpusReport]:
        results = []
        for article in articles:
            try:
                results.append(self.analyse_article(article))
            except Exception as e:
                logger.warning(f"Failed to analyse article {article.get('id')}: {e}")

        return results, self._build_report(results)

    def sensitivity_analysis(self, result: ArticleAnalysis, perturbation: float = 0.05) -> dict:
        """
        Perturb each GSEAS weight upward by `perturbation`, renormalise the rest
        to sum to 1.0, and recompute the composite score against the article's
        already-extracted dimension scores. A small max_abs_delta means no
        single weight is driving the result.
        """
        dim_scores = {
            "energy_efficiency":   result.energy_score,
            "carbon_awareness":    result.carbon_score,
            "hardware_efficiency": result.hardware_score,
            "green_practices":     result.practices_score,
            "measurement_tooling": result.tooling_score,
        }
        baseline = result.gse_adoption_score
        deltas: dict[str, float] = {}

        for dim in GSEAS_WEIGHTS:
            perturbed = dict(GSEAS_WEIGHTS)
            perturbed[dim] = min(1.0, perturbed[dim] + perturbation)
            total = sum(perturbed.values())
            perturbed = {k: v / total for k, v in perturbed.items()}

            perturbed_score = round(
                sum(dim_scores[k] * perturbed[k] for k in perturbed) * 100, 2
            )
            deltas[dim] = round(perturbed_score - baseline, 2)

        return {
            "baseline_score": baseline,
            "baseline_level": result.gse_level,
            "weight_deltas":  deltas,
            "max_abs_delta":  max((abs(v) for v in deltas.values()), default=0.0),
        }

    def _extract_dimension(
        self, dim: str, cfg: dict, text: str, word_count: int
    ) -> tuple[list[GSESignal], float]:
        signals = []
        total_weight = 0.0

        for pattern in self._compiled_patterns[dim]:
            for match in pattern.finditer(text):
                start = match.start()
                ctx_start = max(0, start - 40)
                ctx_end   = min(len(text), match.end() + 40)
                context   = "..." + text[ctx_start:ctx_end].replace("\n", " ") + "..."

                signals.append(GSESignal(
                    dimension  = cfg["label"],
                    match_text = match.group(),
                    context    = context,
                    position   = start,
                    weight     = cfg["weight"],
                ))
                total_weight += cfg["weight"]

        tf_score = (total_weight / word_count) * 1000 if word_count > 0 else 0.0
        return signals, tf_score

    @staticmethod
    def _clean_text(raw: str) -> str:
        text = re.sub(r"```[\s\S]*?```", " ", raw)
        text = re.sub(r"`[^`]+`", " ", text)
        text = re.sub(r"!\[.*?\]\(.*?\)", " ", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"#{1,6}\s+", " ", text)
        text = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", text)
        text = re.sub(r"https?://\S+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _sigmoid(x: float) -> float:
        return 1 / (1 + math.exp(-x + 1.5))

    @staticmethod
    def _adoption_level(score: float) -> str:
        """Equal-quartile bands — clean boundaries, nothing ad hoc to justify."""
        if score >= 75:   return "Strong"
        if score >= 50:   return "Moderate"
        if score >= 25:   return "Emerging"
        return "Low"

    @staticmethod
    def _build_report(results: list[ArticleAnalysis]) -> CorpusReport:
        """
        Aggregate stats (mean, dimension means, top articles, timeline) are
        computed over relevant articles only. Off-topic articles stay in the
        raw `results` list with is_software_relevant=False — excluded from
        the report, not deleted.
        """
        if not results:
            return CorpusReport(
                total_articles=0, gse_articles=0, mean_adoption_score=0.0,
                level_distribution={}, dimension_means={}, top_articles=[],
                tag_frequency={}, timeline=[], excluded_off_topic=0,
            )

        relevant = [r for r in results if r.is_software_relevant]
        excluded_count = len(results) - len(relevant)
        # Never report an empty corpus just because everything got filtered.
        basis = relevant if relevant else results

        gse_articles = [r for r in basis if r.gse_adoption_score > 0]
        scores = [r.gse_adoption_score for r in basis]
        mean_score = sum(scores) / len(scores) if scores else 0.0

        level_dist: dict[str, int] = {}
        for r in basis:
            level_dist[r.gse_level] = level_dist.get(r.gse_level, 0) + 1

        dim_means = {
            "Energy Efficiency":     sum(r.energy_score    for r in basis) / len(basis),
            "Carbon Awareness":      sum(r.carbon_score    for r in basis) / len(basis),
            "Hardware Efficiency":   sum(r.hardware_score  for r in basis) / len(basis),
            "Green Practices":       sum(r.practices_score for r in basis) / len(basis),
            "Measurement & Tooling": sum(r.tooling_score   for r in basis) / len(basis),
        }

        top = sorted(basis, key=lambda r: r.gse_adoption_score, reverse=True)[:10]

        tag_freq: dict[str, int] = {}
        for r in basis:
            for tag in r.tags:
                tag_freq[tag] = tag_freq.get(tag, 0) + 1

        monthly: dict[str, list[float]] = {}
        for r in basis:
            if r.published_at:
                monthly.setdefault(r.published_at[:7], []).append(r.gse_adoption_score)
        timeline = [
            {"month": m, "mean_score": sum(v) / len(v), "article_count": len(v)}
            for m, v in sorted(monthly.items())
        ]

        return CorpusReport(
            total_articles      = len(results),
            gse_articles        = len(gse_articles),
            mean_adoption_score = round(mean_score, 2),
            level_distribution  = level_dist,
            dimension_means     = {k: round(v, 4) for k, v in dim_means.items()},
            top_articles        = [r.to_dict() for r in top],
            tag_frequency       = dict(sorted(tag_freq.items(), key=lambda x: -x[1])[:30]),
            timeline            = timeline,
            excluded_off_topic  = excluded_count,
        )


_analyser_instance: GSEAnalyser | None = None


def get_analyser() -> GSEAnalyser:
    global _analyser_instance
    if _analyser_instance is None:
        _analyser_instance = GSEAnalyser()
    return _analyser_instance
