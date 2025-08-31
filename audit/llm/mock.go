package llm

import (
	"context"
	"fmt"
	"time"
)

// mocking llm for testing

type MockResponse struct {
	Text  string
	Delay time.Duration
}

type MockClient struct {
	defaultResp  *MockResponse
	respSeq      []*MockResponse
	currentIndex int
}

func NewMockClient(defaultResp *MockResponse, respSeq []*MockResponse) *MockClient {
	mc := &MockClient{
		defaultResp: defaultResp,
		respSeq:     respSeq,
	}

	return mc
}

func (m *MockClient) SendTextMessage(ctx context.Context, text string, historyMessageKeepNum int) (string, error) {
	if m.currentIndex < len(m.respSeq) {
		resp := m.respSeq[m.currentIndex]
		m.currentIndex++

		// mock the query time
		if resp.Delay > 0 {
			select {
			case <-time.After(resp.Delay):
			case <-ctx.Done():
				return "", fmt.Errorf("mock_client: context cannelled")
			}
		}

		return resp.Text, nil
	} else {
		if m.defaultResp.Delay > 0 {
			select {
			case <-time.After(m.defaultResp.Delay):
			case <-ctx.Done():
				return "", fmt.Errorf("mock_client: context cannelled")
			}
		}

		return m.defaultResp.Text, nil
	}
}
