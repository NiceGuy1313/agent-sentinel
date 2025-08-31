package filters

import (
	"fmt"
	"agent-sentinel/tracer"
	"net"
)

type NetEventFilter struct {
	rules []*NetRules
}

func NewNetEventFilter() (*NetEventFilter, error) {
	filter := &NetEventFilter{}
	err := filter.initDefaultRules()
	if err != nil {
		return nil, err
	}

	return filter, nil
}

func (f *NetEventFilter) initDefaultRules() error {
	// TODO: external
	f.rules = []*NetRules{
		{
			Type:   NET_FILTER_RULE_EXCLUDE_SINGLE_IP,
			IPAddr: "172.17.0.1",
			Op:     NET_FILTER_RULE_OP_ALL,
		},
		// agent spec
		{
			Type:   NET_FILTER_RULE_EXCLUDE_SINGLE_IP_PORT,
			IPAddr: "0.0.0.0",
			Port:   8501,
			Op:     NET_FILTER_RULE_OP_ALL,
		},
		// DNS query
		{
			Type:   NET_FILTER_RULE_EXCLUDE_SINGLE_IP_PORT,
			IPAddr: "192.168.31.1",
			Port:   53,
			Op:     NET_FILTER_RULE_OP_ALL,
		},
	}

	for _, rule := range f.rules {
		switch rule.Type {
		case NET_FILTER_RULE_EXCLUDE_SINGLE_IP:
			fallthrough
		case NET_FILTER_RULE_EXCLUDE_SINGLE_IP_PORT:
			rule.IP = net.ParseIP(rule.IPAddr)
			if rule.IP == nil {
				return fmt.Errorf("net_filter: invalid ip address %s", rule.IPAddr)
			}
			// TODO: more cases
		}
	}

	return nil
}

func (f *NetEventFilter) Filter(e *tracer.SocketEvent) bool {
	// log.Debug().Msg("net_filter: filter called")

	for _, rule := range f.rules {
		switch rule.Type {
		case NET_FILTER_RULE_EXCLUDE_SINGLE_IP:
			if e.RemoteIP.Equal(rule.IP) {
				if rule.Op == NET_FILTER_RULE_OP_ALL {
					return true
				}
			}
		case NET_FILTER_RULE_EXCLUDE_SINGLE_IP_PORT:
			if e.RemoteIP.Equal(rule.IP) && int(e.RemotePort) == rule.Port {
				if rule.Op == NET_FILTER_RULE_OP_ALL {
					return true
				}
			}
			// TODO: more cases
		}
	}

	return false
}
