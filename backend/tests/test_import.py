"""Tests for the import feature: match type recommender, import service, and import API."""

import io
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.database import Base, get_db
from app.main import app
from app.models.models import Account, Import, ImportedSearchTerm
from app.services.match_type_recommender import (
    recommend_match_type, contains_location_signal, contains_commercial_intent,
)
from app.services.import_service import (
    parse_csv_content, detect_columns, extract_search_term_data, analyze_search_term,
    _parse_numeric, _parse_int,
)

TEST_DB_URL = "sqlite+aiosqlite:///./test_kwplanner.db"
test_engine = create_async_engine(TEST_DB_URL, echo=False)
test_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with test_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# =============================================================================
# Match Type Recommender Tests
# =============================================================================

class TestLocationSignal:
    def test_near_me(self):
        assert contains_location_signal("pool builder near me") is True

    def test_city_name(self):
        assert contains_location_signal("pool builder houston") is True

    def test_state_name(self):
        assert contains_location_signal("pool company texas") is True

    def test_no_location(self):
        assert contains_location_signal("pool builder") is False

    def test_in_city_pattern(self):
        assert contains_location_signal("pool builder in dallas") is True

    def test_nearby(self):
        assert contains_location_signal("pool companies nearby") is True


class TestCommercialIntent:
    def test_cost(self):
        assert contains_commercial_intent("pool builder cost") is True

    def test_price(self):
        assert contains_commercial_intent("inground pool price") is True

    def test_hire(self):
        assert contains_commercial_intent("hire pool contractor") is True

    def test_no_intent(self):
        assert contains_commercial_intent("swimming pool") is False

    def test_install(self):
        assert contains_commercial_intent("pool installation") is True

    def test_reviews(self):
        assert contains_commercial_intent("best pool builder reviews") is True


class TestRecommendMatchType:
    def test_converting_query_exact(self):
        mt, reason = recommend_match_type("pool builder near me", clicks=5, conversions=2)
        assert mt == "EXACT"
        assert "Converting" in reason

    def test_high_ctr_specific_exact(self):
        mt, reason = recommend_match_type(
            "custom gunite pool builder houston",
            clicks=15, ctr=0.05, impressions=300
        )
        assert mt == "EXACT"

    def test_high_ctr_broad_phrase(self):
        mt, reason = recommend_match_type("pool", clicks=20, ctr=0.04)
        assert mt == "PHRASE"

    def test_longtail_commercial_exact(self):
        mt, reason = recommend_match_type(
            "how much does pool installation cost", clicks=2
        )
        assert mt == "EXACT"
        assert "Long-tail" in reason

    def test_location_query_exact(self):
        mt, reason = recommend_match_type(
            "pools near me", clicks=3
        )
        assert mt == "EXACT"
        assert "Location" in reason

    def test_moderate_data_phrase(self):
        mt, reason = recommend_match_type("pool repair", clicks=7)
        assert mt == "PHRASE"
        assert "Moderate" in reason

    def test_low_data_generic_skip(self):
        mt, reason = recommend_match_type("pool", clicks=2)
        assert mt == "SKIP"
        assert "generic" in reason.lower()

    def test_default_phrase(self):
        mt, reason = recommend_match_type("pool maintenance service", clicks=3)
        assert mt == "PHRASE"
        assert "Default" in reason

    def test_zero_data_generic_skip(self):
        mt, reason = recommend_match_type("spa", clicks=0)
        assert mt == "SKIP"

    def test_single_conversion_always_exact(self):
        mt, _ = recommend_match_type("random query thing", conversions=1)
        assert mt == "EXACT"


# =============================================================================
# Import Service Tests
# =============================================================================

class TestParseNumeric:
    def test_float(self):
        assert _parse_numeric(3.14) == 3.14

    def test_formatted_currency(self):
        assert _parse_numeric("$1,234.56") == 1234.56

    def test_percentage(self):
        assert _parse_numeric("5.98%") == 5.98

    def test_none(self):
        assert _parse_numeric(None) == 0

    def test_dash(self):
        assert _parse_numeric("--") == 0

    def test_int_string(self):
        assert _parse_numeric("42") == 42.0


class TestParseCSV:
    def test_basic_csv(self):
        content = b"Search term,Clicks,Impressions\npool builder,10,100\npool repair,5,50\n"
        headers, rows = parse_csv_content(content)
        assert headers == ["Search term", "Clicks", "Impressions"]
        assert len(rows) == 2
        assert rows[0]["Search term"] == "pool builder"

    def test_csv_with_bom(self):
        content = b"\xef\xbb\xbfSearch term,Clicks\npool builder,10\n"
        headers, rows = parse_csv_content(content)
        assert "Search term" in headers
        assert len(rows) == 1

    def test_csv_skips_total_rows(self):
        content = b"Search term,Clicks\npool builder,10\nTotal: --,15\n"
        headers, rows = parse_csv_content(content)
        assert len(rows) == 1


