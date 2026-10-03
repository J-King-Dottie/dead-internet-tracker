import json
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import embed_dashboard_readable as embed


class ScriptParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.scripts = []
        self.in_script = False

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        if tag == "script":
            self.scripts.append("")
            self.in_script = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_script = False

    def handle_data(self, data):
        if self.in_script:
            self.scripts[-1] += data


class EmbedDataTests(unittest.TestCase):
    def assert_embedded_data(self, html, expected):
        parser = ScriptParser()
        parser.feed(html)
        self.assertEqual(parser.tags, ["html", "head", "script", "body"])
        self.assertEqual(len(parser.scripts), 1)
        script = parser.scripts[0].strip()
        prefix = "window.__DASHBOARD_READABLE_DATA__ = "
        self.assertTrue(script.startswith(prefix))
        self.assertTrue(script.endswith(";"))
        serialized = script[len(prefix):-1]
        # Escaping every '<' also prevents HTML comment/double-escaped script states.
        self.assertNotIn("<", serialized)
        self.assertEqual(json.loads(serialized), expected)

    def test_data_cannot_close_the_script_element(self):
        for text in (
            '</script><p>quoted markup</p>',
            '</ScRiPt><script>window.unexpected = true;</script>',
            '<!-- <script>quoted example</script> -->',
        ):
            with self.subTest(text=text):
                data = {"charts": [{"notes": text}]}
                html = embed.insert_head_block("<html><head></head><body></body></html>", data)
                self.assert_embedded_data(html, data)

    def test_special_characters_and_unicode_round_trip(self):
        data = {"notes": '< 10% & "quotes" \\ paths, café, 日本語, \u2028\u2029'}
        html = embed.insert_head_block("<html><head></head><body></body></html>", data)
        self.assert_embedded_data(html, data)

    def test_reembedding_keeps_one_safe_data_script(self):
        data = {"notes": "</script><p>source text</p>", "charts": []}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            index = root / "index.html"
            source = root / "data.json"
            index.write_text("<html><head></head><body><main></main></body></html>", encoding="utf-8")
            source.write_text(json.dumps(data), encoding="utf-8")
            for _ in range(2):
                embed.embed(index, source)
                html = index.read_text(encoding="utf-8")
                head = html[:html.index("</head>") + len("</head>")] + "<body></body></html>"
                self.assert_embedded_data(head, data)
                self.assertEqual(html.count(embed.HEAD_START), 1)
                self.assertEqual(html.count(embed.BODY_START), 1)
            self.assertEqual(json.loads(source.read_text(encoding="utf-8")), data)


if __name__ == "__main__":
    unittest.main()
