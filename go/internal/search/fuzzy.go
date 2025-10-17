package search

import (
	"sort"
	"strings"

	"github.com/lockr/go/internal/database"
)

// MatchResult represents a search match with scoring information
type MatchResult struct {
	Result     database.SearchResult `json:"result"`
	Score      float64               `json:"score"`
	Highlights []HighlightRange      `json:"highlights,omitempty"`
}

// HighlightRange represents a character range to highlight in the match
type HighlightRange struct {
	Start int `json:"start"`
	End   int `json:"end"`
}

// Engine provides fuzzy search capabilities for secrets
type Engine struct {
	// Configuration options
	caseSensitive    bool
	maxResults       int
	highlightMatches bool
}

// NewEngine creates a new fuzzy search engine with default settings
func NewEngine() *Engine {
	return &Engine{
		caseSensitive:    false,
		maxResults:       100,
		highlightMatches: true,
	}
}

// SetCaseSensitive configures case sensitivity for searches
func (e *Engine) SetCaseSensitive(sensitive bool) {
	e.caseSensitive = sensitive
}

// SetMaxResults sets the maximum number of results to return
func (e *Engine) SetMaxResults(max int) {
	e.maxResults = max
}

// SetHighlightMatches enables or disables match highlighting
func (e *Engine) SetHighlightMatches(highlight bool) {
	e.highlightMatches = highlight
}

// Search performs fuzzy search on the provided secrets
func (e *Engine) Search(query string, secrets []database.SearchResult) []MatchResult {
	if len(query) == 0 {
		// Return all results with score 0 when no query
		results := make([]MatchResult, len(secrets))
		for i, secret := range secrets {
			results[i] = MatchResult{
				Result: secret,
				Score:  0.0,
			}
		}
		return e.limitResults(results)
	}

	var matches []MatchResult

	// Score each secret against the query
	for _, secret := range secrets {
		if score, highlights := e.scoreMatch(query, secret.Key); score > 0 {
			match := MatchResult{
				Result: secret,
				Score:  score,
			}

			if e.highlightMatches {
				match.Highlights = highlights
			}

			matches = append(matches, match)
		}
	}

	// Sort by score (descending) and then by key (ascending) for tie-breaking
	sort.Slice(matches, func(i, j int) bool {
		if matches[i].Score != matches[j].Score {
			return matches[i].Score > matches[j].Score
		}
		// Tie-breaker: prefer keys that start with the query
		iKey := e.normalizeString(matches[i].Result.Key)
		jKey := e.normalizeString(matches[j].Result.Key)
		queryNorm := e.normalizeString(query)

		iStartsWith := strings.HasPrefix(iKey, queryNorm)
		jStartsWith := strings.HasPrefix(jKey, queryNorm)

		if iStartsWith != jStartsWith {
			return iStartsWith
		}

		// Final tie-breaker: alphabetical order
		return iKey < jKey
	})

	return e.limitResults(matches)
}

// scoreMatch calculates a fuzzy match score between query and target
func (e *Engine) scoreMatch(query, target string) (float64, []HighlightRange) {
	queryNorm := e.normalizeString(query)
	targetNorm := e.normalizeString(target)

	// Exact match gets highest score
	if queryNorm == targetNorm {
		highlights := []HighlightRange{{Start: 0, End: len(target)}}
		return 100.0, highlights
	}

	// Check for prefix match
	if strings.HasPrefix(targetNorm, queryNorm) {
		highlights := []HighlightRange{{Start: 0, End: len(query)}}
		return 90.0, highlights
	}

	// Check for substring match
	if idx := strings.Index(targetNorm, queryNorm); idx >= 0 {
		highlights := []HighlightRange{{Start: idx, End: idx + len(query)}}
		score := 80.0 - float64(idx)*2.0 // Prefer matches earlier in the string
		if score < 50.0 {
			score = 50.0
		}
		return score, highlights
	}

	// Fuzzy matching using character-by-character scoring
	score, highlights := e.fuzzyScore(queryNorm, targetNorm, target)
	if score > 0 {
		return score, highlights
	}

	return 0.0, nil
}

