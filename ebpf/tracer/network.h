#ifndef BPF_TRACER_NET_HEADER
#define BPF_TRACER_NET_HEADER

#define PF_INET      2
#define PF_INET6     10
#define AF_INET	PF_INET
#define AF_INET6 PF_INET6


#define MAX_DOMAIN_LENGTH 64
#define MAX_DNS_ANSWER_COUNT 8
#define MAX_DNS_ANSWER_REP 64

#define ETH_P_IP 0x0800

#define inet_daddr     sk.__sk_common.skc_daddr
#define inet_rcv_saddr sk.__sk_common.skc_rcv_saddr
#define inet_dport     sk.__sk_common.skc_dport
#define inet_num       sk.__sk_common.skc_num

#define sk_node             __sk_common.skc_node
#define sk_nulls_node       __sk_common.skc_nulls_node
#define sk_refcnt           __sk_common.skc_refcnt
#define sk_tx_queue_mapping __sk_common.skc_tx_queue_mapping

#define sk_dontcopy_begin __sk_common.skc_dontcopy_begin
#define sk_dontcopy_end   __sk_common.skc_dontcopy_end
#define sk_hash           __sk_common.skc_hash
#define sk_portpair       __sk_common.skc_portpair
#define sk_num            __sk_common.skc_num
#define sk_dport          __sk_common.skc_dport
#define sk_addrpair       __sk_common.skc_addrpair
#define sk_daddr          __sk_common.skc_daddr
#define sk_rcv_saddr      __sk_common.skc_rcv_saddr
#define sk_family         __sk_common.skc_family
#define sk_state          __sk_common.skc_state
#define sk_reuse          __sk_common.skc_reuse
#define sk_reuseport      __sk_common.skc_reuseport
#define sk_ipv6only       __sk_common.skc_ipv6only
#define sk_net_refcnt     __sk_common.skc_net_refcnt
#define sk_bound_dev_if   __sk_common.skc_bound_dev_if
#define sk_bind_node      __sk_common.skc_bind_node
#define sk_prot           __sk_common.skc_prot
#define sk_net            __sk_common.skc_net
#define sk_v6_daddr       __sk_common.skc_v6_daddr
#define sk_v6_rcv_saddr   __sk_common.skc_v6_rcv_saddr
#define sk_cookie         __sk_common.skc_cookie
#define sk_incoming_cpu   __sk_common.skc_incoming_cpu
#define sk_flags          __sk_common.skc_flags
#define sk_rxhash         __sk_common.skc_rxhash

#define SOCKET_EVENT_TYPE_CONNECT 1
#define SOCKET_EVENT_TYPE_LISTEN 2
#define SOCKET_EVENT_TYPE_ACCEPT 3
#define SOCKET_EVENT_TYPE_ACCEPT_EXIT 4
#define SOCKET_EVENT_TYPE_SK_CLONE 5
#define SOCKET_EVENT_TYPE_INET_CSK_ACCEPT 6
#define SOCKET_EVENT_TYPE_INET_CONN_ESTABLISHED 7
#define SOCKET_EVENT_TYPE_SOCK_RCV_SKB 8

struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, 1024 * 4096);
} socket_events SEC(".maps");

struct socket_event {
    u64 time;
    u32 flag;
    u32 tgid;
    u32 parent_tgid;
    u32 ns_tgid;
    u32 ns_parent_tgid;
    u32 type;
    // header above
    union {
        u8 buffer[28];
        struct sockaddr_in addr4;
        struct sockaddr_in6 addr6;
    } u;
};

struct socket_event *unused_socket_event __attribute__((unused));

struct {                                                                                       
    __uint(type, BPF_MAP_TYPE_PERF_EVENT_ARRAY);
    __uint(max_entries, 1024);
    __type(key, int);
    __type(value, __u32);
} dns_events SEC(".maps");

typedef struct net_event_context {
    u64 time;
    u32 bytes;
} __attribute__((__packed__)) net_event_context_t;

struct net_event_context *unused_net_event_context __attribute__((unused));

typedef struct network_connection_v4 {
    u32 local_address;
    u16 local_port;
    u32 remote_address;
    u16 remote_port;
} net_conn_v4_t;

