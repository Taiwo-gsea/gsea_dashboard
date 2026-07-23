"""
Tests for the GSE adoption analyser.
Covers: text cleaning, signal extraction, scoring, level assignment, corpus report,
and sensitivity analysis.

Updated for GSEAS v2 — explicit named weights (25/20/15/25/15%), four equal-quartile
adoption bands (Low/Emerging/Moderate/Strong at 0–24/25–49/50–74/75–100).
"""
import pytest
from nlp.gse_analyser import GSEAnalyser, get_analyser, GSEAS_WEIGHTS


@pytest.fixture
def analyser():
    return GSEAnalyser()


@pytest.fixture
def gse_article():
    return {
        "id": 1,
        "title": "Measuring software carbon with CodeCarbon and Green Metrics Tool",
        "url": "https://dev.to/test/article",
        "author": "testuser",
        "published_at": "2026-01-15T10:00:00Z",
        "body_markdown": (
            "We used CodeCarbon to measure energy consumption of 0.45 kWh. "
            "The carbon intensity of our AWS EU-West region is 316 gCO2eq/kWh. "
            "Our SCI score is 142 gCO2eq per 1000 API calls. "
            "We reduced power consumption by enabling carbon-aware scheduling. "
            "The Green Software Foundation SCI spec guided our measurement methodology. "
            "Hardware lifecycle and embodied carbon contributed 12% of our total footprint."
        ),
        "tag_list": ["green-software", "sustainability", "carbon"],
    }


@pytest.fixture
def minimal_article():
    return {
        "id": 2,
        "title": "How to build a REST API",
        "url": "https://dev.to/test/rest",
        "author": "dev",
        "published_at": "2026-02-01T00:00:00Z",
        "body_markdown": "In this tutorial we build a REST API using Python and FastAPI.",
        "tag_list": ["python", "api"],
    }


@pytest.fixture
def offtopic_article():
    """Reproduces the real-world contamination case: a farming/agriculture
    article that matched the broad 'sustainability'/'carbon' dev.to tags but
    has nothing to do with software engineering."""
    return {
        "id": 3,
        "title": "Vertical Farming vs. Agroforestry: Sustainable Food Production",
        "url": "https://dev.to/test/farming",
        "author": "dirkroethig-verdantis",
        "published_at": "2026-05-20T00:00:00Z",
        "body_markdown": (
            "Vertical farming reduces land use and water consumption. "
            "Agroforestry combines trees and crops to lower the carbon footprint "
            "of food production. Sustainable practices help farmers reduce emissions."
        ),
        "tag_list": ["sustainability", "carbon", "farming"],
    }


@pytest.fixture
def tool_specific_article():
    """A genuinely software-relevant article that uses only domain-specific
    tool names (no generic software vocabulary) — tests that green_practices/
    measurement_tooling signals alone are sufficient for relevance."""
    return {
        "id": 4,
        "title": "CodeCarbon Results",
        "url": "https://dev.to/test/codecarbon",
        "author": "dev",
        "published_at": "2026-05-20T00:00:00Z",
        "body_markdown": "CodeCarbon reported 0.3 kWh. RAPL confirmed the reading.",
        "tag_list": ["green-software"],
    }


class TestWeights:
    def test_weights_sum_to_one(self):
        assert abs(sum(GSEAS_WEIGHTS.values()) - 1.0) < 1e-9

    def test_energy_and_practices_highest(self):
        """Energy Efficiency and Green Practices are the two GSF core pillars."""
        assert GSEAS_WEIGHTS["energy_efficiency"] == 0.25
        assert GSEAS_WEIGHTS["green_practices"] == 0.25

    def test_hardware_and_tooling_lowest(self):
        assert GSEAS_WEIGHTS["hardware_efficiency"] == 0.15
        assert GSEAS_WEIGHTS["measurement_tooling"] == 0.15

    def test_all_weights_positive(self):
        for k, v in GSEAS_WEIGHTS.items():
            assert v > 0, f"{k} weight must be positive"