// fuzzyScore performs character-by-character fuzzy matching
func (e *Engine) fuzzyScore(query, target, originalTarget string) (float64, []HighlightRange) {
	if len(query) == 0 || len(target) == 0 {
		return 0.0, nil
	}

	queryRunes := []rune(query)
	targetRunes := []rune(target)
	originalRunes := []rune(originalTarget)

	// Track matched positions for highlighting
	var matchedPositions []int

	queryPos := 0
	targetPos := 0
	consecutiveMatches := 0
	totalScore := 0.0

	for queryPos < len(queryRunes) && targetPos < len(targetRunes) {
		if queryRunes[queryPos] == targetRunes[targetPos] {
			// Character match
			matchedPositions = append(matchedPositions, targetPos)

			consecutiveMatches++
			// Bonus for consecutive matches
			charScore := 2.0 + float64(consecutiveMatches)*0.5
			totalScore += charScore

			queryPos++
			targetPos++
		} else {
			// No match - move to next target character
			consecutiveMatches = 0
			targetPos++
		}
	}

	// Check if we matched all query characters
	if queryPos < len(queryRunes) {
		return 0.0, nil // Not all query characters were found
	}

	// Calculate final score based on match ratio and penalties
	matchRatio := float64(len(matchedPositions)) / float64(len(queryRunes))
	lengthRatio := float64(len(queryRunes)) / float64(len(targetRunes))

	finalScore := totalScore * matchRatio * lengthRatio * 20.0 // Scale to reasonable range

	// Ensure minimum score threshold
	if finalScore < 10.0 {
		finalScore = 10.0
	}

	// Convert matched positions to highlights
	var highlights []HighlightRange
	if len(matchedPositions) > 0 {
		highlights = e.createHighlights(matchedPositions, originalRunes)
	}

	return finalScore, highlights
}

// createHighlights converts matched positions into highlight ranges
func (e *Engine) createHighlights(positions []int, original []rune) []HighlightRange {
	if len(positions) == 0 {
		return nil
	}

	var highlights []HighlightRange
	start := positions[0]
	end := positions[0] + 1

	for i := 1; i < len(positions); i++ {
		if positions[i] == positions[i-1]+1 {
			// Consecutive position - extend current range
			end = positions[i] + 1
		} else {
			// Non-consecutive - finalize current range and start new one
			highlights = append(highlights, HighlightRange{Start: start, End: end})
			start = positions[i]
			end = positions[i] + 1
		}
	}

	// Add the final range
	highlights = append(highlights, HighlightRange{Start: start, End: end})

	return highlights
}

// normalizeString normalizes a string for comparison
func (e *Engine) normalizeString(s string) string {
	if e.caseSensitive {
		return s
	}
	return strings.ToLower(s)
}

// limitResults limits the number of results returned
func (e *Engine) limitResults(results []MatchResult) []MatchResult {
	if len(results) <= e.maxResults {
		return results
	}
	return results[:e.maxResults]
}

// FilterTopMatches returns the top N matches with a minimum score threshold
func (e *Engine) FilterTopMatches(matches []MatchResult, maxResults int, minScore float64) []MatchResult {
	var filtered []MatchResult

	for _, match := range matches {
		if match.Score >= minScore && len(filtered) < maxResults {
			filtered = append(filtered, match)
		}
	}

	return filtered
}

// SearchInteractive performs a search optimized for interactive use
func (e *Engine) SearchInteractive(query string, secrets []database.SearchResult, maxResults int) []MatchResult {
	// For interactive search, we want fast response with limited results
	oldMax := e.maxResults
	e.SetMaxResults(maxResults)

	results := e.Search(query, secrets)

	// Restore original setting
	e.SetMaxResults(oldMax)

	return results
}

// GetQuerySuggestions provides query suggestions based on available keys
func (e *Engine) GetQuerySuggestions(partialQuery string, secrets []database.SearchResult, maxSuggestions int) []string {
	if len(partialQuery) == 0 {
		return nil
	}

	queryNorm := e.normalizeString(partialQuery)
	var suggestions []string
	seen := make(map[string]bool)

	for _, secret := range secrets {
		keyNorm := e.normalizeString(secret.Key)

		// Add keys that start with the partial query
		if strings.HasPrefix(keyNorm, queryNorm) && !seen[secret.Key] {
			suggestions = append(suggestions, secret.Key)
			seen[secret.Key] = true
		}

		if len(suggestions) >= maxSuggestions {
			break
		}
	}

	return suggestions
}

// MatchQuality represents the quality of a match
type MatchQuality int

const (
	ExactMatch MatchQuality = iota
	PrefixMatch
	SubstringMatch
	FuzzyMatch
	NoMatch
)

// GetMatchQuality determines the quality of a match
func (e *Engine) GetMatchQuality(query, target string) MatchQuality {
	queryNorm := e.normalizeString(query)
	targetNorm := e.normalizeString(target)

	if queryNorm == targetNorm {
		return ExactMatch
	}

	if strings.HasPrefix(targetNorm, queryNorm) {
		return PrefixMatch
	}

	if strings.Contains(targetNorm, queryNorm) {
		return SubstringMatch
	}

	// Check for fuzzy match
	if score, _ := e.fuzzyScore(queryNorm, targetNorm, target); score > 0 {
		return FuzzyMatch
	}

	return NoMatch
}
