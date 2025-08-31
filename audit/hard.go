package audit

type Hard struct {
	rules []Rule
}

func NewHard() *Hard {
	h := &Hard{}
	return h
}

func (h *Hard) Query() {

}
