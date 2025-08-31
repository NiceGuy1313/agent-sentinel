package api

import (
	"context"
	"fmt"
	"github.com/rs/zerolog/log"
	"net"
	"os"
	"path"
)

const sockFile = "computer-monitor.sock"

type ComputerMonitorServer struct {
	listener net.Listener
	conn     *computerMonitorConnection
	// TODO multiple callbacks for a single op
	mCallbacks map[int]ComputerMonitorMessageCallback
	reqCh      chan *ComputerMonitorMessage
	repCh      chan *ComputerMonitorCallbackResponse
	sockFile   string
}

func NewComputerMonitorServer(dir string) (*ComputerMonitorServer, error) {
	server := &ComputerMonitorServer{
		mCallbacks: make(map[int]ComputerMonitorMessageCallback),
		reqCh:      make(chan *ComputerMonitorMessage),
		repCh:      make(chan *ComputerMonitorCallbackResponse),
	}

	server.sockFile = path.Join(dir, sockFile)
	if _, err := os.Stat(server.sockFile); err == nil {
		err = os.Remove(server.sockFile)
		if err != nil {
			log.Error().Err(err).Msg("computer_monitor_server: remove old unix socket failed")
			return nil, err
		}
	}

	l, err := net.Listen("unix", server.sockFile)
	if err != nil {
		log.Error().Err(err).Msg("computer_monitor_server: create unix socket failed")
		return nil, err
	}

	// allow anyone can connect it, immediately delete it when an agent connected
	if err = os.Chmod(server.sockFile, 0777); err != nil {
		log.Error().Err(err).Msg("computer_monitor_server: chmod unix socket failed")
		return nil, err
	}

	log.Debug().Msgf("Created computer monitor server socket %s", server.sockFile)

	server.listener = l
	return server, nil
}

func (cms *ComputerMonitorServer) Start(ctx context.Context) error {
	err := cms.waitConnection(ctx)
	return err
}

func (cms *ComputerMonitorServer) RegisterComputerMonitorMessageHandler(op int, f ComputerMonitorMessageCallback) {
	cms.mCallbacks[op] = f
}

func (cms *ComputerMonitorServer) DeleteComputerMonitorMessageHandler(op int) {
	delete(cms.mCallbacks, op)
}

func (cms *ComputerMonitorServer) waitConnection(ctx context.Context) error {
	log.Info().Msg("computer_monitor_server: server started, waiting incoming connection")

	conn, err := cms.listener.Accept()

	if err != nil {
		select {
		case <-ctx.Done():
			return fmt.Errorf("computer_monitor_server: context cannelled")
		default:
			log.Error().Err(err).Msg("computer_monitor_server: accept failed")
			return err
		}
	}

	// free it when consumed, so only accept once
	if err = os.Remove(cms.sockFile); err != nil {
		log.Error().Err(err).Msg("computer_monitor_server: remove sock file failed")
	}

	cms.conn = newComputerMonitorConnection(conn, cms.repCh, cms.reqCh)
	go cms.conn.handleConn()
	// FIXME: parallel or sequential ?
	go cms.handleComputerMonitorMessage()

	select {
	case <-ctx.Done():
		return fmt.Errorf("computer_monitor_server: context cannelled")
	}
}

func (cms *ComputerMonitorServer) handleComputerMonitorMessage() {
	for {
		select {
		// FIXME: exit code
		case req := <-cms.reqCh:
			f, ok := cms.mCallbacks[int(req.Op)]

			// default return empty response
			if ok != true {
				cms.repCh <- CreateEmptyComputerMonitorMessageResponse()
			} else {
				cms.repCh <- f(req.Op, req)
			}
		}
	}
}

func (cms *ComputerMonitorServer) Close() {
	if cms.conn != nil {
		_ = cms.conn.close()
	}
	_ = cms.listener.Close()
}

func CreateEmptyComputerMonitorMessageResponse() *ComputerMonitorCallbackResponse {
	return &ComputerMonitorCallbackResponse{
		Close: false,
		Data:  make([]byte, 0),
	}
}
