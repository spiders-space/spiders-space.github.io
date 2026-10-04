import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_site
import fetch_channel


class Response:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.urls = []

    def get(self, url, **kwargs):
        self.urls.append(url)
        result = next(self.responses)
        if isinstance(result, Exception):
            raise result
        return Response(result)


def channel_page(*post_ids):
    messages = "".join(
        '<div class="tgme_widget_message" data-post="test/{0}">'
        '<div class="tgme_widget_message_text">post {0}</div></div>'.format(pid)
        for pid in post_ids
    )
    return '<div class="tgme_channel_info"></div>' + messages


def archived_post(post_id, media_name=None):
    return {
        "id": post_id,
        "url": f"https://t.me/test/{post_id}",
        "text_html": f"post {post_id}",
        "media": ([{"type": "photo", "local": f"media/{media_name}"}]
                  if media_name else []),
    }


class FetchChannelTests(unittest.TestCase):
    def test_full_scan_walks_past_overlap_and_returns_deleted_ids_as_missing(self):
        session = FakeSession([
            channel_page(5, 4),
            channel_page(3, 1),
            channel_page(),
        ])
        existing = {pid: archived_post(pid) for pid in (3, 2, 1)}
        with patch.object(fetch_channel, "S", session), \
             patch.object(fetch_channel, "BASE", "https://t.me/s/test"), \
             patch.object(fetch_channel, "MAX_PAGES", 0), \
             patch.object(fetch_channel.time, "sleep"):
            found, complete = fetch_channel.scan_channel(existing)

        self.assertTrue(complete)
        self.assertEqual(set(found), {5, 4, 3, 1})
        self.assertEqual(session.urls, [
            "https://t.me/s/test",
            "https://t.me/s/test?before=4",
            "https://t.me/s/test?before=1",
        ])

    def test_failed_page_marks_scan_incomplete(self):
        session = FakeSession([
            channel_page(4, 3),
            RuntimeError("temporary Telegram failure"),
        ])
        with patch.object(fetch_channel, "S", session), \
             patch.object(fetch_channel, "BASE", "https://t.me/s/test"), \
             patch.object(fetch_channel, "MAX_PAGES", 0), \
             patch.object(fetch_channel.time, "sleep"):
            found, complete = fetch_channel.scan_channel({1: archived_post(1)})

        self.assertFalse(complete)
        self.assertEqual(set(found), {4, 3})

    def test_complete_reconciliation_removes_deleted_post_and_its_media(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            posts_file = tmp_path / "posts.json"
            media_dir = tmp_path / "media"
            media_dir.mkdir()
            old = {
                1: archived_post(1, "1_1.jpg"),
                2: archived_post(2, "2_1.jpg"),
            }
            posts_file.write_text(json.dumps(list(old.values())), encoding="utf-8")
            for name in ("1_1.jpg", "2_1.jpg", "20_1.jpg"):
                (media_dir / name).write_bytes(b"media")

            with patch.object(fetch_channel, "POSTS_JSON", posts_file), \
                 patch.object(fetch_channel, "MEDIA_DIR", media_dir), \
                 patch.object(fetch_channel, "fetch_channel_meta", return_value={"title": "test", "counters": []}), \
                 patch.object(fetch_channel, "scan_channel", return_value=({1: old[1]}, True)):
                fetch_channel.main()

            saved = json.loads(posts_file.read_text(encoding="utf-8"))
            self.assertEqual([post["id"] for post in saved], [1])
            self.assertTrue((media_dir / "1_1.jpg").exists())
            self.assertFalse((media_dir / "2_1.jpg").exists())
            # Prefix matching must not confuse post #2 with post #20.
            self.assertTrue((media_dir / "20_1.jpg").exists())

    def test_incomplete_reconciliation_preserves_old_posts_and_media(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            posts_file = tmp_path / "posts.json"
            media_dir = tmp_path / "media"
            media_dir.mkdir()
            old = {
                1: archived_post(1, "1_1.jpg"),
                2: archived_post(2, "2_1.jpg"),
            }
            posts_file.write_text(json.dumps(list(old.values())), encoding="utf-8")
            (media_dir / "2_1.jpg").write_bytes(b"media")

            with patch.object(fetch_channel, "POSTS_JSON", posts_file), \
                 patch.object(fetch_channel, "MEDIA_DIR", media_dir), \
                 patch.object(fetch_channel, "fetch_channel_meta", return_value={"title": "test", "counters": []}), \
                 patch.object(fetch_channel, "scan_channel", return_value=({1: old[1]}, False)):
                fetch_channel.main()

            saved = json.loads(posts_file.read_text(encoding="utf-8"))
            self.assertEqual({post["id"] for post in saved}, {1, 2})
            self.assertTrue((media_dir / "2_1.jpg").exists())


class BuildSiteTests(unittest.TestCase):
    def test_prune_mirrors_removed_media(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "media"
            target = Path(tmp) / "docs-media"
            source.mkdir()
            target.mkdir()
            (source / "current.jpg").write_bytes(b"current")
            (target / "current.jpg").write_bytes(b"current")
            (target / "deleted.jpg").write_bytes(b"deleted")

            build_site.sync_dir(source, target, prune=True)

            self.assertTrue((target / "current.jpg").exists())
            self.assertFalse((target / "deleted.jpg").exists())

    def test_empty_site_rebuild_replaces_feed_and_removes_stale_post_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp) / "docs"
            (docs / "post/99").mkdir(parents=True)
            (docs / "post/99/index.html").write_text("stale", encoding="utf-8")
            (docs / "page/2").mkdir(parents=True)
            (docs / "page/2/index.html").write_text("stale", encoding="utf-8")
            (docs / "data").mkdir()
            (docs / "data/page-2.json").write_text("stale", encoding="utf-8")

            with patch.object(build_site, "DOCS", docs), \
                 patch.object(build_site, "posts", []), \
                 patch.object(build_site, "chan", {}), \
                 patch.object(build_site, "SITE_URL", ""), \
                 patch.object(build_site, "SID", ""):
                build_site.build()

            index = (docs / "index.html").read_text(encoding="utf-8")
            self.assertIn("no transmissions yet", index)
            self.assertFalse((docs / "post/99").exists())
            self.assertFalse((docs / "page/2").exists())
            self.assertFalse((docs / "data/page-2.json").exists())


if __name__ == "__main__":
    unittest.main()
