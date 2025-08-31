package api

import (
	"bufio"
	"encoding/binary"
	"fmt"
	"github.com/rs/zerolog/log"
	"io"
	"net"
)

type computerMonitorConnection struct {
	conn   net.Conn
	reader *bufio.Reader
	writer *bufio.Writer
	repCh  chan *ComputerMonitorCallbackResponse
	reqCh  chan *ComputerMonitorMessage
}

func newComputerMonitorConnection(c net.Conn, repCh chan *ComputerMonitorCallbackResponse, reqCh chan *ComputerMonitorMessage) *computerMonitorConnection {
	conn := &computerMonitorConnection{
		conn:  c,
		repCh: repCh,
		reqCh: reqCh,
	}
	return conn
}

func (conn *computerMonitorConnection) sayHello() error {
	_, err := conn.reader.Peek(4)

	if err != nil {
		log.Error().Err(err).Msg("computer_monitor_server: say hello failed")
		return err
	}
	_, _ = conn.reader.Discard(4)

	n, err := conn.writer.Write([]byte(HELLO_REPLY))

	if err != nil {
		log.Error().Err(err).Msg("computer_monitor_server: say hello failed")
		return err
	}

	if len(HELLO_REPLY) != n {
		log.Error().Msg("computer_monitor_server: say hello failed")
		return fmt.Errorf("computer_monitor_server: say hello failed")
	}

	err = conn.writer.Flush()
	if err != nil {
		log.Error().Err(err).Msg("computer_monitor_server: say hello failed")
		return err
	}

	return nil
}

func (conn *computerMonitorConnection) handleConn() {
	conn.reader = bufio.NewReader(conn.conn)
	conn.writer = bufio.NewWriter(conn.conn)
	defer conn.close()

	if conn.sayHello() != nil {
		return
	}

	// FIXME: read connect request

	msg, err := conn.readComputerMonitorRequest()
	if err != nil {
		return
	}

	// The first request should be CM_OP_CONNECT
	if msg.Op != CM_OP_CONNECT {
		return
	}

	conn.reqCh <- msg
	rep := <-conn.repCh

	if rep.Close {
		return
	}

	err = conn.writeComputerMonitorResponse(msg.Op, rep)
	if err != nil {
		return
	}

	log.Info().Msg("computer_monitor_server: agent connected")

	for {
		if err = conn.handleComputerMonitorRequest(); err != nil {
			return
		}
	}
}

func (conn *computerMonitorConnection) handleComputerMonitorRequest() error {
	msg, err := conn.readComputerMonitorRequest()
	if err != nil {
		return err
	}

	// Forbidden further connect requests
	if msg.Op == CM_OP_CONNECT {
		log.Error().Msg("computer_monitor_server: agent sends connect request again")
		return fmt.Errorf("computer_monitor_server: agent sends connect request again")
	}

	conn.reqCh <- msg

	rep := <-conn.repCh
	if rep.Close {
		return fmt.Errorf("computer_monitor_server: connection closed")
	}

	err = conn.writeComputerMonitorResponse(msg.Op, rep)
	if err != nil {
		return err
	}

	return nil
}

func (conn *computerMonitorConnection) readComputerMonitorRequest() (*ComputerMonitorMessage, error) {
	var header computerMonitorMessageRequestHeader

	if err := binary.Read(conn.reader, binary.LittleEndian, &header); err != nil {
		log.Error().Err(err).Msg("computer_monitor_server: read computer_monitor request failed")
		return nil, err
	}

	msg := &ComputerMonitorMessage{
		Op:      header.Op,
		DateLen: header.DateLen,
	}

	if header.DateLen > 0 {
		msg.Data = make([]byte, header.DateLen)
		n, err := io.ReadFull(conn.reader, msg.Data)

		if err != nil {
			log.Error().Err(err).Msg("computer_monitor_server: read computer_monitor request failed")
			return nil, err
		}

		if n != int(header.DateLen) {
			log.Debug().Msgf("computer_monitor_server: n = %d, header_data_len: %d", n, header.DateLen)
			log.Error().Msg("computer_monitor_server: read computer_monitor request failed")
			return nil, fmt.Errorf("computer_monitor_server: read computer_monitor request failed")
		}
	}

	// log.Debug().Msgf("computer_monitor_server: read computer monitor request %+v", msg)

	return msg, nil
}

func (conn *computerMonitorConnection) writeComputerMonitorResponse(op int16, rep *ComputerMonitorCallbackResponse) error {
	var header computerMonitorMessageResponseHeader

	header.Op = op
	header.DateLen = int32(len(rep.Data))

	if err := binary.Write(conn.writer, binary.LittleEndian, header); err != nil {
		log.Error().Err(err).Msg("computer_monitor_server: write computer_monitor response failed")
		return err
	}

	if header.DateLen > 0 {
		_, err := conn.writer.Write(rep.Data)
		if err != nil {
			log.Error().Err(err).Msg("computer_monitor_server: write computer_monitor response failed")
			return err
		}
	}

	err := conn.writer.Flush()
	if err != nil {
		log.Error().Err(err).Msg("computer_monitor_server: write computer_monitor response failed")
		return err
	}

	// log.Debug().Msgf("computer_monitor_server: write computer monitor response, %d bytes data: %s", header.DateLen, string(rep.Data))

	return nil
}

func (conn *computerMonitorConnection) close() error {
	log.Info().Msg("computer_monitor_server: connection closed")
	return conn.conn.Close()
}

func getInt(buf []byte) int32 {
	n := uint32(buf[0])
	n |= uint32(buf[1]) << 8
	n |= uint32(buf[2]) << 16
	n |= uint32(buf[3]) << 24
	return int32(n)
}
