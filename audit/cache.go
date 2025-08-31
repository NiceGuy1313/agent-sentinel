package audit

import (
	"fmt"
	"github.com/rs/zerolog/log"
	"agent-sentinel/audit/cache"
	"agent-sentinel/audit/helper"
	"agent-sentinel/tracer"
	"net"
	"regexp"
	"strings"
)

func QueryFileOperationCache(event *tracer.FileEvent, cache *cache.ACache, onlyForCheck bool) int {
	key := event.Path

	// once -> task -> all

	var item interface{}
	var items []interface{}
	var err error

cacheSearch:
	for {
		item, err = cache.GetFileOpOnce(key, onlyForCheck)
		if err == nil {
			break
		}

		item, err = cache.GetFileOpTask(key)
		if err == nil {
			break
		}

		items, err = cache.GetFileOpPatternTask(key)
		if err == nil {
			for _, cand := range items {
				ans, _ := cand.(*CachedConfirmedFileOperation)
				if ans.Pattern.MatchString(key) {
					item = cand
					break cacheSearch
				}
			}
		}

		item, err = cache.GetFileOpAll(key)
		if err == nil {
			break
		}

		items, err = cache.GetFileOpPatternAll(key)
		if err == nil {
			for _, cand := range items {
				ans, _ := cand.(*CachedConfirmedFileOperation)
				if ans.Pattern.MatchString(key) {
					item = cand
					break cacheSearch
				}
			}
		}

		return AUDIT_OP_NOT_FOUND_IN_CACHE
	}

	ans, _ := item.(*CachedConfirmedFileOperation)
	// log.Debug().Msgf("anwser: %+v, event: %+v", ans, event)

	switch event.Type {
	case tracer.FileEventTypeFileOpen:
		if AccModeMeetSafeFileOp(event.AccMode, ans.SafeOp) {
			log.Debug().Msgf("audit_cache: file cache hit for (%s, %d)", key, event.AccMode)
			return AUDIT_OP_RESUME_PROCESS
		}
		// can not return `AUDIT_OP_TERMINATE_PROCESS` here
	case tracer.FileEventTypeInodeRename:
		if safeFileOpHasWritePermission(ans.SafeOp) {
			log.Debug().Msgf("audit_cache: file cache hit for (%s, %d)", key, event.AccMode)
			return AUDIT_OP_RESUME_PROCESS
		}
	case tracer.FileEventTypeInodeUnlink:
		// TODO: need access permission for its parent directory
		if safeFileOpHasWritePermission(ans.SafeOp) {
			log.Debug().Msgf("audit_cache: file cache hit for (%s, %d)", key, event.AccMode)
			return AUDIT_OP_RESUME_PROCESS
		}
	default:
		log.Error().Msgf("audit: invalid file event type %d", event.Type)
	}
	return AUDIT_OP_NOT_FOUND_IN_CACHE
}

