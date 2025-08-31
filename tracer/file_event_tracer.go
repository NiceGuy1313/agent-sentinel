package tracer

import (
	"bytes"
	"encoding/binary"
	"errors"
	"github.com/cilium/ebpf/link"
	"github.com/cilium/ebpf/ringbuf"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"golang.org/x/sys/unix"
	"sync"
)

type filePermEventTracer struct {
	bpfObjs          *tracingObjects
	bpfLinks         []link.Link
	ringbufReader    *ringbuf.Reader
	eventSubscribers map[string]chan<- interface{}
	lock             sync.Mutex
}

func newFilePermEventTracer(bpfObjs *tracingObjects) (*filePermEventTracer, error) {
	rt := &filePermEventTracer{
		bpfObjs:          bpfObjs,
		eventSubscribers: make(map[string]chan<- interface{}),
	}

	return rt, nil
}

func (fe *filePermEventTracer) startTracing() error {
	l, err := link.Kprobe("security_file_open", fe.bpfObjs.KprobeSecurityFileOpen, nil)
	if err != nil {
		log.Error().Err(err).Msg("Attaching security_file_open failed")
		return err
	}
	fe.bpfLinks = append(fe.bpfLinks, l)

	l, err = link.Kprobe("security_inode_unlink", fe.bpfObjs.KprobeSecurityInodeUnlink, nil)
	if err != nil {
		log.Error().Err(err).Msg("Attaching security_inode_unlink failed")
		return err
	}
	fe.bpfLinks = append(fe.bpfLinks, l)

	l, err = link.Kprobe("security_inode_rename", fe.bpfObjs.KprobeSecurityInodeRename, nil)
	if err != nil {
		log.Error().Err(err).Msg("Attaching security_inode_rename failed")
		return err
	}
	fe.bpfLinks = append(fe.bpfLinks, l)

	// create ringbuf reader
	fe.ringbufReader, err = ringbuf.NewReader(fe.bpfObjs.FileEvents)
	if err != nil {
		log.Error().Err(err).Msg("Creating ringbuf reader failed")
		return err
	}

	// start callback of file event
	go fe.handleFileEvents()

	log.Info().Msg("lsm_file_permission tracer started")
	return nil
}

func (fe *filePermEventTracer) stopTracing() {
	for _, l := range fe.bpfLinks {
		if err := l.Close(); err != nil {
			log.Error().Err(err).Msg("Unattaching lsm_file_permission failed")
		}
	}

	if fe.ringbufReader != nil {
		if err := fe.ringbufReader.Close(); err != nil {
			log.Error().Err(err).Msg("Closing ringbuf reader failed")
		}
	}

	// notify if subscribers are available
	if len(fe.eventSubscribers) > 0 {
		for _, sub := range fe.eventSubscribers {
			close(sub)
		}
		fe.eventSubscribers = make(map[string]chan<- interface{})
	}
	log.Info().Msg("lsm_file_permission tracer stopped")
}

func (fe *filePermEventTracer) Close() {
	fe.stopTracing()
}

func (fe *filePermEventTracer) handleFileEvents() {
	for {
		record, err := fe.ringbufReader.Read()
		if err != nil {
			if errors.Is(err, ringbuf.ErrClosed) {
				log.Info().Msg("ringbuf reader closed")
				return
			}
			log.Err(err).Msg("ringbuf read failed")
			continue
		}

		event, err := fe.postEventHandle(record.RawSample)
		if err != nil {
			continue
		}

		log.Debug().
			Dict("data", FileEventToLogEvent(event)).Msg("file_event_record")

		for _, sub := range fe.eventSubscribers {
			sub <- event
		}
	}
}

