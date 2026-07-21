# AgentSentinel eBPF/LSM Runtime Event Collection

This document presents the minimal code paths needed to explain how
AgentSentinel collects process, file, and network runtime events.

> Important: `task_kill` is the only active `SEC("lsm/...")` program in this
> repository. Process execution, file, and network events are collected with
> raw tracepoints and kprobes attached to Linux `security_*` functions. The
> `SEC("lsm/file_permission")` implementation is commented out.

## End-to-end flow

```text
Kernel hook
  -> filter to the container and tracked TGIDs
  -> reserve and populate an event
  -> optionally apply the stop policy
  -> submit through a BPF ring buffer
  -> Go ring-buffer reader decodes the event
  -> subscribers receive the typed event
```

## 1. LSM hook

### Kernel program: `task_kill`

- File: `ebpf/tracer/tracer.c`
- Function: `task_kill`
- Role: Captures signal attempts made by tracked Agent processes and creates a
  process-kill event.

```c
SEC("lsm/task_kill")
int BPF_PROG(task_kill, struct task_struct *p, struct kernel_siginfo *info,
	 int sig, const struct cred *cred)
{
    if (!process_in_scope()) {
        return 0;
    }

    if (!process_is_interesting()) {
        return 0;
    }

    struct task_struct *current = (struct task_struct *)bpf_get_current_task();
    struct process_event *event =
        bpf_ringbuf_reserve(&process_events, sizeof(*event), 0);
    if (!event)
        return 0;
```

### Go attachment: `startTracing`

- File: `tracer/process_event_tracer.go`
- Function: `(*processEventTracer).startTracing`
- Role: Attaches the execution kprobe and compiled LSM program, then creates the
  process-event ring-buffer reader.

```go
l, err = link.Kprobe("security_bprm_check", pt.bpfObjs.KprobeSecurityBprmCheck, nil)
if err != nil {
	log.Error().Err(err).Msg("Attaching security_bprm_check failed")
	return err
}
pt.bpfLinks = append(pt.bpfLinks, l)

l, err = link.AttachLSM(link.LSMOptions{
	Program: pt.bpfObjs.TaskKill,
})
if err != nil {
	log.Error().Err(err).Msg("Attaching lsm_task_kill failed")
	return err
}

pt.ringbufReader, err = ringbuf.NewReader(pt.bpfObjs.ProcessEvents)
```

## 2. Process events

### Create and submit an execution event

- File: `ebpf/tracer/tracer.c`
- Function: `kprobe_security_bprm_check`
- Role: Captures a binary immediately before execution, applies the execution
  stop policy, and publishes its process metadata.

```c
struct process_event *event =
    bpf_ringbuf_reserve(&process_events, sizeof(*event), 0);
if (!event)
    return 0;

event->type = PROCESS_EVENT_TYPE_BPRM_CHECK;
event->flag = 0;
BPF_CORE_READ_INTO(&event->parent_pid, parent, pid);
BPF_CORE_READ_INTO(&event->parent_tgid, parent, tgid);
event->ns_parent_pid = get_task_pid_nr_ns(parent);
event->ns_parent_tgid = get_task_tgid_nr_ns(parent);
BPF_CORE_READ_INTO(&event->child_pid, current_task, pid);
BPF_CORE_READ_INTO(&event->child_tgid, current_task, tgid);
event->ns_child_pid = get_task_pid_nr_ns(current_task);
event->ns_child_tgid = get_task_tgid_nr_ns(current_task);
event->time = bpf_ktime_get_ns();

handle_process_stop_policy_for_exec_operations(event);
bpf_ringbuf_submit(event, 0);
```

Fork, exec, and exit lifecycle events are additionally collected by:

```c
SEC("raw_tracepoint/sched_process_fork")
SEC("raw_tracepoint/sched_process_exec")
SEC("raw_tracepoint/sched_process_exit")
```

### Go receiver

- File: `tracer/process_event_tracer.go`
- Function: `(*processEventTracer).handleProcessEvents`
- Role: Reads, decodes, logs, and forwards process events to subscribers.

```go
func (pt *processEventTracer) handleProcessEvents() {
	for {
		record, err := pt.ringbufReader.Read()
		if err != nil {
			if errors.Is(err, ringbuf.ErrClosed) {
				log.Info().Msg("ringbuf reader closed")
				return
			}
			log.Err(err).Msg("ringbuf read failed")
			continue
		}

		event, err := pt.postEventHandle(record.RawSample)
		if err != nil {
			continue
		}
```

