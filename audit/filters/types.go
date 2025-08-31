package filters

import (
	"net"
	"regexp"
)

// file filter

const (
	FILE_FILTER_RULE_EXCLUDE = 1
)

type FileRules struct {
	Type    int
	Path    string
	Op      uint32
	Pattern *regexp.Regexp
}

const (
	NET_FILTER_RULE_EXCLUDE_SINGLE_IP      = 1
	NET_FILTER_RULE_EXCLUDE_SINGLE_IP_PORT = 2
	NET_FILTER_RULE_EXCLUDE_CIDR           = 3
	NET_FILTER_RULE_EXCLUDE_Domain         = 4

	NET_FILTER_RULE_OP_ALL = 1 << 32
)

type NetRules struct {
	Type   int
	IPAddr string
	IP     net.IP
	Port   int
	Domain string
	CIDR   string
	IPNet  *net.IPNet
	Op     int
}
