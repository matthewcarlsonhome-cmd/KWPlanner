"""Tests for the scoring engine."""

import pytest
from app.services.scorer import (
    score_volume,
    score_competition,
    score_cpc_efficiency,
    score_relevance,
    classify_priority,
    detect_seasonality,
    suggest_match_type,
    suggest_ad_group,
    score_keyword,
)


class TestVolumeScore:
    def test_high_volume(self):
        assert score_volume(500) == 25
        assert score_volume(1000) == 25

    def test_medium_high_volume(self):
        assert score_volume(200) == 20
        assert score_volume(499) == 20

    def test_medium_volume(self):
        assert score_volume(100) == 15
        assert score_volume(199) == 15

    def test_low_volume(self):
        assert score_volume(50) == 10
        assert score_volume(99) == 10

    def test_very_low_volume(self):
        assert score_volume(10) == 5
        assert score_volume(49) == 5

    def test_zero_volume(self):
        assert score_volume(0) == 0
        assert score_volume(9) == 0

    def test_none_volume(self):
        assert score_volume(None) == 0


class TestCompetitionScore:
    def test_low_competition(self):
        assert score_competition(0) == 25
        assert score_competition(33) == 25

    def test_medium_competition(self):
        assert score_competition(34) == 15
        assert score_competition(66) == 15

    def test_high_competition(self):
        assert score_competition(67) == 10
        assert score_competition(100) == 10

    def test_none_competition(self):
        assert score_competition(None) == 15


class TestCpcEfficiency:
    def test_much_cheaper(self):
        # Idea CPC = $1.50, account avg = $5.00 → ratio 0.3 → score 25
        assert score_cpc_efficiency(1_000_000, 2_000_000, 5.00) == 25

    def test_somewhat_cheaper(self):
        # Idea CPC = $3.50, account avg = $5.00 → ratio 0.7 → score 20
        assert score_cpc_efficiency(2_000_000, 5_000_000, 5.00) == 20

    def test_about_same(self):
        # Idea CPC = $5.00, account avg = $5.00 → ratio 1.0 → score 15
        assert score_cpc_efficiency(4_000_000, 6_000_000, 5.00) == 15

    def test_more_expensive(self):
        # Idea CPC = $7.50, account avg = $5.00 → ratio 1.5 → score 10
        assert score_cpc_efficiency(5_000_000, 10_000_000, 5.00) == 10

    def test_much_more_expensive(self):
        # Idea CPC = $12.50, account avg = $5.00 → ratio 2.5 → score 5
        assert score_cpc_efficiency(10_000_000, 15_000_000, 5.00) == 5

    def test_missing_data(self):
        assert score_cpc_efficiency(None, None, 5.00) == 15
        assert score_cpc_efficiency(1_000_000, 2_000_000, None) == 15


class TestRelevanceScore:
    def test_high_relevance_pool_builder(self):
        score, category = score_relevance("pool builder near me")
        assert score == 25
        assert category == "high_relevance"

    def test_high_relevance_hot_tub(self):
        score, category = score_relevance("hot tub installation service")
        assert score == 25
        assert category == "high_relevance"

    def test_high_relevance_swimming_pool(self):
        score, category = score_relevance("swimming pool design ideas")
        assert score == 25
        assert category == "high_relevance"

    def test_medium_relevance(self):
        score, category = score_relevance("backyard landscaping ideas")
        assert score == 15
        assert category == "medium_relevance"

    def test_low_relevance(self):
        score, category = score_relevance("random search term")
        assert score == 8
        assert category == "low_relevance"

    def test_negative_pool_table(self):
        """Pool table should be flagged as negative, not positive."""
        score, category = score_relevance("pool table felt replacement")
        assert score == 0
        assert category == "negative_candidate"

    def test_negative_carpool(self):
        score, category = score_relevance("carpool lane rules california")
        assert score == 0
        assert category == "negative_candidate"

    def test_negative_diy(self):
        score, category = score_relevance("diy pool repair tutorial")
        assert score == 0
        assert category == "negative_candidate"

    def test_negative_jobs(self):
        score, category = score_relevance("pool cleaning jobs near me")
        assert score == 0
        assert category == "negative_candidate"

    def test_negative_wins_over_positive(self):
        """When both negative and positive terms present, negative wins."""
        score, category = score_relevance("pool table repair near me")
        assert score == 0
        assert category == "negative_candidate"

    def test_negative_amazon(self):
        score, category = score_relevance("amazon pool filter replacement")
        assert score == 0
        assert category == "negative_candidate"


class TestPriority:
    def test_high(self):
        assert classify_priority(75) == "HIGH"
        assert classify_priority(100) == "HIGH"

    def test_medium(self):
        assert classify_priority(50) == "MEDIUM"
        assert classify_priority(74) == "MEDIUM"

    def test_low(self):
        assert classify_priority(25) == "LOW"
        assert classify_priority(49) == "LOW"

    def test_skip(self):
        assert classify_priority(0) == "SKIP"
        assert classify_priority(24) == "SKIP"


