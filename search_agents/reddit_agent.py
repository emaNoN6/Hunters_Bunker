# ==========================================================
# Hunter's Command Console - Reddit Agent (v2 - Simplified)
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================
import praw
import logging
from hunter.models import SourceConfig

logger = logging.getLogger("Reddit Agent")


def hunt(source: SourceConfig, credentials: dict):
    """
    Hunts a specific subreddit for new posts since the last check.
    This agent's sole responsibility is to fetch the raw post data.
    All translation and data formatting is handled by the RedditForeman.
    """
    subreddit_name = source.target
    last_checked_id = source.last_known_item_id
    source_name = source.source_name

    logger.info(f"[{source_name}]: Waking up. Hunting r/{subreddit_name}...")

    if not all([
        credentials,
        credentials.get('client_id'),
        credentials.get('client_secret'),
        credentials.get('user_agent')
    ]):
        logger.error(f"[{source_name} ERROR]: Reddit API credentials are incomplete.")
        return [], None

    try:
        reddit = praw.Reddit(
                client_id=credentials['client_id'],
                client_secret=credentials['client_secret'],
                user_agent=credentials['user_agent']
        )
        subreddit = reddit.subreddit(subreddit_name)

        # PRAW handles the logic of fetching only new posts since the last one seen.
        # It's more efficient than using timestamps.
        params = {'before': last_checked_id} if last_checked_id else {}

        # We fetch a reasonable limit. The foreman will process them.
        new_posts = list(subreddit.new(limit=50, params=params))

        if not new_posts:
            logger.info(f"[{source_name}]: No new posts found in r/{subreddit_name}.")
            return [], last_checked_id

        # The agent's job is to return the raw, unprocessed data.
        # We extract the necessary attributes into a simple dictionary.
        # The foreman is responsible for turning this into a LeadData object.
        raw_leads = [_extract_post_data(post) for post in new_posts]

        # The newest post is the first one in the list returned by .new()
        newest_id = new_posts[0].id

        logger.info(
                f"[{source_name}]: Hunt successful. Returned {len(raw_leads)} new raw leads. Newest ID: {newest_id}")
        return raw_leads, newest_id

    except Exception as e:
        logger.error(f"[{source_name} ERROR]: An error occurred during the hunt for r/{subreddit_name}: {e}",
                     exc_info=True)
        return [], last_checked_id


def _extract_post_data(post) -> dict:
    """Extracts relevant data from a PRAW submission object."""
    lead = {
        "title":         post.title,
        "url":           post.url,
        "id":            post.id,
        "subreddit":     post.subreddit.display_name,
        "author":        post.author.name if post.author else "[deleted]",
        "created_utc":   post.created_utc,
        "score":         post.score,
        "num_comments":  post.num_comments,
        "is_self":       post.is_self,
        "selftext":      post.selftext,
        "selftext_html": post.selftext_html,
        "flair":         post.link_flair_text,
        "media_type":    None
    }

    _enrich_with_media(post, lead)
    return lead


def _enrich_with_media(post, lead: dict):
    """Analyzes the post for media content and updates the lead dictionary."""
    # Check for Reddit Video
    if getattr(post, 'is_video', False) or (post.media and "reddit_video" in post.media):
        rv = post.media.get("reddit_video", {}) if post.media else {}
        lead["media_type"] = "gif" if rv.get("is_gif") else "video"
        lead["media_url"] = rv.get("hls_url")
        lead["media_fallback_url"] = rv.get("fallback_url")
        lead["media_duration"] = rv.get("duration")
        lead["media_is_video"] = lead["media_type"] == "video"

        if not lead.get("selftext"):
            lead["selftext"] = "[Video Only]"

    # Check for Gallery
    elif getattr(post, 'is_gallery', False):
        lead["media_type"] = "gallery"
        if not lead.get("selftext"):
            lead["selftext"] = "[Gallery]"

        if getattr(post, 'media_metadata', None):
            urls = []
            for item in post.media_metadata.values():
                if 's' in item and 'u' in item['s']:
                    urls.append(item['s']['u'].replace('&amp;', '&'))
            lead["media_url"] = urls

    # Check for Image (Reddit Domain)
    elif getattr(post, 'is_reddit_media_domain', False):
        if post.url.endswith(('jpg', 'jpeg', 'png', 'webp')):
            lead["media_type"] = "image"
            lead["media_url"] = post.url
            if not lead.get("selftext"):
                lead["selftext"] = "[Image Only]"

    # Check for External Video (OEmbed)
    elif post.media and 'oembed' in post.media:
        oembed = post.media['oembed']
        if oembed.get('type') == 'video':
            lead["media_type"] = "video"
            lead["media_url"] = post.url
            lead["media_provider"] = oembed.get('provider_name')
            if not lead.get("selftext"):
                lead["selftext"] = f"[{oembed.get('provider_name', 'External')} Video]"