func QueryNetOperationCache(event *tracer.SocketEvent, domain string, cache *cache.ACache, onlyForCheck bool) int {
	key := event.RemoteIP.String()

	// once -> task -> all
	item, err := cache.GetNetOpOnce(key, onlyForCheck)
	if err != nil {
		item, err = cache.GetNetOpTask(key)
		if err != nil {
			item, err = cache.GetNetOpAll(key)
			if err != nil {
				// query domain
				if domain != "" {
					item, err = cache.GetNetOpOnce(domain, onlyForCheck)
					if err != nil {
						item, err = cache.GetNetOpTask(domain)
						if err != nil {
							item, err = cache.GetNetOpAll(domain)
						}
					}
					if err != nil {
						return AUDIT_OP_NOT_FOUND_IN_CACHE
					}
				} else {
					return AUDIT_OP_NOT_FOUND_IN_CACHE
				}
			}
		}
	} else {
		// delete related item at once
		if domain != "" && !onlyForCheck {
			cache.DelNetOpOnce(domain)
		}
	}

	ans, _ := item.(*CachedConfirmedNetworkOperation)
	safeOP := ans.SafeOp

	switch event.Type {
	case tracer.SocketEventTypeConnect:
		if safeNetOpHasSendPermission(safeOP) {
			log.Debug().Msgf("audit_cache: net cache hit for (%s, %s)", event.RemoteIP.String(), domain)
			return AUDIT_OP_RESUME_PROCESS
		}
		// can not return `AUDIT_OP_TERMINATE_PROCESS` here
	case tracer.SocketEventTypeListen:
		fallthrough
	case tracer.SocketEventTypeAccept:
		if safeNetOpHasListenPermission(safeOP) {
			log.Debug().Msgf("audit_cache: net cache hit for (%s, %s)", event.RemoteIP.String(), domain)
			return AUDIT_OP_RESUME_PROCESS
		}
	case tracer.SocketEventTypeAcceptExit:
		if safeNetOpHasRecvPermission(safeOP) {
			log.Debug().Msgf("audit_cache: net cache hit for (%s, %s)", event.RemoteIP.String(), domain)
			return AUDIT_OP_RESUME_PROCESS
		}
	default:
		log.Error().Msgf("audit: invalid file event type %d", event.Type)
	}

	return AUDIT_OP_NOT_FOUND_IN_CACHE
}

func addAuditorAnswerToCache(ans *AuditorAnswer, cache *cache.ACache, safeBinary bool) {
	cachedAns := transformAuditorAnswerToCache(ans)

	for _, fop := range cachedAns.ConfirmedFileOperations {
		addSafeFileOpToCache(fop, cache, safeBinary)
	}

	for _, nop := range cachedAns.ConfirmedNetworkOperation {
		addSafeNetOpToCache(nop, cache)
	}
}

func addSafeFileOpToCache(ans *CachedConfirmedFileOperation, cache *cache.ACache, safeBinary bool) {
	key := ans.FilePath

	if ans.TTL == AUDIT_SAFE_OP_TTL_ALL {
		// TODO: may merge with the old one ? also consider net op
		log.Debug().Msgf("audit_cache: cached all-level file op %+v", ans)
		if ans.Pattern == nil {
			cache.AddFileOpAll(key, ans)

			if safeBinary && ans.SafeOp&AUDIT_SAFE_FILE_OP_EXEC == AUDIT_SAFE_FILE_OP_EXEC {
				log.Debug().Msgf("audit_cache: cached all-level binary %s", ans.FilePath)
				cache.AddSafeBinaryAll(key, ans)
			}
		} else {
			cache.AddFileOpPatternAll(key, ans)
		}
	} else if ans.TTL == AUDIT_SAFE_OP_TTL_TASK {
		log.Debug().Msgf("audit_cache: cached task-level file op %+v", ans)
		if ans.Pattern == nil {
			cache.AddFileOpTask(key, ans)

			if safeBinary && ans.SafeOp&AUDIT_SAFE_FILE_OP_EXEC == AUDIT_SAFE_FILE_OP_EXEC {
				log.Debug().Msgf("audit_cache: cached task-level binary %s", ans.FilePath)
				cache.AddSafeBinaryTask(key, ans)
			}
		} else {
			cache.AddFileOpPatternTask(key, ans)
		}
	} else {
		log.Debug().Msgf("audit_cache: cached once-level file op %+v", ans)

		// only allow valid path
		if ans.Pattern == nil {
			cache.AddFileOpOnce(key, ans)
			if safeBinary && ans.SafeOp&AUDIT_SAFE_FILE_OP_EXEC == AUDIT_SAFE_FILE_OP_EXEC {
				log.Debug().Msgf("audit_cache: cached once-level binary %s", ans.FilePath)
				cache.AddSafeBinaryOnce(key, ans)
			}
		}
	}
}

