"""Google Ads API integration service."""

import asyncio
import logging
from typing import Optional, List, Dict, Any

from app.config import settings

logger = logging.getLogger(__name__)


class GoogleAdsService:
    """Wrapper around the Google Ads API client for keyword research."""

    def __init__(self, refresh_token: str):
        self.refresh_token = refresh_token
        self._client = None

    def _get_client(self):
        """Lazily initialize the Google Ads client."""
        if self._client is None:
            # Skip real client if no credentials configured
            if not settings.google_ads_developer_token:
                logger.info("No developer token configured; using mock data")
                return None
            try:
                from google.ads.googleads.client import GoogleAdsClient
                self._client = GoogleAdsClient.load_from_dict({
                    "developer_token": settings.google_ads_developer_token,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "refresh_token": self.refresh_token,
                    "login_customer_id": settings.google_ads_login_customer_id,
                    "use_proto_plus": True,
                })
            except (ImportError, Exception) as e:
                logger.warning(f"Cannot initialize Google Ads client: {e}; using mock data")
                return None
        return self._client

    async def list_accessible_accounts(self) -> List[Dict[str, str]]:
        """List all child accounts under the MCC."""
        client = self._get_client()
        if not client:
            return self._mock_accounts()

        try:
            customer_service = client.get_service("CustomerService")
            response = await asyncio.to_thread(
                customer_service.list_accessible_customers
            )

            accounts = []
            ga_service = client.get_service("GoogleAdsService")
            for resource_name in response.resource_names:
                customer_id = resource_name.split("/")[-1]
                # Skip the MCC itself
                if customer_id == settings.google_ads_login_customer_id:
                    continue
                try:
                    query = 'SELECT customer.id, customer.descriptive_name FROM customer LIMIT 1'
                    resp = await asyncio.to_thread(
                        ga_service.search,
                        customer_id=customer_id,
                        query=query,
                    )
                    for row in resp:
                        accounts.append({
                            "google_ads_id": str(row.customer.id),
                            "name": row.customer.descriptive_name or f"Account {customer_id}",
                        })
                except Exception as e:
                    logger.warning(f"Cannot access account {customer_id}: {e}")
            return accounts
        except Exception as e:
            logger.error(f"Error listing accounts: {e}")
            return self._mock_accounts()

    async def get_seed_keywords(
        self,
        customer_id: str,
        lookback_days: int = 90,
        min_conversions: float = 2.0,
        min_clicks: int = 10,
        max_seeds: int = 15,
    ) -> List[Dict[str, Any]]:
        """Extract seed keywords from an account's existing keyword performance."""
        client = self._get_client()
        if not client:
            return self._mock_seeds()

        try:
            ga_service = client.get_service("GoogleAdsService")
            query = f"""
                SELECT
                    campaign.name,
                    ad_group.name,
                    ad_group_criterion.keyword.text,
                    ad_group_criterion.keyword.match_type,
                    ad_group_criterion.quality_info.quality_score,
                    metrics.conversions,
                    metrics.clicks,
                    metrics.impressions,
                    metrics.cost_micros,
                    metrics.conversions_from_interactions_rate
                FROM keyword_view
                WHERE ad_group_criterion.status = 'ENABLED'
                    AND campaign.status = 'ENABLED'
                    AND metrics.impressions > 0
                    AND segments.date DURING LAST_{lookback_days}_DAYS
                ORDER BY metrics.conversions DESC, metrics.clicks DESC
                LIMIT 200
            """
            response = await asyncio.to_thread(
                ga_service.search, customer_id=customer_id, query=query
            )

            seeds = []
            seen = set()
            for row in response:
                kw_text = row.ad_group_criterion.keyword.text
                if kw_text.lower() in seen:
                    continue

                conversions = row.metrics.conversions
                clicks = row.metrics.clicks
                qs = row.ad_group_criterion.quality_info.quality_score

                # Tier 1: high conversions
                if conversions >= min_conversions:
                    pass
                # Tier 2: good clicks + quality score
                elif clicks >= min_clicks and qs >= 6:
                    pass
                else:
                    continue

                seen.add(kw_text.lower())
                seeds.append({
                    "keyword": kw_text,
                    "match_type": str(row.ad_group_criterion.keyword.match_type).split(".")[-1],
                    "conversions": float(conversions),
                    "clicks": int(clicks),
                    "cost": float(row.metrics.cost_micros) / 1_000_000,
                    "quality_score": int(qs) if qs else None,
                    "campaign": row.campaign.name,
                    "ad_group": row.ad_group.name,
                })
                if len(seeds) >= max_seeds:
                    break

            return seeds
        except Exception as e:
            logger.error(f"Error getting seeds for {customer_id}: {e}")
            return self._mock_seeds()

    async def get_geo_targets(self, customer_id: str) -> List[str]:
        """Get geo target constant IDs for a customer's campaigns."""
        client = self._get_client()
        if not client:
            return ["2840"]  # US fallback

        try:
            ga_service = client.get_service("GoogleAdsService")
            query = """
                SELECT
                    campaign.name,
                    campaign_criterion.location.geo_target_constant
                FROM campaign_criterion
                WHERE campaign_criterion.type = 'LOCATION'
                    AND campaign.status = 'ENABLED'
            """
            response = await asyncio.to_thread(
                ga_service.search, customer_id=customer_id, query=query
            )
            geo_ids = set()
            for row in response:
                resource = row.campaign_criterion.location.geo_target_constant
                geo_id = resource.split("/")[-1]
                geo_ids.add(geo_id)
            return list(geo_ids) if geo_ids else ["2840"]
        except Exception:
            return ["2840"]

    async def get_existing_keywords(self, customer_id: str) -> set:
        """Get all active keyword texts for deduplication."""
        client = self._get_client()
        if not client:
            return set()

        try:
            ga_service = client.get_service("GoogleAdsService")
            query = """
                SELECT
                    ad_group_criterion.keyword.text,
                    ad_group_criterion.keyword.match_type
                FROM keyword_view
                WHERE ad_group_criterion.status = 'ENABLED'
                    AND campaign.status = 'ENABLED'
            """
            response = await asyncio.to_thread(
                ga_service.search, customer_id=customer_id, query=query
            )
            return {row.ad_group_criterion.keyword.text.lower() for row in response}
        except Exception:
            return set()

    async def get_existing_negatives(self, customer_id: str) -> set:
        """Get existing negative keywords."""
        client = self._get_client()
        if not client:
            return set()

        try:
            ga_service = client.get_service("GoogleAdsService")
            query = """
                SELECT campaign_criterion.keyword.text
                FROM campaign_criterion
                WHERE campaign_criterion.type = 'KEYWORD'
                    AND campaign_criterion.negative = TRUE
                    AND campaign.status != 'REMOVED'
            """
            response = await asyncio.to_thread(
                ga_service.search, customer_id=customer_id, query=query
            )
            return {row.campaign_criterion.keyword.text.lower() for row in response}
        except Exception:
            return set()

    async def get_ad_groups_with_keywords(self, customer_id: str) -> Dict[str, List[str]]:
        """Get ad groups and their keywords for ad group matching."""
        client = self._get_client()
        if not client:
            return {}

        try:
            ga_service = client.get_service("GoogleAdsService")
            query = """
                SELECT
                    ad_group.name,
                    ad_group_criterion.keyword.text
                FROM keyword_view
                WHERE ad_group_criterion.status = 'ENABLED'
                    AND campaign.status = 'ENABLED'
            """
            response = await asyncio.to_thread(
                ga_service.search, customer_id=customer_id, query=query
            )
            groups: Dict[str, List[str]] = {}
            for row in response:
                name = row.ad_group.name
                kw = row.ad_group_criterion.keyword.text
                groups.setdefault(name, []).append(kw)
            return groups
        except Exception:
            return {}

    async def generate_keyword_ideas(
        self,
        customer_id: str,
        seed_keywords: List[str],
        geo_target_ids: List[str],
    ) -> List[Dict[str, Any]]:
        """Call Keyword Planner to generate keyword ideas."""
        client = self._get_client()
        if not client:
            return self._mock_keyword_ideas(seed_keywords)

        try:
            keyword_plan_idea_service = client.get_service("KeywordPlanIdeaService")
            ga_service = client.get_service("GoogleAdsService")

            request = client.get_type("GenerateKeywordIdeasRequest")
            request.customer_id = customer_id
            request.language = ga_service.language_constant_path("1000")
            request.geo_target_constants = [
                ga_service.geo_target_constant_path(loc) for loc in geo_target_ids
            ]
            request.keyword_plan_network = (
                client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
            )
            request.keyword_seed.keywords.extend(seed_keywords)

            response = await asyncio.to_thread(
                keyword_plan_idea_service.generate_keyword_ideas,
                request=request,
            )

            ideas = []
            for result in response:
                metrics = result.keyword_idea_metrics
                monthly_vols = []
                if metrics.monthly_search_volumes:
                    for mv in metrics.monthly_search_volumes:
                        monthly_vols.append({
                            "month": mv.month.value if hasattr(mv.month, 'value') else int(mv.month),
                            "year": mv.year,
                            "searches": mv.monthly_searches,
                        })
                ideas.append({
                    "keyword_text": result.text,
                    "avg_monthly_searches": metrics.avg_monthly_searches,
                    "competition": str(metrics.competition).split(".")[-1],
                    "competition_index": metrics.competition_index,
                    "low_cpc_micros": metrics.low_top_of_page_bid_micros,
                    "high_cpc_micros": metrics.high_top_of_page_bid_micros,
                    "monthly_volumes": monthly_vols,
                })
            return ideas
        except Exception as e:
            logger.error(f"Error generating keyword ideas for {customer_id}: {e}")
            return self._mock_keyword_ideas(seed_keywords)

    async def get_account_avg_cpc(self, customer_id: str) -> Optional[float]:
        """Get account-level average CPC."""
        client = self._get_client()
        if not client:
            return 3.50

        try:
            ga_service = client.get_service("GoogleAdsService")
            query = """
                SELECT
                    metrics.average_cpc
                FROM customer
                WHERE segments.date DURING LAST_30_DAYS
            """
            response = await asyncio.to_thread(
                ga_service.search, customer_id=customer_id, query=query
            )
            for row in response:
                return float(row.metrics.average_cpc) / 1_000_000
            return None
        except Exception:
            return None

    # --- Mock data for development without API credentials ---
    def _mock_accounts(self) -> List[Dict[str, str]]:
        return [
            {"google_ads_id": "123-456-7890", "name": "Magnolia Custom Pools"},
            {"google_ads_id": "234-567-8901", "name": "Blue Haven Pools - Houston"},
            {"google_ads_id": "345-678-9012", "name": "Premier Pools & Spas - Dallas"},
            {"google_ads_id": "456-789-0123", "name": "Anthony & Sylvan Pools"},
            {"google_ads_id": "567-890-1234", "name": "Cody Pools - Austin"},
        ]

    def _mock_seeds(self) -> List[Dict[str, Any]]:
        return [
            {"keyword": "pool builder", "match_type": "EXACT", "conversions": 15.0,
             "clicks": 230, "cost": 890.50, "quality_score": 8,
             "campaign": "Pool Builder - Search", "ad_group": "Pool Builder"},
            {"keyword": "custom pool", "match_type": "PHRASE", "conversions": 8.0,
             "clicks": 145, "cost": 520.00, "quality_score": 7,
             "campaign": "Pool Builder - Search", "ad_group": "Custom Pool"},
            {"keyword": "inground pool cost", "match_type": "PHRASE", "conversions": 5.0,
             "clicks": 98, "cost": 310.25, "quality_score": 7,
             "campaign": "Pool Cost - Search", "ad_group": "Pool Cost"},
            {"keyword": "pool company near me", "match_type": "EXACT", "conversions": 12.0,
             "clicks": 180, "cost": 650.00, "quality_score": 9,
             "campaign": "Pool Builder - Search", "ad_group": "Near Me"},
            {"keyword": "swimming pool installation", "match_type": "PHRASE", "conversions": 3.0,
             "clicks": 75, "cost": 280.00, "quality_score": 6,
             "campaign": "Pool Services - Search", "ad_group": "Installation"},
        ]

    def _mock_keyword_ideas(self, seed_keywords: List[str]) -> List[Dict[str, Any]]:
        """Generate mock keyword ideas for development."""
        mock_ideas = [
            {"keyword_text": "gunite pool builder near me", "avg_monthly_searches": 320,
             "competition": "MEDIUM", "competition_index": 55,
             "low_cpc_micros": 2500000, "high_cpc_micros": 8500000,
             "monthly_volumes": [{"month": i, "year": 2026, "searches": 200 + (100 if 3 <= i <= 6 else 0)} for i in range(1, 13)]},
            {"keyword_text": "fiberglass pool installation cost", "avg_monthly_searches": 480,
             "competition": "LOW", "competition_index": 28,
             "low_cpc_micros": 1800000, "high_cpc_micros": 5200000,
             "monthly_volumes": [{"month": i, "year": 2026, "searches": 350 + (200 if 3 <= i <= 7 else 0)} for i in range(1, 13)]},
            {"keyword_text": "pool remodel contractor", "avg_monthly_searches": 210,
             "competition": "LOW", "competition_index": 22,
             "low_cpc_micros": 3100000, "high_cpc_micros": 9800000,
             "monthly_volumes": [{"month": i, "year": 2026, "searches": 180 + (50 if 2 <= i <= 5 else 0)} for i in range(1, 13)]},
            {"keyword_text": "saltwater pool conversion", "avg_monthly_searches": 390,
             "competition": "MEDIUM", "competition_index": 45,
             "low_cpc_micros": 1500000, "high_cpc_micros": 4500000,
             "monthly_volumes": [{"month": i, "year": 2026, "searches": 300 + (150 if 4 <= i <= 8 else 0)} for i in range(1, 13)]},
            {"keyword_text": "pool deck resurfacing", "avg_monthly_searches": 260,
             "competition": "LOW", "competition_index": 30,
             "low_cpc_micros": 2200000, "high_cpc_micros": 6800000,
             "monthly_volumes": [{"month": i, "year": 2026, "searches": 200 + (80 if 3 <= i <= 6 else 0)} for i in range(1, 13)]},
            {"keyword_text": "hot tub installation near me", "avg_monthly_searches": 520,
             "competition": "MEDIUM", "competition_index": 50,
             "low_cpc_micros": 1200000, "high_cpc_micros": 3800000,
             "monthly_volumes": [{"month": i, "year": 2026, "searches": 350 + (250 if 10 <= i <= 12 else 0)} for i in range(1, 13)]},
            {"keyword_text": "pebble tec pool finish", "avg_monthly_searches": 170,
             "competition": "LOW", "competition_index": 18,
             "low_cpc_micros": 1000000, "high_cpc_micros": 3200000,
             "monthly_volumes": [{"month": i, "year": 2026, "searches": 140 + (50 if 3 <= i <= 6 else 0)} for i in range(1, 13)]},
            {"keyword_text": "pool table felt replacement", "avg_monthly_searches": 880,
             "competition": "LOW", "competition_index": 15,
             "low_cpc_micros": 500000, "high_cpc_micros": 1500000,
             "monthly_volumes": [{"month": i, "year": 2026, "searches": 880} for i in range(1, 13)]},
            {"keyword_text": "infinity pool design ideas", "avg_monthly_searches": 410,
             "competition": "LOW", "competition_index": 25,
             "low_cpc_micros": 900000, "high_cpc_micros": 2800000,
             "monthly_volumes": [{"month": i, "year": 2026, "searches": 300 + (180 if 3 <= i <= 7 else 0)} for i in range(1, 13)]},
            {"keyword_text": "diy pool cleaning tips", "avg_monthly_searches": 720,
             "competition": "LOW", "competition_index": 10,
             "low_cpc_micros": 200000, "high_cpc_micros": 800000,
             "monthly_volumes": [{"month": i, "year": 2026, "searches": 600 + (200 if 5 <= i <= 8 else 0)} for i in range(1, 13)]},
            {"keyword_text": "swim spa dealers near me", "avg_monthly_searches": 350,
             "competition": "MEDIUM", "competition_index": 48,
             "low_cpc_micros": 1800000, "high_cpc_micros": 5500000,
             "monthly_volumes": [{"month": i, "year": 2026, "searches": 300 + (80 if 10 <= i <= 12 else 0)} for i in range(1, 13)]},
            {"keyword_text": "pool builder cost estimate", "avg_monthly_searches": 290,
             "competition": "MEDIUM", "competition_index": 52,
             "low_cpc_micros": 3200000, "high_cpc_micros": 10500000,
             "monthly_volumes": [{"month": i, "year": 2026, "searches": 220 + (100 if 2 <= i <= 5 else 0)} for i in range(1, 13)]},
            {"keyword_text": "carpool lane rules", "avg_monthly_searches": 1200,
             "competition": "LOW", "competition_index": 5,
             "low_cpc_micros": 100000, "high_cpc_micros": 300000,
             "monthly_volumes": [{"month": i, "year": 2026, "searches": 1200} for i in range(1, 13)]},
            {"keyword_text": "concrete pool vs fiberglass", "avg_monthly_searches": 440,
             "competition": "LOW", "competition_index": 20,
             "low_cpc_micros": 1500000, "high_cpc_micros": 4200000,
             "monthly_volumes": [{"month": i, "year": 2026, "searches": 350 + (130 if 3 <= i <= 6 else 0)} for i in range(1, 13)]},
            {"keyword_text": "pool fence requirements", "avg_monthly_searches": 280,
             "competition": "LOW", "competition_index": 12,
             "low_cpc_micros": 800000, "high_cpc_micros": 2400000,
             "monthly_volumes": [{"month": i, "year": 2026, "searches": 230 + (70 if 4 <= i <= 7 else 0)} for i in range(1, 13)]},
        ]
        return mock_ideas