## 3. File events

### Create and submit a file-open event

- File: `ebpf/tracer/tracer.c`
- Function: `kprobe_security_file_open`
- Role: Records the tracked TGID, path, inode, syscall, and access permissions,
  applies file policy, and publishes the event.

```c
event = bpf_ringbuf_reserve(&file_events, sizeof(*event), 0);
if (!event) {
    return 0;
}

event->time = bpf_ktime_get_ns();
event->flag = 0;
event->tgid = get_current_tgid();
event->parent_tgid = get_task_parent_tgid(current_task);
event->ns_tgid = ns_tgid;
parent_task = BPF_CORE_READ(current_task, parent);
event->ns_parent_tgid = get_task_tgid_nr_ns(parent_task);
event->type = FILE_EVENT_TYPE_FILE_OPEN;
event->u.f_open.acc_mode = perm;
event->u.f_open.syscall = syscall_id;
event->u.f_open.inode = inode;

handle_process_stop_policy_for_file_operations(event);
bpf_ringbuf_submit(event, 0);
```

Deletion and rename events use `security_inode_unlink` and
`security_inode_rename` kprobes and the same `file_events` ring buffer.

### Go receiver

- File: `tracer/file_event_tracer.go`
- Function: `(*filePermEventTracer).handleFileEvents`
- Role: Reads, decodes, logs, and forwards file events to subscribers.

```go
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
```

## 4. Network events

### Create and submit a socket-connect event

- File: `ebpf/tracer/tracer.c`
- Function: `kprobe_security_socket_connect`
- Role: Captures outbound connections from tracked TGIDs, records the remote
  address, applies network policy, and publishes the event.

```c
struct socket_event *event;
event = bpf_ringbuf_reserve(&socket_events, sizeof(*event), 0);
if (!event)
    return 0;

struct task_struct *parent_task = BPF_CORE_READ(current_task, parent);
event->time = bpf_ktime_get_ns();
event->flag = 0;
event->type = SOCKET_EVENT_TYPE_CONNECT;
event->tgid = BPF_CORE_READ(current_task, tgid);
event->parent_tgid = get_task_parent_tgid(current_task);
event->ns_tgid = get_task_tgid_nr_ns(current_task);
event->ns_parent_tgid = get_task_tgid_nr_ns(parent_task);

handle_process_stop_policy_for_net_operations(
    event, SOCKET_EVENT_TYPE_CONNECT);
bpf_ringbuf_submit(event, 0);
```

The omitted middle block copies and normalizes either the IPv4 or IPv6 remote
address before the policy call.

### Go receiver

- File: `tracer/socket_event_tracer.go`
- Function: `(*sockOpsEventTracer).handleNetEvents`
- Role: Reads and decodes remote IP/port records, logs them, and forwards typed
  network events to subscribers.

```go
func (se *sockOpsEventTracer) handleNetEvents() {
	for {
		record, err := se.ringbufReader.Read()
		if err != nil {
			if errors.Is(err, ringbuf.ErrClosed) {
				log.Info().Msg("ringbuf reader closed")
				return
			}
			log.Err(err).Msg("ringbuf read failed")
			continue
		}

		event, err := se.postEventHandle(record.RawSample)
		if err != nil {
			continue
		}
```

## Minimal presentation table

| Runtime event | Kernel hook | Ring buffer | Go receiver |
| --- | --- | --- | --- |
| Process kill | `SEC("lsm/task_kill")` | `process_events` | `handleProcessEvents` |
| Process lifecycle | scheduler raw tracepoints | `process_events` | `handleProcessEvents` |
| Program execution | `kprobe/security_bprm_check` | `process_events` | `handleProcessEvents` |
| File open | `kprobe/security_file_open` | `file_events` | `handleFileEvents` |
| File delete/rename | `security_inode_unlink/rename` kprobes | `file_events` | `handleFileEvents` |
| Network connection | `kprobe/security_socket_connect` | `socket_events` | `handleNetEvents` |

The shortest representative code walk is:

```text
kprobe_security_bprm_check()
  -> bpf_ringbuf_reserve(process_events)
  -> populate process_event
  -> bpf_ringbuf_submit(process_events)
  -> ringbufReader.Read()
  -> postEventHandle()
  -> Audit subscriber
```
