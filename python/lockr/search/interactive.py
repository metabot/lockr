"""
Interactive fuzzy search interface for Lockr using prompt_toolkit.

This provides an FZF-like interactive interface for searching through vault keys.
"""

from typing import List, Optional, Callable, Any
from prompt_toolkit import Application
from prompt_toolkit.application import get_app
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, Window, ScrollOffsets
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.widgets import SearchToolbar, Frame
from prompt_toolkit.filters import Condition
from prompt_toolkit.shortcuts import CompleteStyle

from .fuzzy import fuzzy_search, highlight_matches, MatchResult


class FuzzySelector:
    """Interactive fuzzy search selector similar to FZF."""

    def __init__(self, items: List[str], title: str = "Select item",
                 max_results: int = 10, case_sensitive: bool = False):
        """
        Initialize the fuzzy selector.

        Args:
            items: List of items to search through
            title: Title to display at the top
            max_results: Maximum number of results to show
            case_sensitive: Whether search should be case sensitive
        """
        self.items = items
        self.title = title
        self.max_results = max_results
        self.case_sensitive = case_sensitive
        self.selected_index = 0
        self.current_results: List[MatchResult] = []
        self.selected_item: Optional[str] = None

        # Create search buffer
        self.search_buffer = Buffer(
            multiline=False,
            on_text_changed=self._on_search_changed
        )

        # Initialize with all items
        self._update_results("")

        # Create key bindings
        self.bindings = self._create_key_bindings()

        # Create layout
        self.layout = self._create_layout()

        # Create application
        self.app = Application(
            layout=self.layout,
            key_bindings=self.bindings,
            full_screen=True,
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
            """Select current item and exit."""
            if self.current_results and 0 <= self.selected_index < len(self.current_results):
                self.selected_item = self.current_results[self.selected_index].text
            event.app.exit()

        @bindings.add('up', 'c-p')
        def _(event):
            """Move selection up."""
            if self.current_results:
                self.selected_index = max(0, self.selected_index - 1)

        @bindings.add('down', 'c-n')
        def _(event):
            """Move selection down."""
            if self.current_results:
                self.selected_index = min(len(self.current_results) - 1, self.selected_index + 1)

        @bindings.add('pageup')
        def _(event):
            """Move selection up by page."""
            if self.current_results:
                self.selected_index = max(0, self.selected_index - 5)

        @bindings.add('pagedown')
        def _(event):
            """Move selection down by page."""
            if self.current_results:
                self.selected_index = min(len(self.current_results) - 1, self.selected_index + 5)

        @bindings.add('home')
        def _(event):
            """Move to first item."""
            self.selected_index = 0

        @bindings.add('end')
        def _(event):
            """Move to last item."""
            if self.current_results:
                self.selected_index = len(self.current_results) - 1

        return bindings

    def _create_layout(self) -> Layout:
        """Create the application layout."""
        # Results display
        results_control = FormattedTextControl(
            text=self._get_results_text,
            focusable=False,
            show_cursor=False
        )

        results_window = Window(
            content=results_control,
            height=lambda: min(self.max_results, len(self.current_results)) + 2,
            scroll_offsets=ScrollOffsets(top=1, bottom=1)
        )

        # Search input
        search_window = Window(
            content=BufferControl(
                buffer=self.search_buffer,
                input_processors=[],
            ),
            height=1,
            wrap_lines=False,
        )

        # Info line
        info_control = FormattedTextControl(
            text=self._get_info_text,
            focusable=False
        )

        info_window = Window(
            content=info_control,
            height=1,
            style="class:info"
        )

        # Create layout
        root_container = HSplit([
            Window(
                content=FormattedTextControl(text=self.title),
                height=1,
                style="class:title"
            ),
            Window(height=1, char='─', style="class:line"),  # Separator
            search_window,
            Window(height=1, char='─', style="class:line"),  # Separator
            results_window,
            info_window,
        ])

        return Layout(root_container, focused_element=search_window)

    def _on_search_changed(self, buffer: Buffer) -> None:
        """Handle search text changes."""
        query = buffer.text
        self._update_results(query)
        self.selected_index = 0  # Reset selection to top

    def _update_results(self, query: str) -> None:
        """Update search results based on query."""
        if not query:
            # Show all items if no query
            self.current_results = [
                MatchResult(item, 0.0, []) for item in self.items[:self.max_results]
            ]
        else:
            self.current_results = fuzzy_search(
                query, self.items, self.max_results, self.case_sensitive
            )

    def _get_results_text(self) -> FormattedText:
        """Get formatted text for results display."""
        if not self.current_results:
            return FormattedText([("class:no-results", "No matches found")])

        lines = []
        for i, result in enumerate(self.current_results):
            prefix = "❯ " if i == self.selected_index else "  "
            style = "class:selected" if i == self.selected_index else "class:result"

            if result.positions:
                # Highlight matches
                highlighted = highlight_matches(
                    result.text, result.positions,
                    start_marker="",  # We'll use styles instead
                    end_marker=""
                )
                # For now, just show the text (highlighting can be improved)
                display_text = result.text
            else:
                display_text = result.text

            lines.append((style, f"{prefix}{display_text}\n"))

        return FormattedText(lines)

    def _get_info_text(self) -> FormattedText:
        """Get formatted text for info line."""
        total = len(self.items)
        matches = len(self.current_results)
        selected = self.selected_index + 1 if self.current_results else 0

        info = f"{matches}/{total}"
        if self.current_results:
            info += f" [{selected}/{matches}]"

        instructions = " • Press ↑↓ to navigate, Enter to select, Esc to cancel"

        return FormattedText([
            ("class:info", info),
            ("class:instructions", instructions)
        ])

    def run(self) -> Optional[str]:
        """
        Run the interactive selector.

        Returns:
            Selected item or None if cancelled
        """
        self.app.run()
        return self.selected_item


def interactive_search(items: List[str], title: str = "Select item",
                      max_results: int = 10, case_sensitive: bool = False) -> Optional[str]:
    """
    Show an interactive fuzzy search interface.

    Args:
        items: List of items to search through
        title: Title to display
        max_results: Maximum number of results to show
        case_sensitive: Whether search should be case sensitive

    Returns:
        Selected item or None if cancelled
    """
    if not items:
        return None

    selector = FuzzySelector(items, title, max_results, case_sensitive)
    return selector.run()