#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <string.h>
#include <X11/Xlib.h>


int xdo_get_window_size(Display *xdpy, Window wid, unsigned int *width_ret,
                        unsigned int *height_ret) {
  int ret;
  XWindowAttributes attr;
  ret = XGetWindowAttributes(xdpy, wid, &attr);
  if (ret != 0) {
    if (width_ret != NULL) {
      *width_ret = attr.width;
    }

    if (height_ret != NULL) {
      *height_ret = attr.height;
    }
  }
  return 0;
}

int main () {
  Display *xdpy;
  if ((xdpy = XOpenDisplay(":1")) == NULL) {
      /* Can't use _xdo_eprintf yet ... */
      fprintf(stderr, "Error: Can't open display: %s\n", "");
      return 0;
  }

  xdo_get_window_size(xdpy, 18874377, NULL, NULL);
  XCloseDisplay(xdpy);
  return 0;
}