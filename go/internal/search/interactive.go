package search

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"github.com/lockr/go/internal/database"
)

const (
	// MaxDisplayResults is the maximum number of results to show in the interactive UI
	MaxDisplayResults = 5
)

// InteractiveSearch provides a real-time fuzzy search interface
type InteractiveSearch struct {
	engine   *Engine
	secrets  []database.SearchResult
	results  []MatchResult
	query    string
	selected int
	active   bool
	styles   InteractiveStyles
}

// InteractiveStyles defines the visual styling for the interactive search
type InteractiveStyles struct {
	QueryPrompt    lipgloss.Style
	QueryInput     lipgloss.Style
	ResultSelected lipgloss.Style
	ResultNormal   lipgloss.Style
	ResultKey      lipgloss.Style
	ResultMeta     lipgloss.Style
	Highlight      lipgloss.Style
	MoreIndicator  lipgloss.Style
	NoResults      lipgloss.Style
}

// NewInteractiveSearch creates a new interactive search instance
func NewInteractiveSearch(secrets []database.SearchResult) *InteractiveSearch {
	engine := NewEngine()
	engine.SetMaxResults(MaxDisplayResults * 2) // Get more results for better filtering

	return &InteractiveSearch{
		engine:   engine,
		secrets:  secrets,
		results:  []MatchResult{},
		query:    "",
		selected: 0,
		active:   true,
		styles:   defaultInteractiveStyles(),
	}
}

// defaultInteractiveStyles returns the default styling configuration
func defaultInteractiveStyles() InteractiveStyles {
	return InteractiveStyles{
		QueryPrompt: lipgloss.NewStyle().
			Foreground(lipgloss.Color("32")). // Green
			Bold(true),
		QueryInput: lipgloss.NewStyle().
			Foreground(lipgloss.Color("255")). // White
			Background(lipgloss.Color("238")), // Dark gray
		ResultSelected: lipgloss.NewStyle().
			Foreground(lipgloss.Color("0")).  // Black
			Background(lipgloss.Color("14")), // Cyan
		ResultNormal: lipgloss.NewStyle().
			Foreground(lipgloss.Color("255")), // White
		ResultKey: lipgloss.NewStyle().
			Foreground(lipgloss.Color("220")). // Yellow
			Bold(true),
		ResultMeta: lipgloss.NewStyle().
			Foreground(lipgloss.Color("241")), // Gray
		Highlight: lipgloss.NewStyle().
			Foreground(lipgloss.Color("11")). // Bright yellow
			Bold(true),
		MoreIndicator: lipgloss.NewStyle().
			Foreground(lipgloss.Color("242")), // Dark gray
		NoResults: lipgloss.NewStyle().
			Foreground(lipgloss.Color("red")).
			Italic(true),
	}
}

// Model represents the state for the Bubble Tea model
type Model struct {
	search   *InteractiveSearch
	quitting bool
	selected *MatchResult
}

// NewModel creates a new Bubble Tea model for interactive search
func NewModel(secrets []database.SearchResult) Model {
	return Model{
		search: NewInteractiveSearch(secrets),
	}
}

// Init initializes the model (required by Bubble Tea)
func (m Model) Init() tea.Cmd {
	return nil
}

// Update handles messages and updates the model state
func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.KeyMsg:
		switch msg.String() {
		case "ctrl+c", "esc":
			m.quitting = true
			return m, tea.Quit

		case "enter":
			if len(m.search.results) > 0 && m.search.selected < len(m.search.results) {
				m.selected = &m.search.results[m.search.selected]
			}
			return m, tea.Quit

		case "up", "ctrl+p":
			m.search.MoveSelection(-1)

		case "down", "ctrl+n":
			m.search.MoveSelection(1)

		case "backspace":
			m.search.RemoveChar()

		default:
			// Add character to query
			if len(msg.String()) == 1 && msg.String()[0] >= 32 { // Printable characters
				m.search.AddChar(msg.String()[0])
			}
		}
	}

	return m, nil
}

// View renders the current state of the model
func (m Model) View() string {
	if m.quitting {
		return ""
	}

	return m.search.Render()
}

// AddChar adds a character to the search query and updates results
func (is *InteractiveSearch) AddChar(ch byte) {
	is.query += string(ch)
	is.updateResults()
	is.selected = 0 // Reset selection when query changes
}

// RemoveChar removes the last character from the search query
func (is *InteractiveSearch) RemoveChar() {
	if len(is.query) > 0 {
		is.query = is.query[:len(is.query)-1]
		is.updateResults()
		is.selected = 0 // Reset selection when query changes
	}
}

