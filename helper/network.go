package helper

import (
	"encoding/binary"
	"errors"
	"net"
	"strings"
)

func Int2ip(nn uint32) net.IP {
	ip := make(net.IP, 4)
	binary.BigEndian.PutUint32(ip, nn)
	return ip
}

// ParseDNSName "\u0005zhihu\u0003com" =>  "zhihu.com"
func ParseDNSName(buf []uint8) (string, error) {
	name := ""

	for i := 0; i < len(buf); i++ {
		subLen := int(buf[i])

		if subLen == 0 {
			break
		}

		if name == "" {
			if (i + subLen) > len(buf) {
				return "", errors.New("invalid DNS name")
			}
			name = string(buf[i+1 : i+subLen+1])
		} else {
			name = strings.Join([]string{name, string(buf[i+1 : i+1+subLen])}, ".")
		}
		i += subLen
	}

	return name, nil
}