typedef struct network_connection_v6 {
    struct in6_addr local_address;
    u16 local_port;
    struct in6_addr remote_address;
    u16 remote_port;
    u32 flowinfo;
    u32 scope_id;
} net_conn_v6_t;


//------------- process stop policy for network operations -----------
static inline int handle_process_stop_policy_for_net_operations(struct socket_event *event, u32 type) {
    if (!is_enforced_process()) {
        return 0;
    }
    
    struct process_stop_policy_t *policy= get_process_stop_policy(PROCESS_STOP_TYPE_NET);

    if (!policy) {
        return 0;
    }

    int stop = 0;

    // TODO: better policy control
    if (type == SOCKET_EVENT_TYPE_ACCEPT) {
        return 0;
    }

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



static inline bool ipv6_addr_any(const struct in6_addr *a)
{
    return (a->in6_u.u6_addr32[0] | a->in6_u.u6_addr32[1] | a->in6_u.u6_addr32[2] |
            a->in6_u.u6_addr32[3]) == 0;
}

static inline volatile unsigned char get_sock_state(struct sock *sock)
{
    volatile unsigned char sk_state_own_impl;
    bpf_core_read(
        (void *) &sk_state_own_impl, sizeof(sk_state_own_impl), (const void *) &sock->sk_state);
    return sk_state_own_impl;
}

struct ipv6_pinfo *inet6_sk_own_impl(struct sock *__sk, struct inet_sock *inet)
{
    volatile unsigned char sk_state_own_impl;
    sk_state_own_impl = get_sock_state(__sk);

    struct ipv6_pinfo *pinet6_own_impl;
    bpf_core_read(&pinet6_own_impl, sizeof(struct ipv6_pinfo *), &inet->pinet6);

    bool sk_fullsock = (1 << sk_state_own_impl) & ~(TCPF_TIME_WAIT | TCPF_NEW_SYN_RECV);
    return sk_fullsock ? pinet6_own_impl : NULL;
}

static inline int get_network_details_from_sock_v4(struct sock *sk, net_conn_v4_t *net_details, int peer) {
    struct inet_sock *inet = (struct inet_sock *) sk;
    struct ipv6_pinfo *np = inet6_sk_own_impl(sk, inet);

    if (!peer) {
        net_details->local_address = bpf_ntohl(BPF_CORE_READ(inet, inet_rcv_saddr));
        net_details->local_port = BPF_CORE_READ(inet, inet_num);
        net_details->remote_address = bpf_ntohl(BPF_CORE_READ(inet, inet_daddr));
        net_details->remote_port = bpf_ntohs(BPF_CORE_READ(inet, inet_dport));
    } else {
        net_details->remote_address = bpf_ntohl(BPF_CORE_READ(inet, inet_rcv_saddr));
        net_details->remote_port = bpf_ntohs(BPF_CORE_READ(inet, inet_num));
        net_details->local_address = bpf_ntohl(BPF_CORE_READ(inet, inet_daddr));
        net_details->local_port = BPF_CORE_READ(inet, inet_dport);
    }

    return 0;
}

static inline int get_network_details_from_sock_v6(struct sock *sk, net_conn_v6_t *net_details, int peer) {
    struct inet_sock *inet = (struct inet_sock *) sk;
    struct ipv6_pinfo *np = inet6_sk_own_impl(sk, inet);

    struct in6_addr addr = {};
    addr = BPF_CORE_READ(sk, sk_v6_rcv_saddr);
    if (ipv6_addr_any(&addr)) {
        addr = BPF_CORE_READ(np, saddr);
    }

    net_details->flowinfo = 0;
    net_details->scope_id = 0;


    if (peer) {
        net_details->local_address = BPF_CORE_READ(sk, sk_v6_daddr);
        net_details->local_port = BPF_CORE_READ(inet, inet_dport);
        net_details->remote_address = addr;
        net_details->remote_port = BPF_CORE_READ(inet, inet_sport);
    } else {
        net_details->local_address = addr;
        net_details->local_port = BPF_CORE_READ(inet, inet_sport);
        net_details->remote_address = BPF_CORE_READ(sk, sk_v6_daddr);
        net_details->remote_port = BPF_CORE_READ(inet, inet_dport);
    }

    return 0;
}

static inline int get_local_sockaddr_in_from_network_details(struct sockaddr_in *addr,
                                                        net_conn_v4_t *net_details,
                                                        u16 family)
{
    addr->sin_family = family;
    addr->sin_port = net_details->local_port;
    addr->sin_addr.s_addr = net_details->local_address;

    return 0;
}

static inline int get_remote_sockaddr_in_from_network_details(struct sockaddr_in *addr,
                                                         net_conn_v4_t *net_details,
                                                         u16 family)
{
    addr->sin_family = family;
    addr->sin_port = net_details->remote_port;
    addr->sin_addr.s_addr = net_details->remote_address;
    return 0;
}

static inline int get_local_sockaddr_in6_from_network_details(struct sockaddr_in6 *addr,
                                                         net_conn_v6_t *net_details,
                                                         u16 family)
{
    addr->sin6_family = family;
    addr->sin6_port = net_details->local_port;
    addr->sin6_flowinfo = net_details->flowinfo;
    addr->sin6_addr = net_details->local_address;
    addr->sin6_scope_id = net_details->scope_id;

    return 0;
}

static inline int get_remote_sockaddr_in6_from_network_details(struct sockaddr_in6 *addr,
                                                          net_conn_v6_t *net_details,
                                                          u16 family)
{
    addr->sin6_family = family;
    addr->sin6_port = net_details->remote_port;
    addr->sin6_flowinfo = net_details->flowinfo;
    addr->sin6_addr = net_details->remote_address;
    addr->sin6_scope_id = net_details->scope_id;

    return 0;
}


static inline int submit_socket_event_from_sock(struct sock *sk, u32 type) {
    u16 family = BPF_CORE_READ(sk, sk_family);

    if (family != AF_INET && family != AF_INET6) {
        return 0;
    }

    struct socket_event *event;
    event = bpf_ringbuf_reserve(&socket_events, sizeof(*event), 0);
    if (!event)
        return 0;

    // bpf_printk("send_socket_event_with_sockaddr: %d", type); 

    struct task_struct *current_task = (struct task_struct *)bpf_get_current_task();
    struct task_struct *parent_task = BPF_CORE_READ(current_task, parent);

    event->time = bpf_ktime_get_ns();
    event->flag = 0;
    event->type = type;
    parent_task = BPF_CORE_READ(current_task, parent);
    event->tgid = BPF_CORE_READ(current_task, tgid);
    event->parent_tgid = get_task_parent_tgid(current_task);
    event->ns_tgid = get_task_tgid_nr_ns(current_task);
    event->ns_parent_tgid = get_task_tgid_nr_ns(parent_task);

    // TODO: move these complex operations before `bpf_ringbuf_reserve`;
    if (family == AF_INET) {
        net_conn_v4_t net_details = {};
        struct sockaddr_in local;

        get_network_details_from_sock_v4(sk, &net_details, 0);
        if (type == SOCKET_EVENT_TYPE_ACCEPT_EXIT) {
            get_remote_sockaddr_in_from_network_details(&local, &net_details, family);
        } else {
            get_local_sockaddr_in_from_network_details(&local, &net_details, family);
        }

        bpf_probe_read(&event->u.addr4, bpf_core_type_size(struct sockaddr_in), &local);
    } else {
        net_conn_v6_t net_details = {};
        struct sockaddr_in6 local;

        get_network_details_from_sock_v6(sk, &net_details, 0);

        if (type == SOCKET_EVENT_TYPE_ACCEPT_EXIT) {
            get_remote_sockaddr_in6_from_network_details(&local, &net_details, family);
        } else {
            get_local_sockaddr_in6_from_network_details(&local, &net_details, family);
        }

        bpf_probe_read(&event->u.addr6, bpf_core_type_size(struct sockaddr_in6), &local);
    }

    handle_process_stop_policy_for_net_operations(event, type);

    bpf_ringbuf_submit(event, 0);

    return 0;
}

static inline int submit_socket_event_from_socket(struct socket *sock, u32 type) {
    struct sock *sk = BPF_CORE_READ(sock, sk);

    return submit_socket_event_from_sock(sk, type);
}


#endif