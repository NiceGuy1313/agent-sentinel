package tracer

import (
	"github.com/google/gopacket/layers"
	"net"
	"os"
)

const (
	ProcessTracer = iota + 1
	ReadlineTracer
	SocketTracer
	DNSTracer
	FileTracer

	// event flag
	EventFlagProcessStopped              = 0x1
	EventFlagProcessMayAttackRootProcess = 0x2

	// interesting process map
	DefaultInterestingPidMapValue = 1
	// enforced process map
	DefaultEnforcedProcessMapValue

	// path pattern
	MaxPathPatternLength = 64
)

type BpfTracer interface {
	AddSubscriber(string) (<-chan interface{}, error)
	DeleteSubscriber(string)
	Close()
}

type Options struct {
	EnableTracer []int
	// TODO list of container ids
	ContainerID string
	MountNSID   int
	PidNSID     int
	BashPath    string
	CgroupPath  string
}

// process stop policy

const (
	ProcessStopTypeExec = 1
	ProcessStopTypeNet  = 2
	ProcessStopTypeFile = 3
	ProcessStopTypeKill = 4

	ProcessStopCommonAlwaysStop = 1

	ProcessStopFileAccessCoreFiles = 1

	ProcessStopKillRootProcess

	ProcessStopPolicyHeaderSize = 4
)

type ProcessStopPolicy interface {
	Unify() (*ProcessStopPolicyEntry, error)
}

type ProcessStopPolicyEntry struct {
	Buffer [16]uint8
}

type ProcessStopPolicyExec struct {
	Common uint32
}

type ProcessStopPolicyKill struct {
	Common   uint32
	Flag     uint32
	RootTgid uint32
}

type ProcessStopPolicyNet struct {
	Common uint32
}

type ProcessStopPolicyFile struct {
	Common         uint32
	Flag           uint32
	FilePermission uint32
	NSRootTgid     uint32
}

// process tracer
const (
	ProcessEventTypeFork = iota + 1
	ProcessEventTypeExec
	ProcessEventTypeBprmCheck
	ProcessEventTypeExit = 4
	ProcessEventTypeKill = 5

	ProcessEventHeaderSize = 44
)

type ProcessEventHeader struct {
	Time         uint64
	Flag         uint32
	ParentPid    uint32
	ParentTgid   uint32
	NsParentPid  uint32
	NsParentTgid uint32
	ChildPid     uint32
	ChildTgid    uint32
	NsChildPid   uint32
	NsChildTgid  uint32
	Type         uint32
}

type ProcessEvent struct {
	Time            uint64
	Flag            uint32
	ParentPid       uint32
	ParentTgid      uint32
	NsParentPid     uint32
	NsParentTgid    uint32
	ChildPid        uint32
	ChildTgid       uint32
	NsChildPid      uint32
	NsChildTgid     uint32
	Type            uint32
	Syscall         uint32
	ExecutableCtime uint64
	ExecutableDev   uint32
	ExecutableInode uint32
	ExecutablePath  string
	Args            []string
	Signal          os.Signal
	TargetNSTgid    uint32
}

type ReadlineEvent struct {
	Time         uint64
	Tgid         uint32
	ParentTgid   uint32
	NsTgid       uint32
	NsParentTgid uint32
	TaskComm     string
	Readline     string
}

// file event
const (
	FileEventHeaderSize = 32

	MayExec   = 0x00000001
	MayWrite  = 0x00000002
	MayRead   = 0x00000004
	MayAppend = 0x00000008

	FileEventTypeFileOpen    = 0
	FileEventTypeInodeUnlink = 1
	FileEventTypeInodeRename = 2
)

type FileEventHeader struct {
	Time         uint64
	Flag         uint32
	Tgid         uint32
	ParentTgid   uint32
	NsTgid       uint32
	NsParentTgid uint32
	Type         uint32
}

type FileEvent struct {
	Time         uint64
	Flag         uint32
	Tgid         uint32
	ParentTgid   uint32
	NsTgid       uint32
	NsParentTgid uint32
	Type         uint32
	Ctime        uint64
	Dev          uint32
	Inode        uint32
	Syscall      uint32
	AccMode      uint32
	Path         string
	NewPath      string
}

// net tracer

const (
	SocketEventTypeConnect    = 1
	SocketEventTypeListen     = 2
	SocketEventTypeAccept     = 3
	SocketEventTypeAcceptExit = 4

	SocketEventHeaderSize = 28
)

type SocketEventHeader struct {
	Time         uint64
	Flag         uint32
	Tgid         uint32
	ParentTgid   uint32
	NsTgid       uint32
	NsParentTgid uint32
	Type         uint32
}

type SockaddrInet4 struct {
	SinPort uint16
	SinAddr uint32
}

type SockaddrInet6 struct {
	Sin6Port     uint16
	Sin6Flowinfo uint32
	Sin6Addr     [16]uint8
	Sin6ScopeId  uint32
}

type SocketEvent struct {
	Time         uint64
	Flag         uint32
	Tgid         uint32
	ParentTgid   uint32
	NsTgid       uint32
	NsParentTgid uint32
	Type         uint32
	Family       uint32
	RemoteIP     net.IP
	RemotePort   uint16
}

type DNSEvent struct {
	Time      uint64
	Questions []layers.DNSQuestion
	Answers   []layers.DNSResourceRecord
}

type PathPattern struct {
	Prefix string
}

type PathPatternEntry struct {
	Buffer [64]uint8
}
