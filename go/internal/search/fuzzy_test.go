package search

import (
	"fmt"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/lockr/go/internal/database"
)

func TestEngine_BasicSearch(t *testing.T) {
	engine := NewEngine()

	// Create test data
	secrets := []database.SearchResult{
		{Key: "api_key_github", CreatedAt: time.Now(), AccessCount: 5},
		{Key: "api_key_stripe", CreatedAt: time.Now(), AccessCount: 3},
		{Key: "database_password", CreatedAt: time.Now(), AccessCount: 10},
		{Key: "user_password", CreatedAt: time.Now(), AccessCount: 8},
		{Key: "github_token", CreatedAt: time.Now(), AccessCount: 2},
	}

	// Test exact match
	results := engine.Search("api_key_github", secrets)
	require.Greater(t, len(results), 0)
	assert.Equal(t, "api_key_github", results[0].Result.Key)
	assert.Equal(t, 100.0, results[0].Score)

	// Test prefix match
	results = engine.Search("api", secrets)
	require.GreaterOrEqual(t, len(results), 2)

	// Should find both api_key entries
	found := make(map[string]bool)
	for _, result := range results {
		if result.Result.Key == "api_key_github" || result.Result.Key == "api_key_stripe" {
			found[result.Result.Key] = true
		}
	}
	assert.Len(t, found, 2)

	// Test fuzzy match
	results = engine.Search("github", secrets)
	require.Greater(t, len(results), 0)

	// Should find both github-related entries
	githubFound := false
	tokenFound := false
	for _, result := range results {
		if result.Result.Key == "api_key_github" {
			githubFound = true
		}
		if result.Result.Key == "github_token" {
			tokenFound = true
		}
	}
	assert.True(t, githubFound)
	assert.True(t, tokenFound)
}

func TestEngine_Scoring(t *testing.T) {
	engine := NewEngine()

	secrets := []database.SearchResult{
		{Key: "test", CreatedAt: time.Now()},
		{Key: "test_key", CreatedAt: time.Now()},
		{Key: "my_test", CreatedAt: time.Now()},
		{Key: "something_test_else", CreatedAt: time.Now()},
	}

	results := engine.Search("test", secrets)
	require.GreaterOrEqual(t, len(results), 4)

	// Exact match should have highest score
	assert.Equal(t, "test", results[0].Result.Key)
	assert.Equal(t, 100.0, results[0].Score)

	// Prefix match should have higher score than substring match
	prefixScore := 0.0
	substringScore := 0.0

	for _, result := range results {
		if result.Result.Key == "test_key" {
			prefixScore = result.Score
		}
		if result.Result.Key == "my_test" {
			substringScore = result.Score
		}
	}

	assert.Greater(t, prefixScore, substringScore)
}

func TestEngine_CaseSensitivity(t *testing.T) {
	engine := NewEngine()
	engine.SetCaseSensitive(false) // Default

	secrets := []database.SearchResult{
		{Key: "TestKey", CreatedAt: time.Now()},
		{Key: "TESTKEY", CreatedAt: time.Now()},
		{Key: "testkey", CreatedAt: time.Now()},
	}

	// Case-insensitive search
	results := engine.Search("testkey", secrets)
	assert.Len(t, results, 3)

	// Case-sensitive search
	engine.SetCaseSensitive(true)
	results = engine.Search("testkey", secrets)
	assert.Len(t, results, 1)
	assert.Equal(t, "testkey", results[0].Result.Key)
}

func TestEngine_MaxResults(t *testing.T) {
	engine := NewEngine()
	engine.SetMaxResults(2)

	secrets := make([]database.SearchResult, 10)
	for i := 0; i < 10; i++ {
		secrets[i] = database.SearchResult{
			Key:       fmt.Sprintf("key_%d", i),
			CreatedAt: time.Now(),
		}
	}

	results := engine.Search("key", secrets)
	assert.LessOrEqual(t, len(results), 2)
}

func TestEngine_Highlights(t *testing.T) {
	engine := NewEngine()
	engine.SetHighlightMatches(true)

	secrets := []database.SearchResult{
		{Key: "api_key_github", CreatedAt: time.Now()},
	}

	results := engine.Search("github", secrets)
	require.Greater(t, len(results), 0)

	result := results[0]
	assert.Greater(t, len(result.Highlights), 0)

	// Check that highlight ranges are valid
	for _, highlight := range result.Highlights {
		assert.GreaterOrEqual(t, highlight.Start, 0)
		assert.LessOrEqual(t, highlight.End, len(result.Result.Key))
		assert.Less(t, highlight.Start, highlight.End)
	}
}

func TestEngine_EmptyQuery(t *testing.T) {
	engine := NewEngine()

	secrets := []database.SearchResult{
		{Key: "key1", CreatedAt: time.Now()},
		{Key: "key2", CreatedAt: time.Now()},
	}

	// Empty query should return all results with zero score
	results := engine.Search("", secrets)
	assert.Len(t, results, 2)
	for _, result := range results {
		assert.Equal(t, 0.0, result.Score)
	}
}

func TestEngine_NoMatches(t *testing.T) {
	engine := NewEngine()

	secrets := []database.SearchResult{
		{Key: "api_key", CreatedAt: time.Now()},
		{Key: "database", CreatedAt: time.Now()},
	}

	results := engine.Search("xyz123", secrets)
	assert.Len(t, results, 0)
}

func TestEngine_InteractiveSearch(t *testing.T) {
	engine := NewEngine()

	secrets := make([]database.SearchResult, 20)
	for i := 0; i < 20; i++ {
		secrets[i] = database.SearchResult{
			Key:       fmt.Sprintf("key_%d", i),
			CreatedAt: time.Now(),
		}
	}

	results := engine.SearchInteractive("key", secrets, 5)
	assert.LessOrEqual(t, len(results), 5)
}

func TestEngine_QuerySuggestions(t *testing.T) {
	engine := NewEngine()

	secrets := []database.SearchResult{
		{Key: "api_key_github", CreatedAt: time.Now()},
		{Key: "api_key_stripe", CreatedAt: time.Now()},
		{Key: "api_token", CreatedAt: time.Now()},
		{Key: "database", CreatedAt: time.Now()},
	}

	suggestions := engine.GetQuerySuggestions("api", secrets, 10)
	assert.GreaterOrEqual(t, len(suggestions), 3)

	// All suggestions should start with "api"
	for _, suggestion := range suggestions {
		assert.Contains(t, suggestion, "api")
	}
}

func TestEngine_MatchQuality(t *testing.T) {
	engine := NewEngine()

	assert.Equal(t, ExactMatch, engine.GetMatchQuality("test", "test"))
	assert.Equal(t, PrefixMatch, engine.GetMatchQuality("test", "test_key"))
	assert.Equal(t, SubstringMatch, engine.GetMatchQuality("test", "my_test_key"))
	assert.Equal(t, NoMatch, engine.GetMatchQuality("xyz", "abc"))
}
