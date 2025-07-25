import chainlit as cl
import sys
import os
from pathlib import Path

# Add the parent directory to Python path for imports
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from services.app_context import app_context
from services.progress_handler import ChainlitProgressHandler
from agents.single_company_workflow import SingleCompanyWorkflow

@cl.on_chat_start
async def start():
    """
    Initializes the application context and workflow for a new chat session.
    This function is called once per user session.
    """
    # Ensure the application context is initialized. This is idempotent.
    if not app_context.initialized:
        await app_context.initialize()

    # Create a single, reusable workflow instance for this user's session.
    # This is the key to performance and stability.
    workflow = SingleCompanyWorkflow(app_context, ChainlitProgressHandler())

    # Store the workflow instance in the user's session for later use.
    cl.user_session.set("workflow", workflow)

    # Get the company resolver to provide suggestions to the user.
    resolver = app_context.agents['company_resolver']
    company_names = list(resolver.display_names.values())

    await cl.Message(
        content="Welcome to the Company Intelligence Briefing System! "
                "Please enter a company name to get started.",
        actions=[
            cl.Action(name="suggestion", value=name, label=name) for name in company_names
        ]
    ).send()

@cl.action_callback("suggestion")
async def on_suggestion(action: cl.Action):
    """Handles clicks on company suggestion buttons."""
    await handle_message(cl.Message(content=action.value))

@cl.on_message
async def handle_message(message: cl.Message):
    """
    Processes incoming user messages, using the pre-initialized workflow.
    """
    company_name = message.content.strip()

    # Retrieve the pre-initialized workflow instance from the user session.
    # This avoids creating a new workflow for every message.
    workflow = cl.user_session.get("workflow")

    # Run the workflow. The progress handler within the workflow will send
    # updates directly to the Chainlit UI.
    result = await workflow.run(company_name)

    # Display the final result or an error message.
    if "error" in result:
        await cl.Message(content=f"Error: {result['error']}").send()
    else:
        report_content = result.get("report", "No report was generated.")
        elements = []
        if "profile" in result and result["profile"]:
            profile = result["profile"]
            profile_text = (
                f"Description: {profile.get('description', 'N/A')}\n"
                f"Website: {profile.get('website', 'N/A')}\n"
                f"Recent Stock Price: ${profile.get('recent_stock_price', 'N/A')}"
            )
            elements.append(
                cl.Text(name=f"{profile.get('display_name', '')} Profile", content=profile_text, display="inline")
            )
        await cl.Message(content=report_content, elements=elements).send()

@cl.on_chat_end
async def end():
    """Optional: Perform cleanup when a user session ends."""
    print("User session ended.")