import asyncio
import logging
from typing import Optional

log = logging.getLogger(__name__)

class ComickClient:
    BASE_URL = "https://comick-api-proxy.notaspider.dev/api"
    WEB_BASE = "https://comick.dev"
    HEADERS = {"User-Agent": "Tachiyomi/1.0"}

    def __init__(self, session):
        self.session = session

    async def search_slug(self, title: str):
        search_url = f"{self.BASE_URL}/v1.0/search"
        log.info(f"Searching for: {title}")
        data = await self._fetch_json(search_url, params={"q": title, "tachiyomi": "true"})
        if not data:
            log.warning(f"No results for: {title}")
            return None, None
        top = data[0]
        slug = top.get("slug")
        log.info(f"Found: {top.get('title', title)} (slug: {slug})")
        return slug, top

    async def get_latest_chapter(self, title: str, slug: str):
        """
        Returns the latest chapter info for a given manhwa title/slug.
        Resolves slug if needed.
        """
        resolved_slug, top = await self.search_slug(title)
        if not resolved_slug or not top:
            log.warning(f"Could not resolve slug for {title}")
            return None

        slug = resolved_slug
        hid = top.get("hid")
        cover_url = top.get("cover_url") or top.get("cover")

        if not hid:
            log.warning(f"No hid found for {title}")
            return None

        chapters_url = f"{self.BASE_URL}/comic/{hid}/chapters"
        chapters_data = await self._fetch_json(chapters_url, params={"limit": 1, "tachiyomi": "true"})
        if not chapters_data or "chapters" not in chapters_data or not chapters_data["chapters"]:
            log.warning(f"No chapters found for {title}")
            return None

        latest = chapters_data["chapters"][0]
        chap_num_raw = latest.get("chap") or latest.get("chapter") or 0
        try:
            chap_num = float(chap_num_raw)
        except Exception:
            chap_num = 0.0

        chap_title = latest.get("title", "")
        chap_hid = latest.get("hid") or latest.get("id") or ""
        chap_link = f"{self.WEB_BASE}/comic/{slug}/chapter/{chap_hid}"

        return {
            "title": title,
            "slug": slug,
            "chapter": chap_num,
            "chapter_title": chap_title,
            "link": chap_link,
            "cover": cover_url
        }

    async def _fetch_json(self, url: str, params: Optional[dict] = None, retries: int = 2, timeout: int = 10):
        """Fetch JSON from API with basic retries and timeout."""
        if not self.session:
            return None

        for attempt in range(1, retries + 2):
            try:
                async with self.session.get(url, headers=self.HEADERS, params=params, timeout=timeout) as resp:
                    if resp.status != 200:
                        log.warning(f"API returned {resp.status} for {url} (attempt {attempt})")
                        if attempt <= retries:
                            await asyncio.sleep(1)
                            continue
                        return None
                    return await resp.json()
            except asyncio.TimeoutError:
                log.warning(f"API request timeout for {url} (attempt {attempt})")
                if attempt <= retries:
                    await asyncio.sleep(1)
                    continue
                return None
            except Exception as e:
                log.error(f"Fetch error for {url} (attempt {attempt}): {e}", exc_info=True)
                if attempt <= retries:
                    await asyncio.sleep(1)
                    continue
                return None
