package audit

import (
	"fmt"
	"github.com/google/gopacket/layers"
	"github.com/muesli/cache2go"
	"github.com/rs/zerolog/log"
	"agent-sentinel/tracer"
	"net"
	"time"
)

const DNSTTL = 2 * time.Minute

type DNSCache struct {
	cache *cache2go.CacheTable
}

func NewDNSCache() *DNSCache {
	cache := cache2go.Cache("dns")
	return &DNSCache{cache}
}

//func (c *DNSCache) AddDNSRecord(event *tracer.DNSEvent) {
//	ipMap := make(map[string]net.IP)
//	cnameMap := make(map[string]string)
//	resolveOrder := make([]string, 0)
//
//	for _, answer := range event.Answers {
//		log.Debug().Msgf("DNS record %s", answer.String())
//		name := string(answer.Name)
//		if answer.Type == layers.DNSTypeA {
//			ipMap[name] = answer.IP
//		} else if answer.Type == layers.DNSTypeCNAME {
//			resolveOrder = append(resolveOrder, name)
//			cname := string(answer.CNAME)
//			cnameMap[cname] = name
//		}
//	}
//
//	// reverse order
//	for i := len(resolveOrder) - 1; i > 0; i-- {
//		if ip, ok := ipMap[resolveOrder[i]]; ok {
//			ipMap[cnameMap[resolveOrder[i]]] = ip
//		}
//	}
//
//	for name, ip := range ipMap {
//		log.Debug().Msgf("dns_cache: adding (%s,%s)", ip.String(), name)
//		c.cache.Add(ip.String(), DNSTTL, name)
//	}
//}

func (c *DNSCache) AddDNSRecord(event *tracer.DNSEvent) {
	if len(event.Questions) < 1 {
		return
	}

	targetAddr := string(event.Questions[0].Name)

	for _, answer := range event.Answers {
		// log.Debug().Msgf("DNS record %s", answer.String())
		if answer.Type == layers.DNSTypeA || answer.Type == layers.DNSTypeAAAA {
			log.Debug().Msgf("dns_cache: adding (%s,%s)", targetAddr, answer.IP.String())
			c.cache.Add(answer.IP.String(), DNSTTL, targetAddr)
		}
	}
}

func (c *DNSCache) IP2Domain(ip net.IP) (string, error) {
	item, err := c.cache.Value(ip.String())
	if err != nil {
		return "", err
	}

	name, ok := item.Data().(string)
	if !ok {
		return "", fmt.Errorf("invalid DNS record")
	}

	return name, nil
}