class TestDetectColumns:
    def test_search_term_detection(self):
        headers = ["Search term", "Campaign", "Ad Group", "Clicks", "Impressions", "Cost"]
        mapping = detect_columns(headers, "search_terms")
        assert mapping["search_term"] == "Search term"
        assert mapping["campaign"] == "Campaign"
        assert mapping["clicks"] == "Clicks"

    def test_keyword_detection(self):
        headers = ["Keyword", "Campaign", "Ad Group", "Match Type", "Quality Score"]
        mapping = detect_columns(headers, "keywords")
        assert mapping["keyword"] == "Keyword"
        assert mapping["match_type"] == "Match Type"
        assert mapping["quality_score"] == "Quality Score"

    def test_fuzzy_matching(self):
        headers = ["Search Terms", "Campaign Name", "Ad group name", "Match type"]
        mapping = detect_columns(headers, "search_terms")
        assert "campaign" in mapping


class TestAnalyzeSearchTerm:
    def test_converting_term(self):
        data = {
            "search_term": "pool builder near me houston",
            "campaign": "Pool Campaign",
            "ad_group": "Builder",
            "matched_keyword": "pool builder",
            "match_type_triggered": "Phrase",
            "impressions": 100,
            "clicks": 15,
            "cost": 75.0,
            "conversions": 2.0,
            "conv_rate": 0.133,
            "ctr": 0.15,
        }
        result = analyze_search_term(data)
        assert result["recommended_match_type"] == "EXACT"
        assert result["relevance_score"] == 25

    def test_negative_term_flagged(self):
        data = {
            "search_term": "pool table felt replacement",
            "campaign": "Pool Campaign",
            "ad_group": "Builder",
            "matched_keyword": "pool",
            "match_type_triggered": "Broad",
            "impressions": 50,
            "clicks": 8,
            "cost": 40.0,
            "conversions": 0,
            "conv_rate": 0,
            "ctr": 0.16,
        }
        result = analyze_search_term(data)
        assert result["recommended_match_type"] == "NEGATIVE"
        assert result["is_negative_candidate"] is True
        assert result["priority"] == "SKIP"

    def test_duplicate_detection(self):
        data = {
            "search_term": "pool builder",
            "campaign": "", "ad_group": "", "matched_keyword": "",
            "match_type_triggered": "", "impressions": 10, "clicks": 5,
            "cost": 25.0, "conversions": 0, "conv_rate": 0, "ctr": 0.5,
        }
        existing = {"pool builder"}
        result = analyze_search_term(data, existing_keywords=existing)
        assert result["is_duplicate"] is True

    def test_empty_search_term(self):
        data = {
            "search_term": "",
            "campaign": "", "ad_group": "", "matched_keyword": "",
            "match_type_triggered": "", "impressions": 0, "clicks": 0,
            "cost": 0, "conversions": 0, "conv_rate": 0, "ctr": 0,
        }
        result = analyze_search_term(data)
        assert result["recommended_match_type"] == "SKIP"


class TestExtractSearchTermData:
    def test_basic_extraction(self):
        row = {
            "Search term": "pool builder near me",
            "Clicks": "15",
            "Impressions": "200",
            "Cost": "$75.50",
            "Conversions": "2.0",
            "Conv. rate": "13.33%",
        }
        mapping = {
            "search_term": "Search term",
            "clicks": "Clicks",
            "impressions": "Impressions",
            "cost": "Cost",
            "conversions": "Conversions",
            "conv_rate": "Conv. rate",
        }
        data = extract_search_term_data(row, mapping)
        assert data["search_term"] == "pool builder near me"
        assert data["clicks"] == 15
        assert data["cost"] == 75.50
        assert data["conversions"] == 2.0
        assert abs(data["conv_rate"] - 0.1333) < 0.001

    def test_computed_ctr(self):
        row = {"Search term": "test", "Clicks": "10", "Impressions": "100"}
        mapping = {"search_term": "Search term", "clicks": "Clicks", "impressions": "Impressions"}
        data = extract_search_term_data(row, mapping)
        assert data["ctr"] == 0.1


# =============================================================================
# Import API Tests
# =============================================================================

