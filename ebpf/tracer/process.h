#ifndef BPF_TRACER_PROCESS_HEADER
#define BPF_TRACER_PROCESS_HEADER

#define MAX_LINE_SIZE 128

#define MAX_ARR_LEN 1024
#define MAX_ARR_NUM 24
#define MAX_STRING_LEN 128

#define PROCESS_EVENT_TYPE_FORK 1
#define PROCESS_EVENT_TYPE_EXEC 2
#define PROCESS_EVENT_TYPE_BPRM_CHECK 3
#define PROCESS_EVENT_TYPE_EXIT 4
#define PROCESS_EVENT_TYPE_KILL 5


// struct {
//     __uint(type, BPF_MAP_TYPE_PERF_EVENT_ARRAY);
// } process_events SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, 1024 * 4096 /* 256 KB */);
} process_events SEC(".maps");

struct process_exec_event {
    u32 syscall;
    u32 dev;
    u32 inode;
    u64 ctime;
    u8 filepath[MAX_PATH_LEN];
    u8 args_arr[MAX_ARR_LEN];
};

struct process_kill_event {
    u32 syscall;
    u32 signal;
    u32 target_ns_tgid;
};

struct process_event {
    u64 time;
    u32 flag;
    u32 parent_pid;
    u32 parent_tgid;
    u32 ns_parent_pid;
    u32 ns_parent_tgid;
    u32 child_pid;
    u32 child_tgid;
    u32 ns_child_pid;
    u32 ns_child_tgid;
    u32 type;
    // header above
    union {
        u8 buffer[5140];
        struct process_exec_event exec_event;
        struct process_kill_event kill_event;
    } u;
};

const struct process_event *unused_process_event __attribute__((unused));

struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, 256 * 1024 /* 256 KB */);
} readline_events SEC(".maps");

struct readline_event {
    u64 time;
    u32 tgid;
    u32 parent_tgid;
    u32 ns_tgid;
    u32 ns_parent_tgid;
    u8 task_comm[TASK_COMM_LEN];
    u8 readline [MAX_LINE_SIZE];
};

const struct readline_event *unused_readline_event __attribute__((unused));

struct args_buffer_t {
    u8 buf[MAX_ARR_LEN];
};

// maps for parsing args use
struct {
  __uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
  __type(key, u32);
  __type(value, struct args_buffer_t);
  __uint(max_entries, 1);
} args_buffers SEC(".maps");

static __always_inline struct args_buffer_t *get_args_buf(int idx) {
  return bpf_map_lookup_elem(&args_buffers, &idx);
}

// maps for parsing process exec event use
struct {
  __uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
  __type(key, u32);
  __type(value, struct process_exec_event);
  __uint(max_entries, 1);
} process_exec_event_buffers SEC(".maps");

static __always_inline struct process_exec_event *get_process_exec_event_buf(int idx) {
  return bpf_map_lookup_elem(&process_exec_event_buffers, &idx);
}

//------------- process stop policy for exec operations -----------
static inline int handle_process_stop_policy_for_exec_operations(struct process_event *event) {
    if (!is_enforced_process()) {
        return 0;
    }
    
    struct process_stop_policy_t *policy= get_process_stop_policy(PROCESS_STOP_TYPE_EXEC);

    if (!policy) {
        return 0;
    }

    int stop = 0;

    if (policy->common & PROCESS_STOP_COMMON_ALWAYS_STOP) {
        stop = 1;
    }

    if (stop) {
        int sig_ret = bpf_send_signal(SIGSTOP);
        if (!sig_ret) {
            event->flag |= EVENT_FLAG_PROCESS_STOPPED;
            // increment_enforcement_op();
        }
    }

    return 0;   
}

//------------- process stop policy for kill operations -----------
static inline int handle_process_stop_policy_for_kill_operations(struct process_event *event) {
    if (!is_enforced_process()) {
        return 0;
    }
    
    struct process_stop_policy_t *policy = get_process_stop_policy(PROCESS_STOP_TYPE_KILL);

    if (!policy) {
        return 0;
    }

    int stop = 0;

    bpf_printk("policy %d,%d", policy->kill.flag, policy->kill.ns_root_tgid);

    // enforce sensitive signals to root process    
    if ((policy->kill.flag & PROCESS_STOP_KILL_ROOT_PROCESS)
        && event->u.kill_event.target_ns_tgid == policy->kill.ns_root_tgid
        && (event->u.kill_event.signal == SIGKILL
            || event->u.kill_event.signal == SIGSTOP
            || event->u.kill_event.signal == SIGINT
            || event->u.kill_event.signal == SIGTERM)) {
        stop = 1;
        event->flag |= EVENT_FLAG_PROCESS_MAY_ATTACK_ROOT_PROCESS;
        // NOTE: we can not stop this signal sending operation by sending an another stop signal.
    }

    if (stop) {
        int sig_ret = bpf_send_signal(SIGKILL);
        if (!sig_ret) {
            event->flag |= EVENT_FLAG_PROCESS_STOPPED;
            // increment_enforcement_op();
        }
    }

    return 0;   
}



