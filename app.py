"""Gradio app with explicit local profile memory and optional public trend checks."""
import json
import gradio as gr

from agent import run_agent
from profiles import ProfileStore, validate_profile
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

STORE = ProfileStore()


def save_profile(profile_id, wardrobe_json, preferences, size, budget):
    try:
        profile = validate_profile({"wardrobe": json.loads(wardrobe_json),
                                    "style_preferences": preferences or "", "size": size,
                                    "max_price": budget})
        STORE.save(profile_id, profile)
        return "Profile saved locally. Load it in a later session to reuse your wardrobe and defaults."
    except (OSError, ValueError, TypeError) as exc:
        return f"Profile was not saved: {exc}. Correct the fields or check local folder permissions."


def load_profile(profile_id):
    try:
        profile = STORE.load(profile_id)
        if profile is None:
            raise ValueError("No profile with that name. Save one first.")
        return (json.dumps(profile["wardrobe"], indent=2), profile["style_preferences"],
                profile["size"] or "", profile["max_price"], "Custom / saved wardrobe",
                "Profile loaded. Its wardrobe and defaults will be used for your next search.")
    except (OSError, ValueError, TypeError) as exc:
        return (gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(),
                f"Could not load profile: {exc}. Check the name or save a corrected profile.")


def delete_profile(profile_id):
    try:
        STORE.delete(profile_id)
        return "Saved profile deleted. Clear the editor too if you want to discard the currently loaded values."
    except (OSError, ValueError) as exc:
        return f"Could not delete profile: {exc}. Check the name and local folder permissions."


def handle_query(user_query: str, wardrobe_choice: str, wardrobe_json: str = "",
                 preferences: str = "", size: str = "", budget: float | None = None,
                 include_trends: bool = False) -> tuple[str, str, str]:
    if not isinstance(user_query, str) or not user_query.strip():
        return "Please enter an item to search for.", "", ""
    try:
        if wardrobe_choice == "Custom / saved wardrobe":
            wardrobe = json.loads(wardrobe_json)
        elif wardrobe_choice == "Empty wardrobe (new user)":
            wardrobe = get_empty_wardrobe()
        else:
            wardrobe = get_example_wardrobe()
        profile = validate_profile({"wardrobe": wardrobe, "style_preferences": preferences or "",
                                    "size": size, "max_price": budget})
    except (ValueError, TypeError) as exc:
        return f"Please correct your wardrobe or defaults: {exc}", "", ""
    session = run_agent(user_query.strip(), wardrobe, profile=profile,
                        include_trends=include_trends)
    sections = list(session["notices"])
    if session["error"]:
        sections.append(session["error"])
    item = session["selected_item"]
    if item:
        sections.append(
            f"{item['title']}\n${item['price']:.2f} on {item['platform']}\n"
            f"Size: {item['size']} | Condition: {item['condition']}\n"
            f"Brand: {item.get('brand') or 'Unbranded'}\n{item['description']}")
    if session["price_comparison"]:
        sections.append("PRICE CHECK\n" + session["price_comparison"]["message"])
    if session["trends"]:
        trends = session["trends"]
        text = "RECENT STYLE SIGNALS\n" + trends["message"]
        text += f"\nChecked: {trends['checked_at']} | posts: {trends['posts_checked']}"
        for trend in trends["trends"]:
            text += f"\n{trend['style']}: {trend['post_count']} posts; size-matched listings: {', '.join(trend['listing_ids'])}"
            for source in trend["sources"]:
                text += f"\n  {source['title']} ({source['published_at']})\n  {source['url']}"
        sections.append(text)
    sections.append("Tool trace: " + " → ".join(session["tool_calls"]))
    outfit = session["outfit_suggestion"] or ""
    if session["error"] == outfit:
        outfit = ""
    return "\n\n".join(sections), outfit, session["fit_card"] or ""


EXAMPLE_QUERIES = ["vintage graphic tee under $30", "90s track jacket in size M",
                   "graphic tee size XXS under $30", "designer ballgown size XXS under $5"]


def build_interface():
    with gr.Blocks(title="FitFindr") as demo:
        gr.Markdown("# FitFindr 🛍️\nFind secondhand pieces, compare prices and build a look around your wardrobe.")
        query = gr.Textbox(label="What are you looking for?", placeholder="vintage graphic tee size M under $30")
        choice = gr.Radio(["Example wardrobe", "Empty wardrobe (new user)", "Custom / saved wardrobe"],
                          value="Example wardrobe", label="Wardrobe")
        with gr.Accordion("Style profile — save once, load in a later session", open=False):
            gr.Markdown("Profiles are stored on this computer. Names identify local profiles; they are not passwords. Use this app locally. Loading fills the editor; saving is explicit. The selected wardrobe mode controls searches; Save stores the wardrobe editor.")
            profile_id = gr.Textbox(label="Local profile name")
            wardrobe = gr.Textbox(label="Wardrobe editor (JSON)", lines=10,
                                  value=json.dumps(get_example_wardrobe(), indent=2))
            preferences = gr.Textbox(label="Style preferences", placeholder="earth tones, relaxed silhouettes")
            size = gr.Textbox(label="Default size (query can override)")
            budget = gr.Number(label="Default maximum price (optional)", value=None, minimum=0)
            with gr.Row():
                save = gr.Button("Save profile")
                load = gr.Button("Load profile")
                delete = gr.Button("Delete saved profile")
            profile_status = gr.Textbox(label="Profile status", interactive=False)
        trends = gr.Checkbox(label="Check recent public fashion posts (uses internet)", value=False)
        submit = gr.Button("Find it", variant="primary")
        with gr.Row():
            listing = gr.Textbox(label="Listing, price check and tool trace", lines=16, interactive=False)
            outfit = gr.Textbox(label="Outfit idea", lines=12, interactive=False)
            card = gr.Textbox(label="Your fit card", lines=12, interactive=False)
        inputs = [query, choice, wardrobe, preferences, size, budget, trends]
        submit.click(handle_query, inputs, [listing, outfit, card])
        query.submit(handle_query, inputs, [listing, outfit, card])
        gr.Examples([[q] for q in EXAMPLE_QUERIES], inputs=[query])
        save.click(save_profile, [profile_id, wardrobe, preferences, size, budget], profile_status)
        load.click(load_profile, profile_id, [wardrobe, preferences, size, budget, choice, profile_status])
        delete.click(delete_profile, profile_id, profile_status)
    return demo


if __name__ == "__main__":
    build_interface().launch()