class TestTextCleaning:
    def test_strips_code_blocks(self, analyser):
        text = "Before ```code block\nsome code``` After"
        clean = analyser._clean_text(text)
        assert "code block" not in clean
        assert "Before" in clean
        assert "After" in clean

    def test_strips_html_tags(self, analyser):
        text = "<p>Hello <strong>world</strong></p>"
        clean = analyser._clean_text(text)
        assert "<" not in clean
        assert "Hello" in clean
        assert "world" in clean

    def test_strips_markdown_links(self, analyser):
        text = "Check [this link](https://example.com) for details"
        clean = analyser._clean_text(text)
        assert "https://example.com" not in clean
        assert "this link" in clean

    def test_strips_urls(self, analyser):
        text = "Visit https://greensoftware.foundation for more info"
        clean = analyser._clean_text(text)
        assert "https://greensoftware.foundation" not in clean

    def test_collapses_whitespace(self, analyser):
        text = "Hello    world\n\n\ntest"
        clean = analyser._clean_text(text)
        assert "  " not in clean


class TestSignalExtraction:
    def test_detects_carbon_signals(self, analyser, gse_article):
        result = analyser.analyse_article(gse_article)
        carbon_signals = [s for s in result.signals if "Carbon" in s.dimension]
        assert len(carbon_signals) > 0

    def test_detects_energy_signals(self, analyser, gse_article):
        result = analyser.analyse_article(gse_article)
        energy_signals = [s for s in result.signals if "Energy" in s.dimension]
        assert len(energy_signals) > 0

    def test_detects_practices_signals(self, analyser, gse_article):
        result = analyser.analyse_article(gse_article)
        practice_signals = [s for s in result.signals if "Practice" in s.dimension]
        assert len(practice_signals) > 0

    def test_context_window_present(self, analyser, gse_article):
        result = analyser.analyse_article(gse_article)
        for signal in result.signals:
            assert len(signal.context) > 0

    def test_no_signals_in_minimal_article(self, analyser, minimal_article):
        result = analyser.analyse_article(minimal_article)
        assert result.signal_count == 0 or result.gse_adoption_score < 25


class TestScoring:
    def test_gse_article_scores_higher_than_minimal(self, analyser, gse_article, minimal_article):
        gse_result = analyser.analyse_article(gse_article)
        min_result = analyser.analyse_article(minimal_article)
        assert gse_result.gse_adoption_score > min_result.gse_adoption_score

    def test_score_range(self, analyser, gse_article):
        result = analyser.analyse_article(gse_article)
        assert 0 <= result.gse_adoption_score <= 100

    def test_dimension_scores_range(self, analyser, gse_article):
        result = analyser.analyse_article(gse_article)
        for score in [result.energy_score, result.carbon_score,
                      result.hardware_score, result.practices_score,
                      result.tooling_score]:
            assert 0.0 <= score <= 1.0

    def test_gse_rich_article_not_low_level(self, analyser, gse_article):
        result = analyser.analyse_article(gse_article)
        assert result.gse_level != "Low"

    def test_minimal_article_low_level(self, analyser, minimal_article):
        result = analyser.analyse_article(minimal_article)
        assert result.gse_level in ("Low", "Emerging")

    def test_composite_uses_named_weights(self, analyser, gse_article):
        """Manually compute composite to verify GSEAS_WEIGHTS are applied."""
        result = analyser.analyse_article(gse_article)
        expected = (
            result.energy_score    * GSEAS_WEIGHTS["energy_efficiency"] +
            result.carbon_score    * GSEAS_WEIGHTS["carbon_awareness"] +
            result.hardware_score  * GSEAS_WEIGHTS["hardware_efficiency"] +
            result.practices_score * GSEAS_WEIGHTS["green_practices"] +
            result.tooling_score   * GSEAS_WEIGHTS["measurement_tooling"]
        ) * 100
        assert abs(result.gse_adoption_score - round(expected, 2)) < 0.01


