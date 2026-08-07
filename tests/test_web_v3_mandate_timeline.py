import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
RENDER_JS = (ROOT / "web" / "v3" / "js" / "render.js").read_text(encoding="utf-8")
APP_JS = (ROOT / "web" / "v3" / "js" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "web" / "v3" / "design-tokens.css").read_text(encoding="utf-8")


class MandateTimelineTests(unittest.TestCase):

    def run_builder(self, mandates):
        # Extract buildMandateTimeline from render.js for unit-testing
        start = RENDER_JS.index("export function buildMandateTimeline(profile) {")
        # Find the matching closing brace for the function
        brace_depth = 0
        end = start
        for i, ch in enumerate(RENDER_JS[start:], start=start):
            if ch == "{":
                brace_depth += 1
            elif ch == "}":
                brace_depth -= 1
                if brace_depth == 0:
                    end = i + 1
                    break
        function_source = RENDER_JS[start:end].replace("export function", "function")
        script = f"""
        function toDateMs(value) {{ return value ? new Date(value).getTime() : 0; }}
        {function_source}
        process.stdout.write(JSON.stringify(buildMandateTimeline({{
          pivot_mandats: {json.dumps(mandates)}
        }})));
        """
        result = subprocess.run(
            ["node", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)

    def test_builder_only_merges_truly_contiguous_periods(self):
        mandates = [
            {
                "label": "Commission A",
                "categorie": "commission",
                "fonction": "membre",
                "debut": "2023-01-01",
                "fin": "2023-01-31",
                "actif": False,
                "source_url": "https://example.test/1",
            },
            {
                "label": "Commission A",
                "categorie": "commission",
                "fonction": "membre",
                "debut": "2023-02-01",
                "fin": "2023-02-28",
                "actif": False,
                "source_url": "https://example.test/2",
            },
            {
                "label": "Commission A",
                "categorie": "commission",
                "fonction": "membre",
                "debut": "2023-03-02",
                "fin": "2023-03-31",
                "actif": False,
                "source_url": "javascript:alert(1)",
            },
            {
                "label": "Mandat récent",
                "categorie": "mandat_electif",
                "fonction": "député",
                "debut": "2024-01-01",
                "fin": None,
                "actif": True,
                "source_url": None,
            },
            {
                "label": "Date inconnue",
                "categorie": "commission",
                "fonction": "membre",
                "debut": None,
                "fin": None,
                "actif": True,
                "source_url": None,
            },
        ]

        result = self.run_builder(mandates)

        self.assertEqual([item["label"] for item in result], [
            "Mandat récent", "Commission A", "Commission A", "Date inconnue",
        ])
        self.assertEqual(result[1]["debut"], "2023-03-02")
        self.assertEqual(result[2]["debut"], "2023-01-01")
        self.assertEqual(result[2]["fin"], "2023-02-28")
        self.assertEqual(result[2]["sourceUrls"], [
            "https://example.test/1", "https://example.test/2",
        ])
        self.assertEqual(result[1]["sourceUrls"], [])

    def test_primary_view_and_mobile_layout_are_explicit(self):
        # mandateView default is in app.js
        self.assertIn('mandateView: "timeline"', APP_JS)
        # Updated panel heading (PR2: "Mandats & responsabilités")
        self.assertIn("Mandats &amp; responsabilités", RENDER_JS)
        # View control buttons still present
        self.assertIn('["timeline", "Chronologie"], ["responsibilities", "Responsabilités"]', RENDER_JS)
        self.assertIn('["all", "Tous"], ["elective", "Électifs"], ["responsibilities", "Responsabilités"], ["groups", "Groupes"]', RENDER_JS)
        # Mobile compact layout (small viewport override)
        self.assertIn("grid-template-columns: 56px minmax(0, 1fr)", CSS)
        # Date fallback string still in render
        self.assertIn('"date non renseignée"', RENDER_JS)


if __name__ == "__main__":
    unittest.main()
