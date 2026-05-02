from enum import Enum, auto
import database as db

class UserState(Enum):
    IDLE = auto()
    AWAITING_URL = auto()
    AWAITING_FILE = auto()
    AWAITING_AI = auto()
    AWAITING_PAYMENT = auto()

class StateManager:
    @staticmethod
    def set_state(user_id: int, state: UserState):
        """Standardized interface to persist state."""
        state_map = {
            UserState.IDLE: None,
            UserState.AWAITING_URL: "awaiting_url",
            UserState.AWAITING_FILE: "awaiting_file",
            UserState.AWAITING_AI: "awaiting_ai",
            UserState.AWAITING_PAYMENT: "awaiting_payment"
        }
        db.set_user_state(user_id, state_map.get(state))

    @staticmethod
    def get_state(user_id: int) -> UserState:
        """Standardized interface to retrieve state."""
        raw_state = db.get_user_state(user_id)
        reverse_map = {
            "awaiting_url": UserState.AWAITING_URL,
            "awaiting_file": UserState.AWAITING_FILE,
            "awaiting_ai": UserState.AWAITING_AI,
            "awaiting_payment": UserState.AWAITING_PAYMENT
        }
        return reverse_map.get(raw_state, UserState.IDLE)
