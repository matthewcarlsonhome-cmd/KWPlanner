"""Integration tests for the API endpoints."""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.database import Base, get_db
from app.main import app
from app.models.models import Account, ResearchRun, KeywordIdea, Decision, SeedKeyword, NegativeFlag
from datetime import datetime

# Test database
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
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def sample_account():
    async with test_session() as db:
        account = Account(
            google_ads_id="123-456-7890",
            name="Test Pool Company",
            is_active=True,
            avg_cpc=3.50,
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)
        return account


@pytest_asyncio.fixture
async def sample_run_with_ideas(sample_account):
    async with test_session() as db:
        account = await db.get(Account, sample_account.id)

        run = ResearchRun(
            account_id=account.id,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            status="completed",
            seed_count=5,
            ideas_generated=3,
            ideas_high=1,
            ideas_medium=1,
            ideas_low=1,
        )
        db.add(run)
        await db.flush()

        # Add seeds
        seed = SeedKeyword(
            run_id=run.id,
            keyword="pool builder",
            match_type="EXACT",
            conversions=15.0,
            clicks=230,
        )
        db.add(seed)

        # Add keyword ideas
        ideas_data = [
            {"keyword_text": "gunite pool builder near me", "avg_monthly_searches": 320,
             "competition": "MEDIUM", "competition_index": 55, "total_score": 80,
             "priority": "HIGH", "volume_score": 20, "competition_score": 15,
             "cpc_score": 20, "relevance_score": 25, "relevance_category": "high_relevance",
             "suggested_match_type": "EXACT", "suggested_ad_group": "Pool Builder"},
            {"keyword_text": "backyard pool design", "avg_monthly_searches": 180,
             "competition": "LOW", "competition_index": 25, "total_score": 60,
             "priority": "MEDIUM", "volume_score": 15, "competition_score": 25,
             "cpc_score": 10, "relevance_score": 15, "relevance_category": "medium_relevance",
             "suggested_match_type": "PHRASE", "suggested_ad_group": "Pool Design"},
            {"keyword_text": "pool table repair", "avg_monthly_searches": 400,
             "competition": "LOW", "competition_index": 10, "total_score": 30,
             "priority": "LOW", "volume_score": 20, "competition_score": 25,
             "cpc_score": 5, "relevance_score": 0, "relevance_category": "negative_candidate",
             "suggested_match_type": "PHRASE", "suggested_ad_group": "General"},
        ]

        idea_ids = []
        for data in ideas_data:
            idea = KeywordIdea(run_id=run.id, account_id=account.id, **data)
            db.add(idea)
            await db.flush()
            idea_ids.append(idea.id)

        # Add a negative flag for pool table
        db.add(NegativeFlag(
            keyword_idea_id=idea_ids[2],
            account_id=account.id,
            keyword_text="pool table repair",
            reason="Matches negative pattern: pool table",
            suggested_scope="CAMPAIGN",
        ))

        await db.commit()
        return {"account": account, "run": run, "idea_ids": idea_ids}


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health(self, client):
        response = await client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestAccounts:
    @pytest.mark.asyncio
    async def test_list_accounts_empty(self, client):
        response = await client.get("/api/accounts")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_accounts(self, client, sample_account):
        response = await client.get("/api/accounts")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Test Pool Company"
        assert data[0]["google_ads_id"] == "123-456-7890"

    @pytest.mark.asyncio
    async def test_get_account(self, client, sample_account):
        response = await client.get(f"/api/accounts/{sample_account.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Pool Company"

    @pytest.mark.asyncio
    async def test_get_account_not_found(self, client):
        response = await client.get("/api/accounts/9999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_sync_accounts(self, client):
        response = await client.post("/api/accounts/sync")
        assert response.status_code == 200
        data = response.json()
        assert data["synced"] > 0


class TestResults:
    @pytest.mark.asyncio
    async def test_get_results(self, client, sample_run_with_ideas):
        account = sample_run_with_ideas["account"]
        response = await client.get(f"/api/results/{account.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    @pytest.mark.asyncio
    async def test_filter_by_priority(self, client, sample_run_with_ideas):
        account = sample_run_with_ideas["account"]
        response = await client.get(f"/api/results/{account.id}?priority=HIGH")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["keyword_text"] == "gunite pool builder near me"

    @pytest.mark.asyncio
    async def test_search_filter(self, client, sample_run_with_ideas):
        account = sample_run_with_ideas["account"]
        response = await client.get(f"/api/results/{account.id}?search=gunite")
        data = response.json()
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_get_seeds(self, client, sample_run_with_ideas):
        account = sample_run_with_ideas["account"]
        response = await client.get(f"/api/results/{account.id}/seeds")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["keyword"] == "pool builder"

    @pytest.mark.asyncio
    async def test_get_negatives(self, client, sample_run_with_ideas):
        account = sample_run_with_ideas["account"]
        response = await client.get(f"/api/results/{account.id}/negatives")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["keyword_text"] == "pool table repair"

    @pytest.mark.asyncio
    async def test_no_results_for_unknown_account(self, client):
        response = await client.get("/api/results/9999")
        data = response.json()
        assert data["total"] == 0


class TestDecisions:
    @pytest.mark.asyncio
    async def test_approve_keywords(self, client, sample_run_with_ideas):
        idea_ids = sample_run_with_ideas["idea_ids"]
        response = await client.post("/api/decisions", json={
            "keyword_idea_ids": [idea_ids[0]],
            "decision": "approved",
            "decided_by": "matthew@sspdigital.com",
            "notes": "Good keyword for Houston market",
        })
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["decision"] == "approved"

    @pytest.mark.asyncio
    async def test_bulk_reject(self, client, sample_run_with_ideas):
        idea_ids = sample_run_with_ideas["idea_ids"]
        response = await client.post("/api/decisions", json={
            "keyword_idea_ids": [idea_ids[1], idea_ids[2]],
            "decision": "rejected",
        })
        assert response.status_code == 200
        assert len(response.json()) == 2

    @pytest.mark.asyncio
    async def test_invalid_decision(self, client, sample_run_with_ideas):
        response = await client.post("/api/decisions", json={
            "keyword_idea_ids": [1],
            "decision": "invalid",
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_decisions(self, client, sample_run_with_ideas):
        account = sample_run_with_ideas["account"]
        idea_ids = sample_run_with_ideas["idea_ids"]

        # Create a decision first
        await client.post("/api/decisions", json={
            "keyword_idea_ids": [idea_ids[0]],
            "decision": "approved",
        })

        response = await client.get(f"/api/decisions/{account.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1


class TestExport:
    @pytest.mark.asyncio
    async def test_export_csv(self, client, sample_run_with_ideas):
        account = sample_run_with_ideas["account"]
        response = await client.post("/api/export/google-ads-editor", json={
            "account_id": account.id,
            "priority": ["HIGH", "MEDIUM"],
            "format": "csv",
        })
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_export_excel(self, client, sample_run_with_ideas):
        response = await client.post("/api/export/all-accounts", json={
            "format": "xlsx",
            "priority": ["HIGH", "MEDIUM"],
        })
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_export_negatives(self, client, sample_run_with_ideas):
        account = sample_run_with_ideas["account"]
        response = await client.post(
            f"/api/export/negatives?account_id={account.id}"
        )
        assert response.status_code == 200


class TestSettings:
    @pytest.mark.asyncio
    async def test_get_settings(self, client):
        response = await client.get("/api/settings")
        assert response.status_code == 200
        data = response.json()
        assert data["lookback_days"] == 90
        assert data["volume_weight"] == 25

    @pytest.mark.asyncio
    async def test_update_settings(self, client):
        response = await client.put("/api/settings", json={
            "lookback_days": 60,
            "min_monthly_searches": 100,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["lookback_days"] == 60
        assert data["min_monthly_searches"] == 100


class TestResearch:
    @pytest.mark.asyncio
    async def test_research_status_idle(self, client):
        response = await client.get("/api/research/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "idle"

    @pytest.mark.asyncio
    async def test_list_runs_empty(self, client):
        response = await client.get("/api/research/runs")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_runs(self, client, sample_run_with_ideas):
        account = sample_run_with_ideas["account"]
        response = await client.get(f"/api/research/runs?account_id={account.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "completed"
