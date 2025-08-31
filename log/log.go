package log

import (
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"os"
)

func InitMonitorLogger(logFile string) error {
	if logFile != "" {
		fd, err := os.OpenFile(logFile, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0666)
		if err != nil {
			log.Error().Err(err).Msg("Init global monitor logger failed")
			return err
		}
		log.Logger = zerolog.New(fd).With().Timestamp().Caller().Logger()
	} else {
		log.Logger = zerolog.New(os.Stderr).With().Timestamp().Caller().Logger()
	}

	zerolog.SetGlobalLevel(zerolog.InfoLevel)
	return nil
}

func WithDebugLevel() {
	zerolog.SetGlobalLevel(zerolog.DebugLevel)
}