class TestAdoptionLevels:
    def test_strong_threshold(self, analyser):
        assert analyser._adoption_level(75.0) == "Strong"
        assert analyser._adoption_level(100.0) == "Strong"

    def test_moderate_threshold(self, analyser):
        assert analyser._adoption_level(50.0) == "Moderate"
        assert analyser._adoption_level(74.9) == "Moderate"

    def test_emerging_threshold(self, analyser):
        assert analyser._adoption_level(25.0) == "Emerging"
        assert analyser._adoption_level(49.9) == "Emerging"

    def test_low_threshold(self, analyser):
        assert analyser._adoption_level(0.0) == "Low"
        assert analyser._adoption_level(24.9) == "Low"

    def test_boundary_exactness_75(self, analyser):
        assert analyser._adoption_level(74.99) == "Moderate"
        assert analyser._adoption_level(75.0) == "Strong"

    def test_boundary_exactness_50(self, analyser):
        assert analyser._adoption_level(49.99) == "Emerging"
        assert analyser._adoption_level(50.0) == "Moderate"

    def test_boundary_exactness_25(self, analyser):
        assert analyser._adoption_level(24.99) == "Low"
        assert analyser._adoption_level(25.0) == "Emerging"


class TestArticleAnalysis:
    def test_to_dict_has_required_keys(self, analyser, gse_article):
        result = analyser.analyse_article(gse_article)
        d = result.to_dict()
        required = ["article_id", "title", "url", "author", "gse_adoption_score",
                    "gse_level", "signal_count", "dominant_dimension", "signals"]
        for key in required:
            assert key in d, f"Missing key: {key}"

    def test_dominant_dimension_is_valid(self, analyser, gse_article):
        result = analyser.analyse_article(gse_article)
        valid = {"Energy Efficiency", "Carbon Awareness", "Hardware Efficiency",
                 "Green Practices", "Measurement & Tooling"}
        assert result.dominant_dimension in valid

    def test_empty_article_does_not_crash(self, analyser):
        empty = {"id": 99, "title": "", "url": "", "author": "",
                 "published_at": "", "body_markdown": "", "tag_list": []}
        result = analyser.analyse_article(empty)
        assert result.gse_adoption_score >= 0

    def test_gse_level_only_four_values(self, analyser, gse_article, minimal_article):
        valid_levels = {"Low", "Emerging", "Moderate", "Strong"}
        for article in [gse_article, minimal_article]:
            result = analyser.analyse_article(article)
            assert result.gse_level in valid_levels


class TestSensitivityAnalysis:
    def test_sensitivity_keys_present(self, analyser, gse_article):
        result = analyser.analyse_article(gse_article)
        sens = analyser.sensitivity_analysis(result)
        assert "baseline_score" in sens
        assert "weight_deltas" in sens
        assert "max_abs_delta" in sens

    def test_sensitivity_all_dimensions_covered(self, analyser, gse_article):
        result = analyser.analyse_article(gse_article)
        sens = analyser.sensitivity_analysis(result)
        for dim in GSEAS_WEIGHTS:
            assert dim in sens["weight_deltas"]

    def test_sensitivity_baseline_matches_score(self, analyser, gse_article):
        result = analyser.analyse_article(gse_article)
        sens = analyser.sensitivity_analysis(result)
        assert sens["baseline_score"] == result.gse_adoption_score

    def test_sensitivity_max_delta_is_small(self, analyser, gse_article):
        """No single dimension should swing the composite by more than 10 points."""
        result = analyser.analyse_article(gse_article)
        sens = analyser.sensitivity_analysis(result, perturbation=0.05)
        assert sens["max_abs_delta"] < 10.0


class TestCorpusAnalysis:
    def test_corpus_report_fields(self, analyser, gse_article, minimal_article):
        results, report = analyser.analyse_corpus([gse_article, minimal_article])
        assert report.total_articles == 2
        assert report.mean_adoption_score >= 0
        assert len(report.dimension_means) == 5
        assert isinstance(report.level_distribution, dict)

    def test_corpus_top_articles_ordered(self, analyser, gse_article, minimal_article):
        results, report = analyser.analyse_corpus([gse_article, minimal_article])
        if len(report.top_articles) > 1:
            scores = [a["gse_adoption_score"] for a in report.top_articles]
            assert scores == sorted(scores, reverse=True)

    def test_corpus_level_distribution_valid_keys(self, analyser, gse_article, minimal_article):
        results, report = analyser.analyse_corpus([gse_article, minimal_article])
        valid = {"Low", "Emerging", "Moderate", "Strong"}
        for key in report.level_distribution:
            assert key in valid

    def test_singleton(self):
        a1 = get_analyser()
        a2 = get_analyser()
        assert a1 is a2