// MoveSelection moves the selection cursor up or down
func (is *InteractiveSearch) MoveSelection(direction int) {
	if len(is.results) == 0 {
		return
	}

	is.selected += direction

	if is.selected < 0 {
		is.selected = len(is.results) - 1
	} else if is.selected >= len(is.results) {
		is.selected = 0
	}
}

// GetSelectedResult returns the currently selected result
func (is *InteractiveSearch) GetSelectedResult() *MatchResult {
	if len(is.results) == 0 || is.selected < 0 || is.selected >= len(is.results) {
		return nil
	}
	return &is.results[is.selected]
}

// updateResults refreshes the search results based on the current query
func (is *InteractiveSearch) updateResults() {
	allResults := is.engine.Search(is.query, is.secrets)

	// Limit to display results
	displayCount := MaxDisplayResults
	if len(allResults) < displayCount {
		displayCount = len(allResults)
	}

	is.results = allResults[:displayCount]

	// Ensure selection is within bounds
	if is.selected >= len(is.results) {
		is.selected = len(is.results) - 1
	}
	if is.selected < 0 && len(is.results) > 0 {
		is.selected = 0
	}
}

// Render renders the interactive search interface
func (is *InteractiveSearch) Render() string {
	var b strings.Builder

	// Render query prompt and input
	b.WriteString(is.styles.QueryPrompt.Render("Search: "))
	b.WriteString(is.styles.QueryInput.Render(is.query))

	// Add cursor indicator
	b.WriteString("█")
	b.WriteString("\n\n")

	// Render results
	if len(is.results) == 0 {
		if len(is.query) > 0 {
			b.WriteString(is.styles.NoResults.Render("No matches found"))
		} else {
			b.WriteString(is.styles.ResultMeta.Render("Start typing to search..."))
		}
	} else {
		for i, result := range is.results {
			line := is.renderResult(result, i == is.selected)
			b.WriteString(line)
			b.WriteString("\n")
		}

		// Show "more results" indicator if there are additional matches
		totalMatches := len(is.engine.Search(is.query, is.secrets))
		if totalMatches > len(is.results) {
			moreCount := totalMatches - len(is.results)
			moreText := fmt.Sprintf("... and %d more results", moreCount)
			b.WriteString(is.styles.MoreIndicator.Render(moreText))
			b.WriteString("\n")
		}
	}

	// Add help text
	b.WriteString("\n")
	b.WriteString(is.styles.ResultMeta.Render("Use ↑/↓ to navigate, Enter to select, Esc to cancel"))

	return b.String()
}

// renderResult renders a single search result
func (is *InteractiveSearch) renderResult(result MatchResult, selected bool) string {
	key := result.Result.Key

	// Apply highlighting if available
	if len(result.Highlights) > 0 {
		key = is.applyHighlights(key, result.Highlights)
	}

	// Format metadata
	meta := fmt.Sprintf("(accessed %d times)", result.Result.AccessCount)

	// Combine key and metadata
	var content string
	if selected {
		content = is.styles.ResultSelected.Render(fmt.Sprintf(" %s ", key)) +
			" " + is.styles.ResultMeta.Render(meta)
	} else {
		styledKey := is.styles.ResultKey.Render(key)
		content = "  " + styledKey + " " + is.styles.ResultMeta.Render(meta)
	}

	return content
}

// applyHighlights applies highlighting to matched portions of text
func (is *InteractiveSearch) applyHighlights(text string, highlights []HighlightRange) string {
	if len(highlights) == 0 {
		return text
	}

	runes := []rune(text)
	var result strings.Builder

	pos := 0
	for _, highlight := range highlights {
		// Add text before highlight
		if highlight.Start > pos {
			result.WriteString(string(runes[pos:highlight.Start]))
		}

		// Add highlighted text
		if highlight.End <= len(runes) {
			highlightedText := string(runes[highlight.Start:highlight.End])
			result.WriteString(is.styles.Highlight.Render(highlightedText))
			pos = highlight.End
		}
	}

	// Add remaining text
	if pos < len(runes) {
		result.WriteString(string(runes[pos:]))
	}

	return result.String()
}

// RunInteractiveSearch runs the interactive search and returns the selected key
func RunInteractiveSearch(secrets []database.SearchResult) (string, error) {
	model := NewModel(secrets)

	program := tea.NewProgram(model)
	finalModel, err := program.Run()
	if err != nil {
		return "", fmt.Errorf("error running interactive search: %w", err)
	}

	// Get the result from the final model
	final := finalModel.(Model)
	if final.selected != nil {
		return final.selected.Result.Key, nil
	}

	return "", nil // User cancelled or no selection made
}

// GetSelectedKey returns the key of the currently selected result
func (m Model) GetSelectedKey() string {
	if m.selected != nil {
		return m.selected.Result.Key
	}
	return ""
}
