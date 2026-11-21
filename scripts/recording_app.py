"""Real FitFindr UI plus an explicitly labeled provider-failure test control.

Only the failure button injects an exception. Normal searches use live Groq.
"""
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gradio as gr
import tools
from app import build_interface
from agent import run_agent
from utils.data_loader import get_example_wardrobe


def trigger_provider_failure():
    with patch.object(tools, '_call_llm', side_effect=RuntimeError('Deliberately injected provider outage')):
        session = run_agent('vintage graphic tee under $30', get_example_wardrobe())
    return ('TEST: provider exception deliberately injected at the model-call boundary.\n\n'
            f"Selected listing retained: {session['selected_item']['title']}\n\n"
            f"Agent response: {session['error']}\n\n"
            f"Actual tool trace: {' → '.join(session['tool_calls'])}\n"
            f"create_fit_card called: {'Yes' if 'create_fit_card' in session['tool_calls'] else 'No'}\n"
            f"fit_card: {session['fit_card']}")


if __name__ == '__main__':
    demo = build_interface()
    with demo:
        with gr.Accordion('Recording-only test: deliberately trigger a provider failure', open=False):
            gr.Markdown('This test raises a real exception inside the model-call boundary. Normal searches above use live Groq. The agent should retain the listing, give recovery steps, and skip the fit-card tool.')
            button = gr.Button('Trigger provider failure')
            result = gr.Textbox(label='Deliberate failure — actual agent response', lines=12, interactive=False)
            button.click(trigger_provider_failure, outputs=result)
    demo.launch()