class TestSeasonality:
    def test_seasonal_pattern(self):
        """Pool construction keywords peak in spring."""
        volumes = [
            {"month": 1, "year": 2026, "searches": 100},
            {"month": 2, "year": 2026, "searches": 150},
            {"month": 3, "year": 2026, "searches": 400},
            {"month": 4, "year": 2026, "searches": 500},
            {"month": 5, "year": 2026, "searches": 450},
            {"month": 6, "year": 2026, "searches": 350},
            {"month": 7, "year": 2026, "searches": 200},
            {"month": 8, "year": 2026, "searches": 150},
            {"month": 9, "year": 2026, "searches": 100},
            {"month": 10, "year": 2026, "searches": 80},
            {"month": 11, "year": 2026, "searches": 70},
            {"month": 12, "year": 2026, "searches": 90},
        ]
        is_seasonal, peak = detect_seasonality(volumes)
        assert is_seasonal is True
        assert peak == "April"

    def test_steady_pattern(self):
        """Even searches year-round."""
        volumes = [
            {"month": i, "year": 2026, "searches": 200}
            for i in range(1, 13)
        ]
        is_seasonal, peak = detect_seasonality(volumes)
        assert is_seasonal is False

    def test_empty_data(self):
        is_seasonal, peak = detect_seasonality(None)
        assert is_seasonal is False
        assert peak is None

    def test_hot_tub_winter_peak(self):
        """Hot tub keywords peak Oct-Dec."""
        volumes = [
            {"month": 1, "year": 2026, "searches": 200},
            {"month": 2, "year": 2026, "searches": 150},
            {"month": 3, "year": 2026, "searches": 100},
            {"month": 4, "year": 2026, "searches": 80},
            {"month": 5, "year": 2026, "searches": 60},
            {"month": 6, "year": 2026, "searches": 50},
            {"month": 7, "year": 2026, "searches": 50},
            {"month": 8, "year": 2026, "searches": 80},
            {"month": 9, "year": 2026, "searches": 150},
            {"month": 10, "year": 2026, "searches": 400},
            {"month": 11, "year": 2026, "searches": 500},
            {"month": 12, "year": 2026, "searches": 450},
        ]
        is_seasonal, peak = detect_seasonality(volumes)
        assert is_seasonal is True
        assert peak == "November"


class TestMatchType:
    def test_short_keyword(self):
        assert suggest_match_type("pool builder") == "PHRASE"

    def test_long_keyword(self):
        assert suggest_match_type("custom gunite pool builder near me") == "EXACT"


class TestAdGroupMatcher:
    def test_good_match(self):
        ad_groups = {
            "Pool Builder": ["pool builder", "pool contractor", "pool company"],
            "Pool Cost": ["pool cost", "pool price", "pool estimate"],
        }
        result = suggest_ad_group("pool builder near me", ad_groups)
        assert result == "Pool Builder"

    def test_cost_match(self):
        ad_groups = {
            "Pool Builder": ["pool builder", "pool contractor"],
            "Pool Cost": ["pool cost", "pool price", "how much does a pool cost"],
        }
        result = suggest_ad_group("pool cost estimate", ad_groups)
        assert result == "Pool Cost"

    def test_no_match_creates_new(self):
        ad_groups = {
            "Pool Builder": ["pool builder", "pool contractor"],
        }
        result = suggest_ad_group("hot tub installation", ad_groups)
        assert result.startswith("NEW AD GROUP:")

    def test_empty_ad_groups(self):
        result = suggest_ad_group("pool builder", {})
        assert result.startswith("NEW AD GROUP:")


class TestFullScoring:
    def test_high_priority_keyword(self):
        """Pool builder with good volume and low competition should score HIGH."""
        result = score_keyword(
            keyword_text="pool builder near me",
            avg_monthly_searches=500,
            competition_index=25,
            low_cpc_micros=2_000_000,
            high_cpc_micros=5_000_000,
            account_avg_cpc=5.00,
        )
        assert result["priority"] == "HIGH"
        assert result["total_score"] >= 75
        assert result["relevance_category"] == "high_relevance"

    def test_negative_keyword(self):
        """Pool table should be SKIP with negative flag."""
        result = score_keyword(
            keyword_text="pool table felt replacement",
            avg_monthly_searches=800,
            competition_index=10,
            low_cpc_micros=500_000,
            high_cpc_micros=1_500_000,
            account_avg_cpc=5.00,
        )
        assert result["relevance_category"] == "negative_candidate"
        assert result["relevance_score"] == 0
        # Negative candidates are always SKIP regardless of other scores
        assert result["priority"] == "SKIP"

    def test_medium_priority_keyword(self):
        """Tangential keyword with decent volume."""
        result = score_keyword(
            keyword_text="backyard landscaping ideas",
            avg_monthly_searches=200,
            competition_index=50,
            low_cpc_micros=1_500_000,
            high_cpc_micros=3_000_000,
            account_avg_cpc=3.00,
        )
        assert result["priority"] in ("MEDIUM", "LOW")
        assert result["relevance_category"] == "medium_relevance"

    def test_scoring_with_seasonality(self):
        """Verify seasonal detection in full scoring."""
        volumes = [
            {"month": i, "year": 2026, "searches": 100 + (300 if i in (4, 5, 6) else 0)}
            for i in range(1, 13)
        ]
        result = score_keyword(
            keyword_text="pool installation cost",
            avg_monthly_searches=300,
            competition_index=30,
            low_cpc_micros=2_000_000,
            high_cpc_micros=6_000_000,
            account_avg_cpc=5.00,
            monthly_volumes=volumes,
        )
        assert result["is_seasonal"] is True