class TestSoftwareRelevanceFilter:
    """Tests for the software-context relevance filter, added after observing
    real-world tag-based corpus contamination from non-software sustainability
    content (e.g. agriculture/farming articles matched by the broad 'carbon'
    and 'sustainability' dev.to tags)."""

    def test_gse_article_marked_relevant(self, analyser, gse_article):
        result = analyser.analyse_article(gse_article)
        assert result.is_software_relevant is True

    def test_offtopic_article_marked_not_relevant(self, analyser, offtopic_article):
        result = analyser.analyse_article(offtopic_article)
        assert result.is_software_relevant is False

    def test_offtopic_article_still_gets_a_score(self, analyser, offtopic_article):
        """Off-topic articles are flagged, not silently zeroed — full
        transparency requires the score to remain inspectable."""
        result = analyser.analyse_article(offtopic_article)
        assert result.gse_adoption_score > 0

    def test_tool_specific_article_relevant_via_signal_alone(self, analyser, tool_specific_article):
        """An article with no generic software vocabulary, but a genuine
        green-software tool name (CodeCarbon, RAPL), should still be marked
        relevant on the strength of that signal alone."""
        result = analyser.analyse_article(tool_specific_article)
        assert result.is_software_relevant is True

    def test_minimal_article_relevant_despite_zero_gse_score(self, analyser, minimal_article):
        """A REST API tutorial is software-relevant even though it has no
        GSE content at all — relevance and adoption score are independent."""
        result = analyser.analyse_article(minimal_article)
        assert result.is_software_relevant is True

    def test_to_dict_includes_relevance_flag(self, analyser, offtopic_article):
        result = analyser.analyse_article(offtopic_article)
        d = result.to_dict()
        assert "is_software_relevant" in d
        assert d["is_software_relevant"] is False


class TestRelevanceFilterCorpusAggregation:
    """Tests that corpus-level statistics correctly exclude off-topic articles
    while preserving them in the raw results list for auditability."""

    def test_excluded_count_reported(self, analyser, gse_article, offtopic_article):
        results, report = analyser.analyse_corpus([gse_article, offtopic_article])
        assert report.excluded_off_topic == 1

    def test_total_articles_includes_offtopic(self, analyser, gse_article, offtopic_article):
        """total_articles counts the full corpus, not just the relevant subset."""
        results, report = analyser.analyse_corpus([gse_article, offtopic_article])
        assert report.total_articles == 2

    def test_offtopic_excluded_from_top_articles(self, analyser, gse_article, offtopic_article):
        results, report = analyser.analyse_corpus([gse_article, offtopic_article])
        top_ids = [a["article_id"] for a in report.top_articles]
        assert offtopic_article["id"] not in top_ids

    def test_offtopic_excluded_from_mean_score(self, analyser, offtopic_article, tool_specific_article):
        """Mean score should reflect only the relevant article, not be dragged
        down by the off-topic one."""
        results, report = analyser.analyse_corpus([offtopic_article, tool_specific_article])
        relevant_result = next(r for r in results if r.article_id == tool_specific_article["id"])
        assert report.mean_adoption_score == relevant_result.gse_adoption_score

    def test_results_list_still_contains_offtopic_article(self, analyser, gse_article, offtopic_article):
        """The raw results list (as opposed to the aggregate report) must
        still include off-topic articles — nothing is silently dropped."""
        results, report = analyser.analyse_corpus([gse_article, offtopic_article])
        assert len(results) == 2

    def test_falls_back_to_full_set_if_all_offtopic(self, analyser, offtopic_article):
        """If every article in a small batch is off-topic, the report should
        still surface results rather than returning an empty report."""
        results, report = analyser.analyse_corpus([offtopic_article])
        assert report.total_articles == 1
        assert report.excluded_off_topic == 1
        assert report.mean_adoption_score > 0  # falls back to using the full set
