package cache

import (
	"strings"
	"sync"
)

type ACache struct {
	fileOpOnce        map[string]*cacheItem
	fileOpTask        map[string]*cacheItem
	fileOpPatternTask map[string]*cacheItem
	fileOpAll         map[string]*cacheItem
	fileOpPatternAll  map[string]*cacheItem
	netOpOnce         map[string]*cacheItem
	netOpTask         map[string]*cacheItem
	netOpAll          map[string]*cacheItem
	binaryOnce        map[string]*cacheItem
	binaryTask        map[string]*cacheItem
	binaryAll         map[string]*cacheItem

	lock sync.RWMutex
}

func NewACache() *ACache {
	aCache := &ACache{
		fileOpOnce:        make(map[string]*cacheItem),
		fileOpAll:         make(map[string]*cacheItem),
		fileOpPatternAll:  make(map[string]*cacheItem),
		fileOpTask:        make(map[string]*cacheItem),
		fileOpPatternTask: make(map[string]*cacheItem),
		netOpOnce:         make(map[string]*cacheItem),
		netOpAll:          make(map[string]*cacheItem),
		netOpTask:         make(map[string]*cacheItem),
		binaryOnce:        make(map[string]*cacheItem),
		binaryTask:        make(map[string]*cacheItem),
		binaryAll:         make(map[string]*cacheItem),
	}

	return aCache
}

func (A *ACache) AddFileOpOnce(key string, value interface{}) {
	A.lock.Lock()
	defer A.lock.Unlock()
	A.fileOpOnce[key] = &cacheItem{
		TTL:   TTL_ONCE,
		value: value,
	}
}

func (A *ACache) GetFileOpOnce(key string, onlyForCheck bool) (interface{}, error) {
	A.lock.RLock()
	defer A.lock.RUnlock()
	value, ok := A.fileOpOnce[key]
	if ok {
		if !onlyForCheck {
			delete(A.fileOpOnce, key)
		}
		return value.value, nil
	}

	return nil, ErrKeyNotFound
}

func (A *ACache) DelFileOpOnce(key string) {
	A.lock.Lock()
	delete(A.fileOpOnce, key)
	A.lock.Unlock()
}

func (A *ACache) ClearFileOpOnce() {
	A.lock.Lock()
	A.fileOpOnce = make(map[string]*cacheItem)
	A.lock.Unlock()
}

func (A *ACache) AddFileOpTask(key string, value interface{}) {
	A.lock.Lock()
	A.fileOpTask[key] = &cacheItem{
		TTL:   TTL_TASK,
		value: value,
	}
	A.lock.Unlock()
}

func (A *ACache) AddFileOpPatternTask(key string, value interface{}) {
	A.lock.Lock()
	A.fileOpPatternTask[key] = &cacheItem{
		TTL:   TTL_TASK,
		value: value,
	}
	A.lock.Unlock()
}

func (A *ACache) GetFileOpTask(key string) (interface{}, error) {
	A.lock.RLock()
	value, ok := A.fileOpTask[key]
	A.lock.RUnlock()

	if ok {
		return value.value, nil
	}

	return nil, ErrKeyNotFound
}

func (A *ACache) GetFileOpPatternTask(key string) ([]interface{}, error) {
	A.lock.RLock()
	items := make([]interface{}, 0)
	for key2, value := range A.fileOpPatternTask {
		if strings.Contains(key, key2) {
			items = append(items, value.value)
		}
	}
	A.lock.RUnlock()

	if len(items) != 0 {
		return items, nil
	}

	return nil, ErrKeyNotFound
}

func (A *ACache) ClearFileOpTask() {
	A.lock.Lock()
	A.fileOpTask = make(map[string]*cacheItem)
	A.lock.Unlock()
}

func (A *ACache) ClearFileOpPatternTask() {
	A.lock.Lock()
	A.fileOpPatternTask = make(map[string]*cacheItem)
	A.lock.Unlock()
}

func (A *ACache) AddFileOpAll(key string, value interface{}) {
	A.lock.Lock()
	A.fileOpAll[key] = &cacheItem{
		TTL:   TTL_ALL,
		value: value,
	}
	A.lock.Unlock()
}

func (A *ACache) AddFileOpPatternAll(key string, value interface{}) {
	A.lock.Lock()
	A.fileOpPatternAll[key] = &cacheItem{
		TTL:   TTL_ALL,
		value: value,
	}
	A.lock.Unlock()
}

func (A *ACache) GetFileOpAll(key string) (interface{}, error) {
	A.lock.RLock()
	value, ok := A.fileOpAll[key]
	A.lock.RUnlock()

	if ok {
		return value.value, nil
	}

	return nil, ErrKeyNotFound
}

