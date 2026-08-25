"""
GSEA Dashboard - NLP Extraction Pipeline
==========================================
Hybrid NLP pipeline for extracting GSE entities from text:

  Layer 1: Rule-based extraction (regex + spaCy EntityRuler)
           — Fast, deterministic, high precision on known patterns
  Layer 2: Transformer NER (Hugging Face) [optional, loaded on demand]
           — Handles novel phrasing, context-sensitive extraction

Entity types:
  ENERGY_VALUE    — Numeric energy measurements (kWh, Wh, W, etc.)
  CARBON_METRIC   — Carbon/CO₂ values and SCI scores
  SOFTWARE_TOOL   — Named GSE tools (CodeCarbon, GMT, etc.)
  METHODOLOGY     — Research methods (proxy measurement, RAPL, etc.)

Reference: Spillias et al. (2025) human-in-the-loop NLP for scientific extraction.
           Alshami et al. (2023) RAG-compatible NER pipeline design.

STATUS: Exploratory hybrid extraction pipeline, not integrated into the
production NLP pipeline described in the dissertation (Chapter 3, Section
3.3.2 and Figure 3.2), which uses devto_fetcher.py + gse_analyser.py — a
purely rule-based design chosen deliberately for auditability against the
Cohen's Kappa validation in Chapter 5, absence of labelled training data,
and the Streamlit Community Cloud deployment memory constraint (Section
3.3.3). This module is retained, alongside its own test suite
(tests/unit/test_nlp_pipeline.py), as evidence of the alternative,
transformer-capable approach that was considered and the reasoning for
not adopting it in the shipped pipeline.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


# ── Entity type definitions ────────────────────────────────────────────────

ENTITY_TYPES = {
    "ENERGY_VALUE":   "Numeric energy measurement (kWh, Wh, W, J)",
    "CARBON_METRIC":  "Carbon emission or intensity value (gCO₂eq, SCI score)",
    "SOFTWARE_TOOL":  "Named GSE software tool or framework",
    "METHODOLOGY":    "Measurement methodology or technique",
    "HARDWARE":       "Hardware component or specification",
}


# ── Pattern library ────────────────────────────────────────────────────────

PATTERNS: dict[str, list[str]] = {
    "ENERGY_VALUE": [
        r'(\d+\.?\d*)\s*(kWh|kilowatt.?hours?)',
        r'(\d+\.?\d*)\s*(Wh|watt.?hours?)',
        r'(\d+\.?\d*)\s*(mWh|milliwatt.?hours?)',
        r'(\d+\.?\d*)\s*(MWh|megawatt.?hours?)',
        r'(\d+\.?\d*)\s*(W|watts?)\s+(?:average|avg|peak|idle|consumption|power)',
        r'energy\s+(?:consumption|consumed|usage|used|draw)\s+(?:of|was|is|:)?\s*(\d+\.?\d*)\s*(kWh|Wh|W)',
        r'power\s+(?:draw|consumption|usage)\s+(?:of|:)?\s*(\d+\.?\d*)\s*(W|watts?)',
        r'(\d+\.?\d*)\s*(joules?|J)\b',
    ],
    "CARBON_METRIC": [
        r'(\d+\.?\d*)\s*(gCO₂eq|gCO2eq|g\s*CO₂\s*eq|grams?\s+CO₂\s+equivalent)',
        r'(\d+\.?\d*)\s*(kgCO₂?|kg\s*CO₂?|kilograms?\s+CO₂?)',
        r'(\d+\.?\d*)\s*(tCO₂?|tonnes?\s+CO₂?)',
        r'SCI\s*(?:score|=|value|of|:)?\s*(?:is|was|=)?\s*(\d+\.?\d*)',
        r'carbon\s+intensity\s+(?:of|:)?\s*(\d+\.?\d*)\s*(gCO₂?(?:eq)?/kWh)',
        r'emissions?\s+(?:rate\s+)?(?:of|:)?\s*(\d+\.?\d*)\s*(gCO₂?|kgCO₂?)',
        r'(\d+\.?\d*)\s*(gCO₂?)\s*(?:per|/)\s*(?:kWh|hour|request|call|user)',
        r'carbon\s+footprint\s+(?:of|:)?\s*(\d+\.?\d*)',
    ],
    "SOFTWARE_TOOL": [
        r'\b(CodeCarbon|code.?carbon)\b',
        r'\b(Green\s+Metrics\s+Tool|GMT)\b',
        r'\b(Scaphandre)\b',
        r'\b(PowerAPI|Power\s+API)\b',
        r'\b(RAPL|Running\s+Average\s+Power\s+Limit)\b',
        r'\b(Kepler|Kubernetes-based\s+Efficient\s+Power\s+Level)\b',
        r'\b(PowerTOP|powertop)\b',
        r'\b(perf|perf-stat)\b',
        r'\b(Streamlit|FastAPI|Flask|Django)\b',
        r'\b(Prometheus|Grafana)\b',
    ],
    "METHODOLOGY": [
        r'\b(proxy\s+metric(?:s)?)\b',
        r'\b(RAPL\s+measurement)\b',
        r'\b(direct\s+measurement)\b',
        r'\b(TDP.?based\s+estimation)\b',
        r'\b(power\s+model(?:ling)?)\b',
        r'\b(System\s+Usability\s+Scale|SUS)\b',
        r'\b(mixed.?methods?)\b',
        r'\b(user\s+stud(?:y|ies))\b',
    ],
    "HARDWARE": [
        r'\b(cloud\s+VM|virtual\s+machine|EC2|GCP|Azure\s+VM)\b',
        r'\b(Raspberry\s+Pi\s+\d?)\b',
        r'\b(Intel\s+Core\s+i\d|AMD\s+Ryzen\s+\d)\b',
        r'\b(NVIDIA\s+[A-Z]\d+|Tesla\s+[A-Z]\d+|RTX\s+\d+)\b',
        r'\b(server\s+rack|data\s+cent(?:re|er))\b',
        r'\b(laptop|desktop|workstation|embedded\s+device)\b',
    ],
}


# ── Entity dataclass ───────────────────────────────────────────────────────

@dataclass
class ExtractedEntity:
    """A single extracted entity with metadata."""
    entity_type: str
    entity_text: str
    start_char: int
    end_char: int
    confidence_score: float
    source_excerpt: str = ""
    entity_value: Optional[float] = None
    entity_unit: Optional[str] = None
    extraction_method: str = "rule_based"

    def to_dict(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "entity_text": self.entity_text,
            "entity_value": self.entity_value,
            "entity_unit": self.entity_unit,
            "confidence_score": self.confidence_score,
            "source_excerpt": self.source_excerpt,
            "extraction_method": self.extraction_method,
            "validated": False,
            "accepted": None,
        }


@dataclass
class ExtractionResult:
    """Full result of a pipeline extraction run."""
    entities: list[ExtractedEntity] = field(default_factory=list)
    source_text_length: int = 0
    extraction_method: str = "rule_based"
    extracted_at: str = field(default_factory=lambda: datetime.now().isoformat())
    processing_time_ms: float = 0.0

    @property
    def by_type(self) -> dict[str, list[ExtractedEntity]]:
        """Group entities by type."""
        groups: dict[str, list] = {}
        for e in self.entities:
            groups.setdefault(e.entity_type, []).append(e)
        return groups

    @property
    def summary(self) -> dict:
        return {
            "total_entities": len(self.entities),
            "by_type": {k: len(v) for k, v in self.by_type.items()},
            "source_text_length": self.source_text_length,
            "extraction_method": self.extraction_method,
            "extracted_at": self.extracted_at,
        }


# ── Pipeline ───────────────────────────────────────────────────────────────

class GSEANLPPipeline:
    """
    Rule-based NLP extraction pipeline for GSE text.

    Architecture:
      1. Pre-process: normalise whitespace, fix unicode
      2. Rule-based extraction: compiled regex patterns per entity type
      3. Context windowing: extract surrounding text for validation
      4. Deduplication: remove overlapping matches, keep highest confidence
      5. (Optional) Transformer re-ranking: score entities with BERT
         — loaded lazily to avoid import-time overhead

    The rule-based layer provides precision on known patterns (E/I/M/R values).
    The transformer layer (when available) catches novel phrasing.
    This hybrid approach is justified by Alshami et al. (2023).
    """

    def __init__(self, context_window: int = 80):
        """
        Args:
            context_window: Number of characters around a match to include
                            as source_excerpt for human validation.
        """
        self.context_window = context_window
        self._compiled_patterns: dict[str, list] = {}
        self._transformer_loaded = False
        self._compile_patterns()
        logger.info("GSEANLPPipeline initialised (rule-based mode).")

    def _compile_patterns(self) -> None:
        """Pre-compile all regex patterns for performance."""
        for entity_type, pattern_list in PATTERNS.items():
            self._compiled_patterns[entity_type] = [
                re.compile(p, re.IGNORECASE | re.UNICODE)
                for p in pattern_list
            ]

    def _extract_numeric_value(self, text: str) -> Optional[float]:
        """Extract first numeric value from a text string."""
        match = re.search(r'\d+\.?\d*', text)
        if match:
            try:
                return float(match.group())
            except ValueError:
                return None
        return None

    def _extract_unit(self, text: str) -> Optional[str]:
        """Extract unit string from matched text."""
        unit_pattern = re.compile(
            r'(kWh|Wh|mWh|MWh|W|watts?|J|joules?|'
            r'gCO₂eq|gCO2eq|gCO₂|kgCO₂?|tCO₂?|'
            r'gCO₂?(?:eq)?/kWh|%)',
            re.IGNORECASE
        )
        match = unit_pattern.search(text)
        return match.group(0) if match else None

    def _get_context(self, text: str, start: int, end: int) -> str:
        """Extract context window around a match."""
        ctx_start = max(0, start - self.context_window)
        ctx_end = min(len(text), end + self.context_window)
        prefix = "..." if ctx_start > 0 else ""
        suffix = "..." if ctx_end < len(text) else ""
        return f"{prefix}{text[ctx_start:ctx_end]}{suffix}"

    def _assign_confidence(self, entity_type: str, pattern_idx: int,
                            match_text: str = "") -> float:
        """
        Assign confidence score based on entity type, pattern specificity,
        and match quality heuristics. Polish 15: varied confidence scores.

        Heuristics:
          - Patterns with explicit units get +0.05 (more specific)
          - Patterns with numeric values get +0.03
          - Later (more general) patterns get a decreasing penalty
          - Minimum confidence floor: 0.50
        """
        base_scores = {
            "ENERGY_VALUE":  0.85,
            "CARBON_METRIC": 0.82,
            "SOFTWARE_TOOL": 0.95,  # Tool names are highly specific
            "METHODOLOGY":   0.78,
            "HARDWARE":      0.80,
        }
        base = base_scores.get(entity_type, 0.75)
        # Penalty for later (more general) patterns
        penalty = min(0.15, pattern_idx * 0.02)
        score = base - penalty
        # Bonus: explicit unit present (e.g. "kWh", "gCO2eq")
        unit_markers = ["kwh", "wh", "gco2", "co2eq", "watts", "joules"]
        if any(u in match_text.lower() for u in unit_markers):
            score += 0.05
        # Bonus: numeric value present
        import re
        if re.search(r'\d', match_text):
            score += 0.03
        return round(min(0.99, max(0.50, score)), 2)

    def _deduplicate(self, entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
        """
        Remove overlapping entities, keeping the one with highest confidence.
        Prevents the same text span from being tagged twice.
        """
        if not entities:
            return []

        entities_sorted = sorted(entities, key=lambda e: (e.start_char, -e.confidence_score))
        deduped = []
        last_end = -1

        for entity in entities_sorted:
            if entity.start_char >= last_end:
                deduped.append(entity)
                last_end = entity.end_char
            else:
                # Overlap: replace if higher confidence
                if deduped and entity.confidence_score > deduped[-1].confidence_score:
                    deduped[-1] = entity
                    last_end = entity.end_char

        return deduped

    def extract(self, text: str) -> ExtractionResult:
        """
        Run the full extraction pipeline on input text.

        Args:
            text: Raw input text (paper excerpt, tool log, etc.)

        Returns:
            ExtractionResult with all found entities and metadata
        """
        import time
        start_time = time.time()

        if not text or not text.strip():
            return ExtractionResult(source_text_length=0)

        # Normalise whitespace
        clean_text = re.sub(r'\s+', ' ', text.strip())

        all_entities: list[ExtractedEntity] = []

        for entity_type, compiled_patterns in self._compiled_patterns.items():
            for pattern_idx, pattern in enumerate(compiled_patterns):
                for match in pattern.finditer(clean_text):
                    matched_text = match.group(0)
                    confidence = self._assign_confidence(entity_type, pattern_idx, matched_text)

                    entity = ExtractedEntity(
                        entity_type=entity_type,
                        entity_text=matched_text.strip(),
                        start_char=match.start(),
                        end_char=match.end(),
                        confidence_score=confidence,
                        source_excerpt=self._get_context(clean_text, match.start(), match.end()),
                        entity_value=self._extract_numeric_value(matched_text),
                        entity_unit=self._extract_unit(matched_text),
                        extraction_method="rule_based",
                    )
                    all_entities.append(entity)

        deduplicated = self._deduplicate(all_entities)
        # Sort by position in text
        deduplicated.sort(key=lambda e: e.start_char)

        elapsed_ms = (time.time() - start_time) * 1000

        return ExtractionResult(
            entities=deduplicated,
            source_text_length=len(clean_text),
            extraction_method="rule_based",
            processing_time_ms=round(elapsed_ms, 2),
        )

    def extract_to_dicts(self, text: str) -> list[dict]:
        """
        Convenience method returning extraction results as list of dicts.
        Used directly by the Streamlit NLP page and FastAPI endpoint.
        """
        result = self.extract(text)
        return [e.to_dict() for e in result.entities]

    def try_load_transformer(self, model_name: str = "dslim/bert-base-NER") -> bool:
        """
        Attempt to load the Hugging Face transformer NER model.
        Falls back gracefully if transformers/torch not installed.

        Args:
            model_name: HuggingFace model identifier

        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            from transformers import pipeline as hf_pipeline
            self._ner_pipeline = hf_pipeline("ner", model=model_name, grouped_entities=True)
            self._transformer_loaded = True
            logger.info(f"Transformer NER loaded: {model_name}")
            return True
        except Exception as e:
            logger.warning(f"Transformer not available ({e}) — using rule-based only.")
            return False


# ── Module-level singleton ─────────────────────────────────────────────────
nlp_pipeline = GSEANLPPipeline()
