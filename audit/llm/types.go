package llm

import "context"

type Client interface {
	SendTextMessage(ctx context.Context, text string, historyMessageKeepNum int) (string, error)
}

type ClaudePromptCache struct {
	Type string `json:"type"`
}