func addSafeNetOpToCache(ans *CachedConfirmedNetworkOperation, cache *cache.ACache) {
	key1 := ans.Domain
	key2 := ans.IP

	// add both keys into the cache
	if ans.TTL == AUDIT_SAFE_OP_TTL_ALL {
		log.Debug().Msgf("audit_cache: cached all-level net op %+v", ans)

		if key1 != "" {
			cache.AddNetOpAll(key1, ans)
		}

		if key2 != nil {
			cache.AddNetOpAll(string(key2), ans)
		}
	} else if ans.TTL == AUDIT_SAFE_OP_TTL_TASK {
		log.Debug().Msgf("audit_cache: cached task-level net op %+v", ans)
		if key1 != "" {
			cache.AddNetOpTask(key1, ans)
		}

		if key2 != nil {
			cache.AddNetOpTask(string(key2), ans)
		}
	} else {
		log.Debug().Msgf("audit_cache: cached once-level net op %+v", ans)
		if key1 != "" {
			cache.AddNetOpOnce(key1, ans)
		}

		if key2 != nil {
			cache.AddNetOpOnce(string(key2), ans)
		}
	}
}

func transformAuditorAnswerToCache(ans *AuditorAnswer) *CachedAuditorAnswer {
	cachedAns := &CachedAuditorAnswer{}
	cachedAns.ActionIsSafe = ans.ActionIsSafe
	cachedAns.Result = ans.Result
	cachedAns.ConfirmedFileOperations = make([]*CachedConfirmedFileOperation, 0)
	cachedAns.ConfirmedNetworkOperation = make([]*CachedConfirmedNetworkOperation, 0)

	for _, fop := range ans.ConfirmedFileOperations {
		ttl, err := TTLStrToInt(fop.TTL)
		if err != nil {
			log.Error().Msgf("audit_cache: invalid TTL %s", fop.TTL)
			continue
		}

		safeOp, err := safeFileOpStrToInt(fop.SafeOp)
		if err != nil {
			log.Error().Msgf("audit_cache: invalid file safe op %s", fop.SafeOp)
			continue
		}

		filePath := fop.FilePath
		var pattern *regexp.Regexp
		if strings.Contains(fop.FilePath, "/*") {
			pattern, err = helper.CompileFilePattern(fop.FilePath)
			if err != nil {
				log.Error().Msgf("audit_cache: invalid path pattern %s", fop.FilePath)
				continue
			}

			// filePath: the prefix path before the first `*` or `**`. e.g. `/tmp/*` -> `/tmp/`
			// For a path pattern query Q(target_path, cache):
			// 1. We collect a set of path patterns from cache. These path patterns have same prefix with the target_path.
			// 2. Iterate the set to execute a pattern match for each path pattern and the target_path.
			end := strings.Index(filePath, "*")
			filePath = filePath[:end]
		}

		cachedOp := &CachedConfirmedFileOperation{
			FilePath: filePath,
			SafeOp:   safeOp,
			TTL:      ttl,
			Pattern:  pattern,
		}

		cachedAns.ConfirmedFileOperations = append(cachedAns.ConfirmedFileOperations, cachedOp)
	}

	for _, nop := range ans.ConfirmedNetworkOperation {
		ttl, err := TTLStrToInt(nop.TTL)
		if err != nil {
			log.Error().Msgf("audit_cache: invalid TTL %s", nop.TTL)
			continue
		}

		safeOp, err := safeNetOpStrToInt(nop.SafeOp)
		if err != nil {
			log.Error().Msgf("audit_cache: invalid net safe op %s", nop.SafeOp)
			continue
		}

		var ip net.IP
		if nop.IP != "" {
			ip = net.ParseIP(nop.IP)
			if ip == nil {
				log.Error().Msgf("audit_cache: invalid ip %s", nop.IP)
				// sometime LLM may output domain as IP. e.g., `{ip: "example.com", domain: "example.com"}`
				if nop.Domain == "" {
					continue
				}
			}
		}

		cachedOp := &CachedConfirmedNetworkOperation{
			IP:     ip,
			Domain: nop.Domain,
			SafeOp: safeOp,
			TTL:    ttl,
		}

		cachedAns.ConfirmedNetworkOperation = append(cachedAns.ConfirmedNetworkOperation, cachedOp)
	}

	return cachedAns
}

