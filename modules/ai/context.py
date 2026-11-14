"""
modules/ai/context.py

Conversation context manager for Milestone 1.

Maintains a rolling window of turns (user + assistant) and handles
interruptions gracefully. When the user interrupts, we record it as a
special turn so the model understands it should pivot without apologising.

A conversation ends by itself after ``idle_reset_sec`` without a turn (the user
closed SAINT and came back later: "my sound isn't working" from an hour ago is
not today's topic). Turns that scroll out of the window leave a one-line note
("Earlier: ...") instead of vanishing, so a long chat keeps its thread without
re-sending every word.
"""

import threading
import time
from typing import List, Dict


class ConversationContext:
    """Thread-safe rolling-window conversation history."""

    def __init__(self, max_turns: int = 6, system_prompt: str = "", idle_reset_sec: float = 0.0,
                 clock=time.monotonic):
        self._lock = threading.Lock()
        self._idle_reset = float(idle_reset_sec or 0)
        self._clock = clock
        self._last = clock()
        self._earlier: List[str] = []      # what scrolled out of the window, a few words each
        self._system_prompt = system_prompt
        self._max_turns = max_turns   # each turn = 1 user + 1 assistant message

        # Internal history: list of {"role": "user"|"assistant", "content": str}
        self._history: List[Dict[str, str]] = []

        # Metadata for analytics / acceptance tests
        self.current_topic: str = ""
        self.current_question: str = ""
        self.previous_answer: str = ""
        self.previous_interruption: str = ""

    # ------------------------------------------------------------------ #
    # Mutations
    # ------------------------------------------------------------------ #
    def _touch(self):
        """A new turn: after a long silence the old conversation is over."""
        now = self._clock()
        if self._idle_reset and now - self._last > self._idle_reset and self._history:
            self._history.clear()
            self._earlier.clear()
            self.current_topic = self.previous_answer = self.previous_interruption = ""
        self._last = now

    def add_user_turn(self, text: str):
        with self._lock:
            self._touch()
            self.current_question = text
            self._history.append({"role": "user", "content": text})
            self._trim()

    def add_assistant_turn(self, text: str):
        with self._lock:
            self.previous_answer = text
            self._history.append({"role": "assistant", "content": text})
            self._trim()

    def handle_interruption(self, new_user_text: str):
        """
        Called when the user interrupts SAINT mid-sentence.

        Inserts a special marker so the LLM understands the context:
        the previous assistant response was cut off, and the user is
        redirecting. The model should pivot naturally, not apologise.
        """
        with self._lock:
            self._touch()
            self.previous_interruption = new_user_text

            # Mark the incomplete assistant turn (if any trailing assistant entry)
            if self._history and self._history[-1]["role"] == "assistant":
                partial = self._history[-1]["content"]
                self._history[-1]["content"] = partial + " [interrupted]"
            elif self._history and self._history[-1]["role"] == "user":
                # No assistant turn yet — the user's question was interrupted
                # before SAINT could respond. Mark the user's question.
                self._history[-1]["content"] = self._history[-1]["content"] + " [interrupted]"

            self._history.append({
                "role": "user",
                "content": new_user_text,
            })
            self.current_question = new_user_text
            self._trim()

    def clear(self):
        with self._lock:
            self._history.clear()
            self._earlier.clear()
            self.current_topic = ""
            self.current_question = ""
            self.previous_answer = ""
            self.previous_interruption = ""

    # ------------------------------------------------------------------ #
    # Formatting for the LLM
    # ------------------------------------------------------------------ #
    def format_messages(self) -> List[Dict[str, str]]:
        """Returns the message list suitable for an OpenAI-style API."""
        with self._lock:
            messages = []
            if self._system_prompt:
                messages.append({"role": "system", "content": self._system_prompt})
            if self._earlier:
                messages.append({"role": "system", "content": "Earlier in this conversation the user asked about: "
                                 + "; ".join(self._earlier) + "."})
            messages.extend(list(self._history))
            return messages

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #
    def _trim(self):
        """Keep at most max_turns * 2 messages (pairs of user + assistant)."""
        max_msgs = self._max_turns * 2
        if len(self._history) > max_msgs:
            dropped, self._history = self._history[:-max_msgs], self._history[-max_msgs:]
            for m in dropped:
                if m["role"] == "user":
                    words = m["content"].replace(" [interrupted]", "").split()
                    self._earlier.append(" ".join(words[:8]) + ("..." if len(words) > 8 else ""))
            self._earlier = self._earlier[-4:]

    def __len__(self):
        with self._lock:
            return len(self._history)
