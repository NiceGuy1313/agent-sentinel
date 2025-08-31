package handler

import (
	"github.com/rs/zerolog/log"
	"syscall"
)

func resumeProcess(pid int) error {
	err := syscall.Kill(pid, syscall.SIGCONT)

	if err != nil {
		return err
	}

	log.Debug().Msgf("handler_process_control: resume process %d", pid)
	return nil
}

func terminateProcess(pid int) error {
	err := syscall.Kill(pid, syscall.SIGKILL)
	if err != nil {
		return err
	}

	log.Debug().Msgf("handler_process_control: terminate process %d", pid)
	return nil
}
