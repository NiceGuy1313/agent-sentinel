package helper

import (
	"fmt"
	"golang.org/x/sys/unix"
	"path/filepath"
	"syscall"
)

const cgroupPath = "/sys/fs/cgroup/unified/docker"

func FindCgroupV2Path(conID string) (string, error) {
	var st syscall.Statfs_t
	path := filepath.Join(cgroupPath, conID)
	err := syscall.Statfs(path, &st)
	if err != nil {
		return "", err
	}
	isCgroupV2Enabled := st.Type == unix.CGROUP2_SUPER_MAGIC
	if !isCgroupV2Enabled {
		return "", fmt.Errorf("docker cgroup not enabled")
	}

	return path, nil
}
