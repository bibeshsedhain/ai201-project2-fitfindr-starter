"""Reproducible workflow evidence. Offline mode explicitly mocks Groq responses."""
import argparse
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tools
from agent import run_agent
from utils.data_loader import get_example_wardrobe


def show(label, session):
    print(f"\n=== {label} ===")
    print(json.dumps(session, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="Use labeled fixture model output; no API calls")
    parser.add_argument("--live-trends", action="store_true", help="Check the public fashion RSS feed")
    args = parser.parse_args()
    wardrobe = get_example_wardrobe()
    def interaction():
        show("Natural language → search → price check → outfit → fit card",
             run_agent("I'm looking for a vintage graphic tee under $30", wardrobe,
                       include_trends=args.live_trends))
        show("Empty size search → bounded retry; unchanged budget",
             run_agent("graphic tee size XXS under $30", wardrobe))
        show("No results → early stop", run_agent("designer ballgown size XXS under $5", wardrobe))
    if args.offline:
        print("OFFLINE DEMO: Groq text below is a test fixture, not a live model response.")
        def fixture(prompt, temperature=0.7):
            if "OUTFIT IDEA:" in prompt:
                return "Thrifted graphic tee meets baggy dark-wash denim and chunky white sneakers. An easy vintage streetwear fit."
            return "Pair the selected graphic tee with Baggy straight-leg jeans, dark wash and Chunky white sneakers. Layer Vintage black denim jacket for a relaxed streetwear look."
        with patch.object(tools, "_call_llm", side_effect=fixture):
            interaction()
    else:
        interaction()
    print("\nDELIBERATE FAILURE: model call raises RuntimeError; no fit-card call should follow.")
    with patch.object(tools, "_call_llm", side_effect=RuntimeError("Injected provider outage")):
        session = run_agent("graphic tee under $30", wardrobe)
        assert session["error"] and "create_fit_card" not in session["tool_calls"]
        show("Actionable API failure, selected item retained", session)
    print("\nEMPTY FIT CARD INPUT:", tools.create_fit_card("", tools.load_listings()[5]))


if __name__ == "__main__":
    main()
