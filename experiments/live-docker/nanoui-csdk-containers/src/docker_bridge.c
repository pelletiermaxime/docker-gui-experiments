#include "docker_bridge.h"
#include "docker.h"

int fd_docker_init(void) { return (int)curl_global_init(CURL_GLOBAL_DEFAULT); }
void fd_docker_cleanup(void) { curl_global_cleanup(); }

int fd_docker_get(const char *url, long timeout_ms, struct fd_response *out) {
    *out = (struct fd_response){0};
    DOCKER *client = docker_init("v1.55");
    if (!client) return -1;
    curl_easy_setopt(client->curl, CURLOPT_NOSIGNAL, 1L);
    curl_easy_setopt(client->curl, CURLOPT_TIMEOUT_MS, timeout_ms);
    out->transport = (int)docker_get_with_http_status(client, (char *)url, &out->status);
    out->size = client->buffer->size;
    if (out->size) {
        out->data = malloc(out->size);
        if (!out->data) { docker_destroy(client); return -1; }
        memcpy(out->data, docker_buffer(client), out->size);
    }
    docker_destroy(client);
    return 0;
}

void fd_docker_response_free(struct fd_response *response) {
    free(response->data);
    *response = (struct fd_response){0};
}
