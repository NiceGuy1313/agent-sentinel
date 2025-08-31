package helper

import (
	"bufio"
	"fmt"
	"os"
	"regexp"
	"strconv"
	"strings"
)

func GetMountNamespaceID(pid int) (int, error) {
	mnt, err := os.Readlink("/proc/" + strconv.Itoa(pid) + "/ns/mnt")
	if err != nil {
		return 0, err
	}

	re := regexp.MustCompile(`\[(\d+)\]`)
	match := re.FindStringSubmatch(mnt)

	if len(match) != 2 {
		return 0, fmt.Errorf("parse mount namespace ID failed")
	}

	mntID, err := strconv.Atoi(match[1])
	if err != nil {
		return 0, fmt.Errorf("parse mount namespace ID failed")
	}

	return mntID, nil
}

func GetPIDNamespaceID(pid int) (int, error) {
	pidns, err := os.Readlink("/proc/" + strconv.Itoa(pid) + "/ns/pid")
	if err != nil {
		return 0, err
	}

	re := regexp.MustCompile(`\[(\d+)\]`)
	match := re.FindStringSubmatch(pidns)

	if len(match) != 2 {
		return 0, fmt.Errorf("parse pid namespace ID failed")
	}

	nsID, err := strconv.Atoi(match[1])
	if err != nil {
		return 0, fmt.Errorf("parse pid namespace ID failed")
	}

	return nsID, nil
}

func GetHostPID(pid int, ns int) (int, error) {
	procFiles, err := os.ReadDir("/proc")
	if err != nil {
		return 0, err
	}

	pidStr := strconv.Itoa(pid)
	nsStr := strconv.Itoa(ns)
	foundPID := 0

	// for each /proc/pid
	for _, file := range procFiles {
		if file.Name()[0] >= '1' && file.Name()[0] <= '9' {
			link, err := os.Readlink("/proc/" + file.Name() + "/ns/pid")
			if err != nil {
				continue
			}

			if strings.Index(link, nsStr) != -1 {
				// read /proc/pid/status
				status, err := os.Open("/proc/" + file.Name() + "/status")
				if err != nil {
					continue
				}

				re := regexp.MustCompile(`\d+`)

				statusScanner := bufio.NewScanner(status)
				for statusScanner.Scan() {
					match, _ := regexp.MatchString("^NStgid:", statusScanner.Text())
					if match {
						pids := re.FindAllString(statusScanner.Text(), 2)
						if len(pids) == 2 && pids[1] == pidStr {
							foundPID, _ = strconv.Atoi(pids[0])
							break
						}
					}
				}
			}

			if foundPID > 0 {
				break
			}
		}
	}

	if foundPID == 0 {
		return 0, fmt.Errorf("no process found with PID %d in namespace %d", pid, ns)
	}

	return foundPID, nil
}
