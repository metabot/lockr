"""
Real-time interactive search for get command.

Provides a minimal interface that shows top 3 recommendations as user types,
with Enter selecting the first result.
"""

from typing import List, Optional, Callable
from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.formatted_text import FormattedText

from .fuzzy import fuzzy_search, highlight_matches, MatchResult


class RealtimeSearchApp:
    """Minimal real-time search interface for get command."""

    def __init__(self, items: List[str], on_select: Callable[[str], None]):
        """
        Initialize the real-time search.

        Args:
            items: List of items to search through
            on_select: Callback function when item is selected
        """
        self.items = items
        self.on_select = on_select
        self.current_results: List[MatchResult] = []
        self.all_matching_results: List[MatchResult] = []  # All matches, not just top 3
        self.selected_index = 0  # Currently selected result index
        self.query = ""

        # Create search buffer
        self.search_buffer = Buffer(
            multiline=False,
            on_text_changed=self._on_search_changed
        )

        # Initialize with empty query (show first 3 items)
        self._update_results("")

        # Create key bindings
        self.bindings = self._create_key_bindings()

        # Create layout
        self.layout = self._create_layout()

        # Create application
        self.app = Application(
            layout=self.layout,
            key_bindings=self.bindings,
            full_screen=False,
            mouse_support=False
        )

    def _create_key_bindings(self) -> KeyBindings:
        """Create key bindings for the interface."""
        bindings = KeyBindings()

        @bindings.add('c-c', 'escape')
        def _(event):
            """Quit without selection."""
            event.app.exit()

        @bindings.add('enter')
        def _(event):
            """Select current highlighted result and exit."""
            if self.current_results and 0 <= self.selected_index < len(self.current_results):
                selected = self.current_results[self.selected_index].text
                self.on_select(selected)
            event.app.exit()

        @bindings.add('tab')
        def _(event):
            """Move to next result."""
            if self.current_results:
                self.selected_index = (self.selected_index + 1) % len(self.current_results)

        @bindings.add('s-tab')  # Shift+Tab
        def _(event):
            """Move to previous result."""
            if self.current_results:
                self.selected_index = (self.selected_index - 1) % len(self.current_results)

        # Also support up/down arrows for navigation (secondary)
        @bindings.add('down')
        def _(event):
            """Move to next result."""
            if self.current_results:
                self.selected_index = (self.selected_index + 1) % len(self.current_results)

        @bindings.add('up')
        def _(event):
            """Move to previous result."""
            if self.current_results:
                self.selected_index = (self.selected_index - 1) % len(self.current_results)

        return bindings

    def _create_layout(self) -> Layout:
        """Create the minimal application layout."""
        # Search input with prompt
        search_window = Window(
            content=BufferControl(
                buffer=self.search_buffer,
                input_processors=[],
            ),
            height=1,
            wrap_lines=False,
        )

        # Results display (top 3 only)
        results_control = FormattedTextControl(
            text=self._get_results_text,
            focusable=False,
            show_cursor=False
        )

        results_window = Window(
            content=results_control,
            height=4,  # Fixed height for 3 results + padding
            wrap_lines=False
        )

        # Status line with match count and instructions
        status_control = FormattedTextControl(
            text=self._get_status_text,
            focusable=False
        )

        status_window = Window(
            content=status_control,
            height=1,
            style="class:status"
        )

        # Create layout with minimal UI
        root_container = HSplit([
            Window(
                content=FormattedTextControl(text="🔍 Interactive Search"),
                height=1,
                style="class:title"
            ),
            search_window,
            results_window,
            status_window,
        ])

        return Layout(root_container, focused_element=search_window)

    def _on_search_changed(self, buffer: Buffer) -> None:
        """Handle search text changes."""
        self.query = buffer.text
        self._update_results(self.query)
        # Reset selection to first item when search changes
        self.selected_index = 0

    def _update_results(self, query: str) -> None:
        """Update search results based on query."""
        if not query:
            # Show first 3 items if no query
            self.all_matching_results = [MatchResult(item, 0.0, []) for item in self.items]
            self.current_results = self.all_matching_results[:3]
        else:
            # Get all fuzzy search results for count, limit display to top 3
            self.all_matching_results = fuzzy_search(query, self.items, limit=100, case_sensitive=False)
            self.current_results = self.all_matching_results[:3]

    def _get_results_text(self) -> FormattedText:
        """Get formatted text for results display."""
        if not self.current_results:
            return FormattedText([("class:no-results", "No matches found\n\n\n")])

        lines = []
        for i, result in enumerate(self.current_results):
            # Highlight currently selected result
            if i == self.selected_index:
                prefix = "❯ "
                style = "class:selected"
            else:
                prefix = "  "
                style = "class:result"

            # Clean display without score (cleaner UI)
            display_text = result.text
            lines.append((style, f"{prefix}{display_text}\n"))

        # Add padding to maintain consistent height
        while len(lines) < 3:
            lines.append(("", "\n"))

        return FormattedText(lines)

    def _get_status_text(self) -> FormattedText:
        """Get formatted text for status line."""
        total_matches = len(self.all_matching_results)

        if total_matches == 0:
            match_info = "No matches"
        elif total_matches <= 3:
            match_info = f"{total_matches} match{'es' if total_matches != 1 else ''}"
        else:
            match_info = f"{total_matches} matches (showing top 3)"

        # Show current selection position if there are results
        if self.current_results:
            selection_info = f" [{self.selected_index + 1}/{len(self.current_results)}]"
        else:
            selection_info = ""

        instructions = " • Tab/↓: next • Shift+Tab/↑: prev • Enter: select • Esc: cancel"

        return FormattedText([
            ("class:match-count", match_info + selection_info),
            ("class:instructions", instructions)
        ])

    def run(self) -> None:
        """Run the real-time search interface."""
        self.app.run()


def realtime_search(items: List[str], on_select: Callable[[str], None]) -> None:
    """
    Show a real-time search interface with top 3 recommendations.

    Args:
        items: List of items to search through
        on_select: Callback function when item is selected with Enter
    """
    if not items:
        print("No items to search through")
        return

    app = RealtimeSearchApp(items, on_select)
    app.run()