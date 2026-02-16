"""FSM states for the bot conversation flow."""

from aiogram.fsm.state import State, StatesGroup


class ProjectStates(StatesGroup):
    """States for the autoload project workflow."""

    # Data collection
    waiting_niche = State()           # Waiting for niche text input
    waiting_pricelist = State()       # Waiting for pricelist .xlsx file
    waiting_competitors = State()     # Waiting for competitors .xlsx file

    # Plan confirmation
    confirming_plan = State()         # Plan shown, waiting for "Start" button

    # CA analysis
    running_ca_analysis = State()     # CA analysis in progress
    confirming_ca = State()           # CA shown, waiting for confirmation
    editing_ca = State()              # User editing CA analysis

    # Description template
    running_template = State()        # Template generation in progress
    confirming_template = State()     # Template shown, waiting for confirmation
    editing_template = State()        # User editing template

    # Categorization
    running_categories = State()      # Categorization in progress
    confirming_categories = State()   # Categories shown, waiting for confirmation

    # Pipeline
    running_pipeline = State()        # File assembly in progress
    complete = State()                # File sent, workflow complete
