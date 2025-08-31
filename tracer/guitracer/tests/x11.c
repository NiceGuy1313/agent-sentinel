#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <string.h>
#include <X11/Xlib.h>
#include <netinet/in.h>
#include <sys/types.h> 
#include <unistd.h>
#include <arpa/inet.h>


int main() {
    // int fd;
    // struct sockaddr_un addr;

    // fd = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
    // printf("fd = %d, error=%s \n", fd, strerror(errno));
    // addr.sun_family = AF_UNIX;
    // addr.sun_path[0] = '\0';
    // strcpy(addr.sun_path + 1, "/tmp/.X11-unix/X1");
    // int ret = connect(fd, (struct sockaddr *)&addr, 20);
    // printf("ret = %d, error=%s \n", ret, strerror(errno));

    // Display *xdpy;
    // if ((xdpy = XOpenDisplay("")) == NULL) {
    //     /* Can't use _xdo_eprintf yet ... */
    //     fprintf(stderr, "Error: Can't open display: %s\n", "");
    //     return 0;
    // }

    // XCloseDisplay(xdpy);
    // return 0;

    int fd;
    struct sockaddr_in addr;

    fd = socket(AF_INET, SOCK_STREAM | SOCK_CLOEXEC, 0);
    printf("fd = %d, error=%s \n", fd, strerror(errno));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = inet_addr("127.0.0.1");
    addr.sin_port = htons(8889);
    int ret = connect(fd, (struct sockaddr *)&addr, sizeof(addr));
    printf("ret = %d, error=%s \n", ret, strerror(errno));
}

/*
socket(AF_UNIX, SOCK_STREAM|SOCK_CLOEXEC, 0) = 3
connect(3, {sa_family=AF_UNIX, sun_path=@"/tmp/.X11-unix/X1"}, 20) = 0
getpeername(3, {sa_family=AF_UNIX, sun_path=@"/tmp/.X11-unix/X1"}, [124 => 20]) = 0
uname({sysname="Linux", nodename="ac1edd5444a7", ...}) = 0
access("/home/computeruse/.Xauthority", R_OK) = -1 ENOENT (No such file or directory)
fcntl(3, F_GETFL)                       = 0x2 (flags O_RDWR)
fcntl(3, F_SETFL, O_RDWR|O_NONBLOCK)    = 0
fcntl(3, F_SETFD, FD_CLOEXEC)           = 0
*/