func (fe *filePermEventTracer) postEventHandle(raw []byte) (*FileEvent, error) {
	buffer := bytes.NewBuffer(raw)
	var header FileEventHeader

	if err := binary.Read(buffer, binary.LittleEndian, &header); err != nil {
		log.Err(err).Msg("Parse ringbuf event failed")
		return nil, err
	}

	event := &FileEvent{
		Time:         header.Time,
		Flag:         header.Flag,
		Tgid:         header.Tgid,
		ParentTgid:   header.ParentTgid,
		NsTgid:       header.NsTgid,
		NsParentTgid: header.NsParentTgid,
		Type:         header.Type,
	}

	switch header.Type {
	case FileEventTypeFileOpen:
		var fileOpenEvent tracingFileOpenEvent
		if err := binary.Read(buffer, binary.LittleEndian, &fileOpenEvent); err != nil {
			log.Err(err).Msg("Parse ringbuf event failed")
			return nil, err
		}

		event.Ctime = fileOpenEvent.Ctime
		event.Dev = fileOpenEvent.Dev
		event.Inode = fileOpenEvent.Inode
		event.Syscall = fileOpenEvent.Syscall
		event.AccMode = fileOpenEvent.AccMode
		event.Path = unix.ByteSliceToString(fileOpenEvent.Path[:])

	case FileEventTypeInodeUnlink:
		var inodeUnlinkEvent tracingInodeUnlinkEvent
		if err := binary.Read(buffer, binary.LittleEndian, &inodeUnlinkEvent); err != nil {
			log.Err(err).Msg("Parse ringbuf event failed")
			return nil, err
		}

		event.Ctime = inodeUnlinkEvent.Ctime
		event.Dev = inodeUnlinkEvent.Dev
		event.Inode = inodeUnlinkEvent.Inode
		event.Syscall = inodeUnlinkEvent.Syscall
		event.Path = unix.ByteSliceToString(inodeUnlinkEvent.Path[:])
	case FileEventTypeInodeRename:
		var inodeRenameEvent tracingInodeRenameEvent
		if err := binary.Read(buffer, binary.LittleEndian, &inodeRenameEvent); err != nil {
			log.Err(err).Msg("Parse ringbuf event failed")
			return nil, err
		}

		event.Ctime = inodeRenameEvent.Ctime
		event.Dev = inodeRenameEvent.Dev
		event.Inode = inodeRenameEvent.Inode
		event.Syscall = inodeRenameEvent.Syscall
		event.Path = unix.ByteSliceToString(inodeRenameEvent.OldPath[:])
		event.NewPath = unix.ByteSliceToString(inodeRenameEvent.NewPath[:])
	}

	return event, nil
}

func (fe *filePermEventTracer) AddSubscriber(name string) (<-chan interface{}, error) {
	ch := make(chan interface{})
	fe.lock.Lock()
	fe.eventSubscribers[name] = ch
	fe.lock.Unlock()

	// enable tracing
	if len(fe.eventSubscribers) == 1 {
		err := fe.startTracing()
		if err != nil {
			return nil, err
		}
	}

	return ch, nil
}

func (fe *filePermEventTracer) DeleteSubscriber(name string) {
	close(fe.eventSubscribers[name])
	fe.lock.Lock()
	delete(fe.eventSubscribers, name)
	fe.lock.Unlock()

	// disable tracing if there is no available subscriber
	if len(fe.eventSubscribers) == 0 {
		fe.stopTracing()
	}
}

func FileEventToLogEvent(event *FileEvent) *zerolog.Event {
	return zerolog.Dict().
		Uint64("time", event.Time).
		Uint32("flag", event.Flag).
		Uint32("pid", event.Tgid).
		Uint32("ppid", event.ParentTgid).
		Uint32("ns_pid", event.NsTgid).
		Uint32("ns_ppid", event.NsParentTgid).
		Uint32("type", event.Type).
		Uint32("syscall", event.Syscall).
		Uint64("ctime", event.Ctime).
		Uint32("device", event.Dev).
		Uint32("inode", event.Inode).
		Uint32("acc_mode", event.AccMode).
		Str("path", event.Path).
		Str("new_path", event.NewPath)
}