class TestImportAPI:
    @pytest.mark.asyncio
    async def test_upload_csv(self, client):
        csv_content = (
            b"Search term,Campaign,Ad Group,Keyword,Match type,Impressions,Clicks,Cost,Conversions\n"
            b"pool builder near me,Pool Campaign,Builder Group,pool builder,Phrase,100,15,75.00,2\n"
            b"hot tub sale,Hot Tub Campaign,Sales,hot tub,Exact,50,8,40.00,1\n"
        )
        response = await client.post(
            "/api/import/upload",
            files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")},
            data={"file_type": "search_terms"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["row_count"] == 2
        assert data["upload_id"] > 0
        assert len(data["preview"]) == 2
        assert "search_term" in data["column_mapping"]

    @pytest.mark.asyncio
    async def test_upload_invalid_file_type(self, client):
        response = await client.post(
            "/api/import/upload",
            files={"file": ("test.pdf", io.BytesIO(b"not csv"), "application/pdf")},
            data={"file_type": "search_terms"},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_full_import_flow(self, client):
        # Step 1: Upload
        csv_content = (
            b"Search term,Campaign,Ad Group,Keyword,Match type,Impressions,Clicks,Cost,Conversions,Conv. rate\n"
            b"pool builder near me,Pool - Search,Builder,pool builder,Phrase,200,20,100.00,3,15%\n"
            b"pool table repair,Pool - Search,Builder,pool,Broad,50,8,40.00,0,0%\n"
            b"custom gunite pool cost houston,Pool - Search,Cost,pool cost,Phrase,80,12,60.00,2,16.67%\n"
        )
        upload_resp = await client.post(
            "/api/import/upload",
            files={"file": ("report.csv", io.BytesIO(csv_content), "text/csv")},
            data={"file_type": "search_terms"},
        )
        assert upload_resp.status_code == 200
        upload_data = upload_resp.json()
        upload_id = upload_data["upload_id"]

        # Step 2: Confirm
        confirm_resp = await client.post("/api/import/confirm", json={
            "upload_id": upload_id,
            "column_mapping": upload_data["column_mapping"],
            "account_name": "Test Pool Company",
        })
        assert confirm_resp.status_code == 200
        assert confirm_resp.json()["status"] == "confirmed"

        # Step 3: Analyze
        analyze_resp = await client.post(f"/api/import/analyze?upload_id={upload_id}")
        assert analyze_resp.status_code == 200
        assert analyze_resp.json()["status"] == "analyzed"

        # Step 4: Get results
        results_resp = await client.get(f"/api/import/{upload_id}/results")
        assert results_resp.status_code == 200
        results = results_resp.json()
        assert results["total"] == 3

        # Verify match type recommendations
        items = {r["search_term"]: r for r in results["items"]}

        # Converting query -> EXACT
        assert items["pool builder near me"]["recommended_match_type"] == "EXACT"

        # Pool table -> NEGATIVE (negative term)
        assert items["pool table repair"]["recommended_match_type"] == "NEGATIVE"
        assert items["pool table repair"]["is_negative_candidate"] is True

        # Commercial + location -> EXACT
        assert items["custom gunite pool cost houston"]["recommended_match_type"] == "EXACT"

    @pytest.mark.asyncio
    async def test_list_imports(self, client):
        # Upload a file first
        csv_content = b"Search term,Clicks\ntest,5\n"
        await client.post(
            "/api/import/upload",
            files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")},
            data={"file_type": "search_terms"},
        )

        resp = await client.get("/api/import/list/all")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    @pytest.mark.asyncio
    async def test_get_import(self, client):
        csv_content = b"Search term,Clicks\ntest,5\n"
        upload_resp = await client.post(
            "/api/import/upload",
            files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")},
            data={"file_type": "search_terms"},
        )
        upload_id = upload_resp.json()["upload_id"]

        resp = await client.get(f"/api/import/{upload_id}")
        assert resp.status_code == 200
        assert resp.json()["file_name"] == "test.csv"

    @pytest.mark.asyncio
    async def test_get_import_not_found(self, client):
        resp = await client.get("/api/import/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_import(self, client):
        csv_content = b"Search term,Clicks\ntest,5\n"
        upload_resp = await client.post(
            "/api/import/upload",
            files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")},
            data={"file_type": "search_terms"},
        )
        upload_id = upload_resp.json()["upload_id"]

        del_resp = await client.delete(f"/api/import/{upload_id}")
        assert del_resp.status_code == 200

        # Verify it's gone
        get_resp = await client.get(f"/api/import/{upload_id}")
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_filter_results_by_priority(self, client):
        csv_content = (
            b"Search term,Campaign,Clicks,Conversions,Impressions\n"
            b"pool builder near me,Campaign,20,3,200\n"
            b"spa,Campaign,1,0,10\n"
        )
        upload_resp = await client.post(
            "/api/import/upload",
            files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")},
            data={"file_type": "search_terms"},
        )
        upload_id = upload_resp.json()["upload_id"]

        await client.post("/api/import/confirm", json={
            "upload_id": upload_id,
            "column_mapping": upload_resp.json()["column_mapping"],
            "account_name": "Filter Test",
        })
        await client.post(f"/api/import/analyze?upload_id={upload_id}")

        # Filter by SKIP priority
        resp = await client.get(f"/api/import/{upload_id}/results?priority=SKIP")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_export_results_csv(self, client):
        csv_content = (
            b"Search term,Campaign,Clicks,Conversions,Impressions\n"
            b"pool builder near me,Campaign,20,3,200\n"
        )
        upload_resp = await client.post(
            "/api/import/upload",
            files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")},
            data={"file_type": "search_terms"},
        )
        upload_id = upload_resp.json()["upload_id"]

        await client.post("/api/import/confirm", json={
            "upload_id": upload_id,
            "column_mapping": upload_resp.json()["column_mapping"],
            "account_name": "Export Test",
        })
        await client.post(f"/api/import/analyze?upload_id={upload_id}")

        resp = await client.post(f"/api/import/{upload_id}/export")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "Search Term" in resp.text
