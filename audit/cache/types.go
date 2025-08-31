package cache

import (
	"errors"
)

type cacheItem struct {
	TTL   int
	value interface{}
}

const (
	// use negative value to leave a place for time duration use in the future
	TTL_ALL  = -1
	TTL_TASK = -2
	TTL_ONCE = -3
)

var ErrKeyNotFound = errors.New("key not found")
