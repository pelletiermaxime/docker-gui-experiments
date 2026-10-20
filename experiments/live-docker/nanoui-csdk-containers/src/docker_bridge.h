#ifndef FERRYDOCK_DOCKER_BRIDGE_H
#define FERRYDOCK_DOCKER_BRIDGE_H
#include <stddef.h>
struct fd_response { unsigned char *data; size_t size; long status; int transport; };
int fd_docker_init(void);
void fd_docker_cleanup(void);
int fd_docker_get(const char *url, long timeout_ms, struct fd_response *out);
void fd_docker_response_free(struct fd_response *response);
#endif
