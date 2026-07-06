package llm

import (
	"os"
	"context"
	"github.com/openai/openai-go"
	"github.com/openai/openai-go/option"
	"github.com/rs/zerolog/log"
	"fmt"
)

type OpenAIClient struct {
	Client              openai.Client
	MessageHistory      []openai.ChatCompletionMessageParamUnion
	MessageHistoryLimit int
	SystemPrompt        string
	Model               string
}

func NewOpenAIClient(model string, systemPrompt string) (*OpenAIClient, error) {
	apikey := os.Getenv("OPENAI_API_KEY")
	if apikey == "" {
		log.Error().Msg("openai: API key is missing")
		return nil, fmt.Errorf("audit: API key is missing")
	}

	clientOpts := []option.RequestOption{option.WithAPIKey(apikey)}
	// Allow pointing at an OpenAI-compatible endpoint (e.g. a host Ollama server
	// exposing gpt-oss) via OPENAI_BASE_URL, like http://<host-ip>:11434/v1.
	if baseURL := os.Getenv("OPENAI_BASE_URL"); baseURL != "" {
		clientOpts = append(clientOpts, option.WithBaseURL(baseURL))
		log.Debug().Msgf("openai: using custom base URL %s", baseURL)
	}

	oc := &OpenAIClient{
		Client:         openai.NewClient(clientOpts...),
		MessageHistory: []openai.ChatCompletionMessageParamUnion{},
		SystemPrompt:   systemPrompt,
		Model:          model,
	}

	return oc, nil
}

func (cc *OpenAIClient) SendTextMessage(ctx context.Context, text string, historyMessageKeepNum int) (string, error) {
	//if historyMessageKeepNum > len(cc.MessageHistory) {
	//	historyMessageKeepNum = len(cc.MessageHistory)
	//}
	//
	//messages := cc.MessageHistory[len(cc.MessageHistory)-historyMessageKeepNum:]

	log.Debug().Msgf("openai_send: %s", text)

	_ = historyMessageKeepNum

	messages := []openai.ChatCompletionMessageParamUnion{
		openai.SystemMessage(cc.SystemPrompt),
		openai.UserMessage(text),
	}

	response, err := cc.Client.Chat.Completions.New(ctx, openai.ChatCompletionNewParams{
		Model: cc.Model,
		// TODO: need count the number of token
		MaxTokens: openai.Int(4096),
		Messages:  messages,
	})

	if err != nil {
		log.Error().Err(err).Msg("audit: send message failed")
		return "", err
	}

	answer := response.Choices[0].Message.Content
	log.Debug().Msgf("openai_accept: %s", answer)

	return answer, nil
}