func (A *ACache) GetFileOpPatternAll(key string) ([]interface{}, error) {
	A.lock.RLock()
	items := make([]interface{}, 0)
	for key2, value := range A.fileOpPatternAll {
		if strings.Contains(key, key2) {
			items = append(items, value.value)
		}
	}
	A.lock.RUnlock()

	if len(items) != 0 {
		return items, nil
	}

	return nil, ErrKeyNotFound
}

func (A *ACache) AddNetOpOnce(key string, value interface{}) {
	A.lock.Lock()
	A.netOpOnce[key] = &cacheItem{
		TTL:   TTL_ONCE,
		value: value,
	}
	A.lock.Unlock()
}

func (A *ACache) GetNetOpOnce(key string, onlyForCheck bool) (interface{}, error) {
	A.lock.Lock()
	defer A.lock.Unlock()
	value, ok := A.netOpOnce[key]

	if ok {
		if !onlyForCheck {
			delete(A.netOpOnce, key)
		}
		return value.value, nil
	}

	return nil, ErrKeyNotFound
}

func (A *ACache) DelNetOpOnce(key string) {
	A.lock.Lock()
	delete(A.netOpOnce, key)
	A.lock.Unlock()
}

func (A *ACache) ClearNetOpOnce() {
	A.lock.Lock()
	A.netOpOnce = make(map[string]*cacheItem)
	A.lock.Unlock()
}

func (A *ACache) AddNetOpTask(key string, value interface{}) {
	A.lock.Lock()
	A.netOpTask[key] = &cacheItem{
		TTL:   TTL_TASK,
		value: value,
	}
	A.lock.Unlock()
}

func (A *ACache) GetNetOpTask(key string) (interface{}, error) {
	A.lock.RLock()
	value, ok := A.netOpTask[key]
	A.lock.RUnlock()

	if ok {
		return value.value, nil
	}

	return nil, ErrKeyNotFound
}

func (A *ACache) ClearNetOpTask() {
	A.lock.Lock()
	A.netOpTask = make(map[string]*cacheItem)
	A.lock.Unlock()
}

func (A *ACache) AddNetOpAll(key string, value interface{}) {
	A.lock.Lock()
	A.netOpAll[key] = &cacheItem{
		TTL:   TTL_ALL,
		value: value,
	}
	A.lock.Unlock()
}

func (A *ACache) GetNetOpAll(key string) (interface{}, error) {
	A.lock.RLock()
	value, ok := A.netOpAll[key]
	A.lock.RUnlock()

	if ok {
		return value.value, nil
	}

	return nil, ErrKeyNotFound
}

func (A *ACache) AddSafeBinaryOnce(key string, value interface{}) {
	A.lock.Lock()
	A.binaryOnce[key] = &cacheItem{
		TTL:   TTL_ONCE,
		value: value,
	}
	A.lock.Unlock()
}

func (A *ACache) GetSafeBinaryOnce(key string) (interface{}, error) {
	A.lock.RLock()
	value, ok := A.binaryOnce[key]
	A.lock.RUnlock()
	if ok {
		return value.value, nil
	}

	return nil, ErrKeyNotFound
}

func (A *ACache) DelSafeBinaryOnce(key string) {
	A.lock.Lock()
	delete(A.binaryOnce, key)
	A.lock.Unlock()
}

func (A *ACache) ClearSafeBinaryOnce() {
	A.lock.Lock()
	A.binaryOnce = make(map[string]*cacheItem)
	A.lock.Unlock()
}

func (A *ACache) AddSafeBinaryTask(key string, value interface{}) {
	A.lock.Lock()
	A.binaryTask[key] = &cacheItem{
		TTL:   TTL_TASK,
		value: value,
	}
	A.lock.Unlock()
}

func (A *ACache) GetSafeBinaryTask(key string) (interface{}, error) {
	A.lock.RLock()
	value, ok := A.binaryTask[key]
	A.lock.RUnlock()
	if ok {
		return value.value, nil
	}

	return nil, ErrKeyNotFound
}

func (A *ACache) ClearSafeBinaryTask() {
	A.lock.Lock()
	A.binaryTask = make(map[string]*cacheItem)
	A.lock.Unlock()
}

func (A *ACache) AddSafeBinaryAll(key string, value interface{}) {
	A.lock.Lock()
	A.binaryAll[key] = &cacheItem{
		TTL:   TTL_ALL,
		value: value,
	}
	A.lock.Unlock()
}

func (A *ACache) GetSafeBinaryAll(key string) (interface{}, error) {
	A.lock.RLock()
	value, ok := A.binaryAll[key]
	A.lock.RUnlock()
	if ok {
		return value.value, nil
	}

	return nil, ErrKeyNotFound
}
