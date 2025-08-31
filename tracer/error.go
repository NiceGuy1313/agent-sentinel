package tracer

type ClosedError struct{}

func (e ClosedError) Error() string {
	return "tracer is closed"
}