static inline int save_args_arr_to_buf(struct args_buffer_t *buf, const u8 *start, const u8 *end, int num) {
    // [len][elem_num][null delimited string array]
    if (start >= end)
        return 0;

    int len = end - start;

    if (len > (MAX_ARR_LEN -1 - 2 * sizeof(int))) {
        len = MAX_ARR_LEN - 1 - 2 * sizeof(int);
    }

    bpf_probe_read(&buf->buf, sizeof(int), &len);
    bpf_probe_read((void *)buf->buf + sizeof(int), sizeof(int), &num);
    bpf_probe_read((void *)buf->buf + 2 * sizeof(int), len & (MAX_ARR_LEN - 1 - 2 * sizeof(int)), start);

    return 0;
}

static inline int save_str_arr_to_buf(struct args_buffer_t *buf, const char **args) {
    int i;
    int len = 0;
    int num = 0;
    int offset = 2 * sizeof(int);

    #pragma unroll
    for (i = 0; i < MAX_ARR_NUM; i++) {
        const char *str;
        bpf_probe_read(&str, sizeof(str), (void *)&args[i]);
        if (!str) {
            break;
        }

        if (offset > (MAX_ARR_LEN - MAX_STRING_LEN - 1)) {
            break;
        }

        int read_len = bpf_probe_read_str((void *)buf->buf + (offset & (MAX_ARR_LEN - MAX_STRING_LEN - 1)), MAX_STRING_LEN, str);

        if (read_len > 0) {
            len += read_len;
            offset += read_len;
            num++;
            continue;
        } else {
            break;
        }
    }

    if (len > 0) {
        bpf_probe_read(&buf->buf, sizeof(int), &len);
        bpf_probe_read((void *)buf->buf + sizeof(int), sizeof(int), &num);
    }

    return 0;
}

static inline int init_process_exec_event_from_linux_binprm (struct linux_binprm *bprm, struct syscall_cache_t *cached_syscall, u32 event_type, struct process_exec_event *event) {
    struct task_struct *current_task = (struct task_struct *)bpf_get_current_task();
    int syscall_id = get_current_task_syscall_id();
    struct file *file = BPF_CORE_READ(bprm, file);

    struct path_buffer_t *path_buf = (struct path_buffer_t *) get_path_buf(0);
    if (!path_buf) {
        return 0;
    }

    struct path f_path = BPF_CORE_READ(file, f_path);
    struct buf_offset buf_off;

    u8 file_path_is_available = 1;
    if (!prepend_path(&f_path, path_buf, &buf_off)) {
        file_path_is_available = 0;
    }

    struct args_buffer_t *args_buf = get_args_buf(0);
    if (args_buf) {
        // init length and num of elements
        __builtin_memset(args_buf, 0, 2 * sizeof(int));

        if (cached_syscall) {
            save_str_arr_to_buf(args_buf, (const char **)cached_syscall->exec.args);
        } else {
            if (event_type == PROCESS_EVENT_TYPE_EXEC) {
                struct mm_struct *mm = BPF_CORE_READ(current_task, mm);

                long unsigned int arg_start, arg_end;
                arg_start = BPF_CORE_READ(mm, arg_start);
                arg_end = BPF_CORE_READ(mm, arg_end);
                int argc = BPF_CORE_READ(bprm, argc);

                save_args_arr_to_buf(args_buf, (void *)arg_start, (void *)arg_end, argc);
            }
        }
    }

    event->syscall = syscall_id;
    event->dev = get_dev_from_file(file);
    event->inode = get_inode_nr_from_file(file);
    event->ctime = get_ctime_nanosec_from_file(file);

    if (file_path_is_available) {
        bpf_probe_read_str(&event->filepath, 
        MAX_PATH_LEN - (buf_off.offset & (MAX_PATH_LEN - 1)), 
        &path_buf->buf[(buf_off.offset & (MAX_PATH_LEN - 1))]);
    } else {
        bpf_probe_read_str(&event->filepath, sizeof(event->filepath), BPF_CORE_READ(bprm, filename));
    }

    if (args_buf) {
        bpf_probe_read(&event->args_arr, sizeof(event->args_arr) ,args_buf->buf);
    }

    return 0;
}

#endif