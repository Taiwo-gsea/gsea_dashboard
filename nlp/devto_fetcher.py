"""
Fetches Green Software Engineering articles from the public dev.to API.
No authentication required. API reference: https://developers.forem.com/api
"""

import json
import time
import logging
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

DEVTO_API_BASE   = "https://dev.to/api"
GSE_TAGS         = ["green-software", "sustainability", "carbon", "energy-efficiency", "climate"]
CACHE_DIR        = Path("data/devto_cache")
RATE_LIMIT_DELAY = 0.12   # stay under 10 req/s
PAGE_SIZE        = 30     # dev.to default page size


class DevToFetcher:
    """Fetches and locally caches dev.to articles for the NLP corpus."""

    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "GSEA-Dashboard-Academic-Research/1.0",
            "Accept":     "application/json",
        })

    def fetch_gse_articles(
        self,
        tags: list[str] = None,
        max_total: int = 500,
        use_cache: bool = True,
    ) -> list[dict]:
        """Fetch articles matching `tags`, deduplicated by ID, cached locally for 24h."""
        tags = tags or GSE_TAGS
        cache_path = self.cache_dir / "gse_articles.json"

        if use_cache and cache_path.exists():
            age_hours = (time.time() - cache_path.stat().st_mtime) / 3600
            if age_hours < 24:
                logger.info(f"Loading {cache_path} from cache ({age_hours:.1f}h old)")
                with open(cache_path) as f:
                    articles = json.load(f)
                return articles[:max_total]

        all_articles = {}
        for tag in tags:
            logger.info(f"Fetching dev.to articles for tag: {tag}")
            fetched = self._fetch_by_tag(tag, max_per_tag=max_total // len(tags) + 50)
            for article in fetched:
                all_articles[article["id"]] = article
            time.sleep(RATE_LIMIT_DELAY)

        articles = list(all_articles.values())
        articles.sort(key=lambda a: a.get("published_at", ""), reverse=True)

        with open(cache_path, "w") as f:
            json.dump(articles, f, indent=2, default=str)
        logger.info(f"Cached {len(articles)} articles to {cache_path}")

        return articles[:max_total]

    def get_article_detail(self, article_id: int) -> Optional[dict]:
        """Fetch and cache the full body of a single article."""
        cache_path = self.cache_dir / f"article_{article_id}.json"
        if cache_path.exists():
            with open(cache_path) as f:
                return json.load(f)

        try:
            resp = self.session.get(f"{DEVTO_API_BASE}/articles/{article_id}", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            with open(cache_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
            time.sleep(RATE_LIMIT_DELAY)
            return data
        except Exception as e:
            logger.warning(f"Could not fetch article {article_id}: {e}")
            return None

    def get_cache_stats(self) -> dict:
        cache_path = self.cache_dir / "gse_articles.json"
        if not cache_path.exists():
            return {"cached": False, "articles": 0}
        with open(cache_path) as f:
            articles = json.load(f)
        age_h = (time.time() - cache_path.stat().st_mtime) / 3600
        return {
            "cached":       True,
            "articles":     len(articles),
            "age_hours":    round(age_h, 1),
            "cache_path":   str(cache_path),
            "tags_covered": list({t for a in articles for t in a.get("tag_list", [])}),
        }

    def clear_cache(self) -> None:
        for f in self.cache_dir.glob("*.json"):
            f.unlink()
        logger.info("Cache cleared.")

    def _fetch_by_tag(self, tag: str, max_per_tag: int = 200) -> list[dict]:
        """Paginate the dev.to API for a single tag until max_per_tag or last page."""
        articles = []
        page = 1

        while len(articles) < max_per_tag:
            try:
                resp = self.session.get(
                    f"{DEVTO_API_BASE}/articles",
                    params={"tag": tag, "page": page, "per_page": PAGE_SIZE},
                    timeout=15,
                )
                resp.raise_for_status()
                batch = resp.json()
            except requests.exceptions.RequestException as e:
                logger.warning(f"API error on tag={tag} page={page}: {e}")
                break

            if not batch:
                break

            articles.extend(self._normalise(a) for a in batch)
            page += 1
            time.sleep(RATE_LIMIT_DELAY)

            if len(batch) < PAGE_SIZE:
                break

        logger.info(f"  [{tag}] fetched {len(articles)} articles")
        return articles[:max_per_tag]

    @staticmethod
    def _normalise(raw: dict) -> dict:
        return {
            "id":             raw.get("id"),
            "title":          raw.get("title", ""),
            "url":            raw.get("url", ""),
            "author":         raw.get("user", {}).get("username", ""),
            "published_at":   raw.get("published_at", ""),
            "body_markdown":  raw.get("body_markdown", raw.get("description", "")),
            "tag_list":       raw.get("tag_list", []),
            "reading_time":   raw.get("reading_time_minutes", 0),
            "reactions":      raw.get("public_reactions_count", 0),
            "comments":       raw.get("comments_count", 0),
        }


_fetcher_instance: Optional[DevToFetcher] = None


def get_fetcher() -> DevToFetcher:
    global _fetcher_instance
    if _fetcher_instance is None:
        _fetcher_instance = DevToFetcher()
    return _fetcher_instance
