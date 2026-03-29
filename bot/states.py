from aiogram.fsm.state import State, StatesGroup


class TournamentCreation(StatesGroup):
    name = State()
    max_participants = State()
    format = State()
    payment_type = State()
    price = State()
    card_number = State()


class PlayerRegistration(StatesGroup):
    game_id = State()
    team_name = State()
    phone = State()
    payment_screenshot = State()


class ResultSubmission(StatesGroup):
    select_match = State()
    score = State()
    screenshot = State()
