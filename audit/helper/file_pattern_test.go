package helper

import "testing"

func TestFilePattern(t *testing.T) {
	_, err := compileFilePattern("/usr/lib/x86_64-linux-gnu/**")
	if err != nil {
		t.Error(err)
	}
}
