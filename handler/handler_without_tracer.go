package handler

import (
	"bytes"
	"context"
	"encoding/json"
	"github.com/rs/zerolog/log"
	"io"
	"agent-sentinel/api"
	"agent-sentinel/audit"
)

type HandlerWithoutTracer struct {
	audit       *audit.AuditWithoutTrace
	ctx         context.Context
	passiveMode bool
}

func NewHandlerWithoutTracer(audit *audit.AuditWithoutTrace) (*HandlerWithoutTracer, error) {
	return &HandlerWithoutTracer{
		audit: audit,
	}, nil
}

func (h *HandlerWithoutTracer) Start(ctx context.Context) error {
	h.ctx = ctx
	return nil
}

func (h *HandlerWithoutTracer) Close() error {
	return nil
}

func (h *HandlerWithoutTracer) NewConnectHandler() api.ComputerMonitorMessageCallback {
	return func(op int16, msg *api.ComputerMonitorMessage) *api.ComputerMonitorCallbackResponse {
		return api.CreateEmptyComputerMonitorMessageResponse()
	}
}

func (h *HandlerWithoutTracer) NewStartPassiveTracingHandler() api.ComputerMonitorMessageCallback {
	return func(op int16, msg *api.ComputerMonitorMessage) *api.ComputerMonitorCallbackResponse {
		if !h.passiveMode {
			h.passiveMode = true
		}
		return api.CreateEmptyComputerMonitorMessageResponse()
	}
}

func (h *HandlerWithoutTracer) NewSendToolUseHandler() api.ComputerMonitorMessageCallback {
	return func(op int16, msg *api.ComputerMonitorMessage) *api.ComputerMonitorCallbackResponse {
		if !h.passiveMode {
			return api.CreateEmptyComputerMonitorMessageResponse()
		}

		reader := bytes.NewReader(msg.Data)
		decoder := json.NewDecoder(reader)

		toolUseMsg := make([]*audit.ToolUseMessage, 0)

		for {
			err := decoder.Decode(&toolUseMsg)
			if err == io.EOF {
				break
			} else if err != nil {
				log.Error().Err(err).Msgf("handler: unmarshal tool use failed, data: %s", string(msg.Data))
				return api.CreateEmptyComputerMonitorMessageResponse()
			}
		}

		log.Debug().Msgf("handler: accept tool use message: %+q", toolUseMsg)

		_, _ = h.audit.Query(toolUseMsg)

		return api.CreateEmptyComputerMonitorMessageResponse()
	}
}

func (h *HandlerWithoutTracer) NewGetLastEnforcementResult() api.ComputerMonitorMessageCallback {
	return func(op int16, msg *api.ComputerMonitorMessage) *api.ComputerMonitorCallbackResponse {
		isSafe, result, err := h.audit.GetLastSafetyCheckResult()
		if err != nil {
			return api.CreateEmptyComputerMonitorMessageResponse()
		}

		alert := &SecurityAlert{IsSafe: isSafe, Message: result}
		jsonData, err := json.Marshal(alert)
		if err != nil {
			log.Error().Err(err).Msg("handler: marshal alert failed")
			return api.CreateEmptyComputerMonitorMessageResponse()
		}

		log.Debug().Msgf("handler: send last_enforement_result %+v", alert)

		return &api.ComputerMonitorCallbackResponse{
			Close: false,
			Data:  jsonData,
		}
	}
}
