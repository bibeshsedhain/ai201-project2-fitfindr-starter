"""Launch Gradio and verify its HTTP callbacks with explicit model fixtures."""
import json
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gradio_client import Client
import app
import tools


def main():
    with patch.object(tools, "_call_llm", return_value="Fixture outfit/caption for HTTP wiring; not live Groq."):
        demo = app.build_interface()
        try:
            _, url, _ = demo.launch(prevent_thread_lock=True, quiet=True, server_name="127.0.0.1")
            client = Client(url, verbose=False)
            inputs = ["Example wardrobe", json.dumps({"items": []}), "", "", None, False]
            happy = client.predict("vintage graphic tee under $30", *inputs, api_name="/handle_query")
            assert len(happy) == 3 and all(happy)
            assert "compare_prices" in happy[0] and "create_fit_card" in happy[0]
            failure = client.predict("designer ballgown size XXS under $5", *inputs, api_name="/handle_query")
            assert "Try a broader description" in failure[0]
            assert failure[1:] == ("", "")
            print("PASS: HTTP happy path fills all three panels using explicit model fixtures.")
            print("PASS: HTTP no-results branch gives actionable error and blank later panels.")
        finally:
            demo.close()


if __name__ == "__main__":
    main()
