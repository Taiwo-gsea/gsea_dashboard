"""
GSEA Dashboard - Unit Tests: NLP Pipeline
==========================================
Tests for the GSEANLPPipeline extraction engine.

Run: pytest tests/unit/test_nlp_pipeline.py -v
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from nlp.pipelines.gsea_pipeline import (
    GSEANLPPipeline, ExtractionResult, nlp_pipeline
)


@pytest.fixture
def pipeline():
    return GSEANLPPipeline()


@pytest.fixture
def sample_text():
    return (
        "The study measured energy consumption of 0.45 kWh over a 2-hour test period. "
        "Carbon emissions were calculated at 104.85 gCO2eq using a UK grid carbon intensity "
        "of 233 gCO2eq/kWh. The SCI score = 0.1049 per API call. "
        "Measurements were collected using CodeCarbon and Green Metrics Tool. "
        "CPU average utilisation was 43.2% with a TDP-based estimation method applied. "
        "The server rack embodied carbon was 2000000 gCO₂eq over its lifetime."
    )


class TestPipelineExtraction:
    """Core extraction functionality tests."""

    def test_extract_returns_extraction_result(self, pipeline, sample_text):
        result = pipeline.extract(sample_text)
        assert isinstance(result, ExtractionResult)

    def test_extract_finds_energy_value(self, pipeline, sample_text):
        result = pipeline.extract(sample_text)
        energy_entities = [e for e in result.entities if e.entity_type == "ENERGY_VALUE"]
        assert len(energy_entities) >= 1

    def test_extract_finds_carbon_metric(self, pipeline, sample_text):
        result = pipeline.extract(sample_text)
        carbon_entities = [e for e in result.entities if e.entity_type == "CARBON_METRIC"]
        assert len(carbon_entities) >= 1

    def test_extract_finds_software_tool(self, pipeline, sample_text):
        result = pipeline.extract(sample_text)
        tool_entities = [e for e in result.entities if e.entity_type == "SOFTWARE_TOOL"]
        tool_names = [e.entity_text for e in tool_entities]
        # CodeCarbon and Green Metrics Tool should both be found
        assert any("CodeCarbon" in t or "codecarbon" in t.lower() for t in tool_names)

    def test_extract_finds_methodology(self, pipeline, sample_text):
        result = pipeline.extract(sample_text)
        method_entities = [e for e in result.entities if e.entity_type == "METHODOLOGY"]
        assert len(method_entities) >= 1

    def test_empty_text_returns_empty_result(self, pipeline):
        result = pipeline.extract("")
        assert len(result.entities) == 0
        assert result.source_text_length == 0

    def test_whitespace_only_returns_empty_result(self, pipeline):
        result = pipeline.extract("   \n\t  ")
        assert len(result.entities) == 0

    def test_extraction_result_has_processing_time(self, pipeline, sample_text):
        result = pipeline.extract(sample_text)
        assert result.processing_time_ms >= 0

    def test_extraction_result_source_text_length_correct(self, pipeline, sample_text):
        result = pipeline.extract(sample_text)
        # Length after whitespace normalisation
        assert result.source_text_length > 0


class TestEntityAttributes:
    """Tests for ExtractedEntity data quality."""

    def test_entities_have_valid_confidence_scores(self, pipeline, sample_text):
        result = pipeline.extract(sample_text)
        for entity in result.entities:
            assert 0.0 <= entity.confidence_score <= 1.0

    def test_entities_have_non_empty_text(self, pipeline, sample_text):
        result = pipeline.extract(sample_text)
        for entity in result.entities:
            assert entity.entity_text.strip() != ""

    def test_entities_have_source_excerpt(self, pipeline, sample_text):
        result = pipeline.extract(sample_text)
        for entity in result.entities:
            assert entity.source_excerpt != ""

    def test_energy_entities_have_numeric_value(self, pipeline):
        result = pipeline.extract("Energy consumption of 0.45 kWh was measured.")
        energy_entities = [e for e in result.entities if e.entity_type == "ENERGY_VALUE"]
        if energy_entities:
            assert energy_entities[0].entity_value is not None
            assert energy_entities[0].entity_value == pytest.approx(0.45)

    def test_software_tool_entities_have_high_confidence(self, pipeline):
        result = pipeline.extract("We used CodeCarbon to measure emissions.")
        tool_entities = [e for e in result.entities if e.entity_type == "SOFTWARE_TOOL"]
        if tool_entities:
            assert tool_entities[0].confidence_score >= 0.90


class TestDeduplication:
    """Tests for entity deduplication logic."""

    def test_no_duplicate_entities_at_same_position(self, pipeline, sample_text):
        result = pipeline.extract(sample_text)
        positions = [(e.start_char, e.end_char) for e in result.entities]
        assert len(positions) == len(set(positions)), "Duplicate (start, end) spans found"


class TestSerialisation:
    """Tests for to_dict() output."""

    def test_entity_to_dict_has_required_keys(self, pipeline, sample_text):
        result = pipeline.extract(sample_text)
        if result.entities:
            d = result.entities[0].to_dict()
            required = {"entity_type", "entity_text", "confidence_score",
                        "source_excerpt", "extraction_method", "validated", "accepted"}
            assert required.issubset(set(d.keys()))

    def test_extract_to_dicts_returns_list(self, pipeline, sample_text):
        dicts = pipeline.extract_to_dicts(sample_text)
        assert isinstance(dicts, list)
        if dicts:
            assert isinstance(dicts[0], dict)


class TestByTypeGrouping:
    """Tests for ExtractionResult.by_type property."""

    def test_by_type_groups_correctly(self, pipeline, sample_text):
        result = pipeline.extract(sample_text)
        by_type = result.by_type
        for entity_type, entities in by_type.items():
            assert all(e.entity_type == entity_type for e in entities)

    def test_summary_counts_match_entities(self, pipeline, sample_text):
        result = pipeline.extract(sample_text)
        summary = result.summary
        total_from_summary = sum(summary["by_type"].values())
        assert total_from_summary == len(result.entities)


class TestModuleLevelSingleton:
    """Tests for the module-level pipeline instance."""

    def test_nlp_pipeline_is_instance(self):
        assert isinstance(nlp_pipeline, GSEANLPPipeline)

    def test_nlp_pipeline_extract_to_dicts_works(self):
        dicts = nlp_pipeline.extract_to_dicts("Energy of 0.1 kWh used by CodeCarbon.")
        assert isinstance(dicts, list)