func querySafeBinaryCache(path string, cache *cache.ACache) int {
	_, err := cache.GetSafeBinaryOnce(path)
	if err != nil {
		_, err = cache.GetSafeBinaryTask(path)
		if err != nil {
			_, err = cache.GetSafeBinaryAll(path)
			if err != nil {
				return AUDIT_OP_NOT_FOUND_IN_CACHE
			}
		}
	}

	log.Debug().Msgf("audit_cache: safe binary cache hit for %s", path)

	return AUDIT_OP_RESUME_PROCESS
}

func safeFileOpStrToInt(op string) (int, error) {
	// verify the LLM output and transfer it to better format for storage
	i := 0
	strlen := len(op)

	if strlen > 3 || strlen == 0 {
		return -1, fmt.Errorf("audit: bad safe file operation")
	}

	if strings.Index(op, SafeFileRead) != -1 {
		i |= AUDIT_SAFE_FILE_OP_READ
		strlen--
	}

	if strings.Index(op, SafeFileWrite) != -1 {
		i |= AUDIT_SAFE_FILE_OP_WRITE
		strlen--
	}

	if strings.Index(op, SafeFileExec) != -1 {
		i |= AUDIT_SAFE_FILE_OP_EXEC
		strlen--
	}

	if strlen > 0 {
		return -1, fmt.Errorf("audit: safe file operation contains unknown operation descriptor")
	}

	return i, nil
}

func safeNetOpStrToInt(op string) (int, error) {
	ops := strings.Split(op, ",")

	if len(ops) == 0 || len(ops) > 3 {
		return -1, fmt.Errorf("audit: bad safe net operation")
	}

	i := 0
	for _, op := range ops {
		switch op {
		case SafeNetworkSend:
			i |= AUDIT_SAFE_NET_OP_SEND
		case SafeNetworkRecv:
			i |= AUDIT_SAFE_NET_OP_RECV
		case SafeNetworkListen:
			i |= AUDIT_SAFE_NET_OP_LISTEN
		default:
			return -1, fmt.Errorf("audit: safe net operation contains unknown operation descriptor")
		}
	}

	return i, nil
}

func TTLStrToInt(ttl string) (int, error) {
	switch ttl {
	case CONFIRMED_OP_TTL_ALL:
		return AUDIT_SAFE_OP_TTL_ALL, nil
	case CONFIRMED_OP_TTL_TASK:
		return AUDIT_SAFE_OP_TTL_TASK, nil
	case CONFIRMED_OP_TTL_ONCE:
		return AUDIT_SAFE_OP_TTL_ONCE, nil
	default:
		return -1, fmt.Errorf("audit: safe net operation contains unknown operation descriptor")
	}
}

func AccModeMeetSafeFileOp(accMode uint32, safeFileOp int) bool {
	if isWrite(accMode) && (safeFileOp&AUDIT_SAFE_FILE_OP_WRITE != AUDIT_SAFE_FILE_OP_WRITE) {
		return false
	}

	if isRead(accMode) && (safeFileOp&AUDIT_SAFE_FILE_OP_READ != AUDIT_SAFE_FILE_OP_READ) {
		return false
	}

	return true
}

func safeFileOpHasWritePermission(safeFileOp int) bool {
	if safeFileOp&AUDIT_SAFE_FILE_OP_WRITE == AUDIT_SAFE_FILE_OP_WRITE {

		return true
	}
	return false
}

func safeNetOpHasSendPermission(safeNetOp int) bool {
	if safeNetOp&AUDIT_SAFE_NET_OP_SEND == AUDIT_SAFE_NET_OP_SEND {
		return true
	}
	return false
}

func safeNetOpHasRecvPermission(safeNetOp int) bool {
	if safeNetOp&AUDIT_SAFE_NET_OP_RECV == AUDIT_SAFE_NET_OP_RECV {
		return true
	}
	return false
}

func safeNetOpHasListenPermission(safeNetOp int) bool {
	if safeNetOp&AUDIT_SAFE_NET_OP_LISTEN == AUDIT_SAFE_NET_OP_LISTEN {
		return true
	}
	return false
}
