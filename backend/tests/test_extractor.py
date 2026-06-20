"""
Pure-logic tests for app.agents.research.extractor — no network, no DB.
"""
from app.agents.research.extractor import _extract_from_html, normalize_url


class TestNormalizeUrl:
    def test_strips_tracking_params(self):
        url = "https://Example.com/Article?utm_source=twitter&id=42"
        # Only the host is lowercased — the path case is preserved as-is.
        assert normalize_url(url) == "https://example.com/Article?id=42"

    def test_strips_fragment(self):
        assert normalize_url("https://example.com/a#section") == "https://example.com/a"

    def test_strips_trailing_slash(self):
        assert normalize_url("https://example.com/a/") == normalize_url("https://example.com/a")

    def test_sorts_remaining_query_params(self):
        a = normalize_url("https://example.com/a?b=2&a=1")
        b = normalize_url("https://example.com/a?a=1&b=2")
        assert a == b

    def test_lowercases_host_not_path(self):
        out = normalize_url("https://EXAMPLE.com/Some-Path")
        assert out.startswith("https://example.com/")
        assert "Some-Path" in out

    def test_root_path_normalizes_to_slash(self):
        assert normalize_url("https://example.com") == "https://example.com/"


class TestExtractFromHtml:
    def test_prefers_og_title_over_title_tag(self):
        html = """
        <html><head>
          <title>Wrong Title - Site Name</title>
          <meta property="og:title" content="Correct Title" />
        </head><body><article>{}</article></body></html>
        """.format(" ".join(["word"] * 100))
        _, title, _ = _extract_from_html(html)
        assert title == "Correct Title"

    def test_falls_back_to_title_tag(self):
        html = """
        <html><head><title>Only Title</title></head>
        <body><article>{}</article></body></html>
        """.format(" ".join(["word"] * 100))
        _, title, _ = _extract_from_html(html)
        assert title == "Only Title"

    def test_extracts_article_tag_content(self):
        body_text = " ".join([f"word{i}" for i in range(150)])
        html = f"<html><body><nav>menu items here</nav><article>{body_text}</article></body></html>"
        text, _, _ = _extract_from_html(html)
        assert "word0" in text
        assert "menu items here" not in text

    def test_skips_short_selector_match_falls_through(self):
        # <article> has too few words (<80) to count — should fall through
        # to the generic body-minus-chrome extraction instead.
        long_text = " ".join([f"real{i}" for i in range(150)])
        html = f"""
        <html><body>
          <nav>nav links</nav>
          <article>too short</article>
          <div>{long_text}</div>
        </body></html>
        """
        text, _, _ = _extract_from_html(html)
        assert "real0" in text
        assert "nav links" not in text

    def test_extracts_published_time_meta(self):
        html = """
        <html><head>
          <meta property="article:published_time" content="2026-01-15T10:00:00Z" />
        </head><body><article>{}</article></body></html>
        """.format(" ".join(["word"] * 100))
        _, _, raw_date = _extract_from_html(html)
        assert raw_date == "2026-01-15T10:00:00Z"

    def test_extracts_time_tag_datetime_when_no_meta(self):
        html = """
        <html><body>
          <time datetime="2026-02-01T08:00:00Z">Feb 1</time>
          <article>{}</article>
        </body></html>
        """.format(" ".join(["word"] * 100))
        _, _, raw_date = _extract_from_html(html)
        assert raw_date == "2026-02-01T08:00:00Z"

    def test_india_today_group_content_area_selector(self):
        # Regression test for the Business Today bug: businesstoday.in (India
        # Today Group) marks its real article body with a class containing
        # "content_area", not "article-content"/"articleBody" etc. Without
        # the content_area selector, extraction fell through to the generic
        # body-minus-chrome fallback and picked up nav menu text instead.
        nav_text = " ".join(["Business Today BT Bazaar India Today"] * 30)
        article_text = " ".join([f"marketupdate{i}" for i in range(150)])
        html = f"""
        <html><body>
          <div class="site-header">{nav_text}</div>
          <div class="story_content_area_wrapper">{article_text}</div>
          <div class="site-footer">{nav_text}</div>
        </body></html>
        """
        text, _, _ = _extract_from_html(html)
        assert "marketupdate0" in text
        assert "Bazaar" not in text
