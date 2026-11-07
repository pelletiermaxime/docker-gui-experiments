#define _GNU_SOURCE
#include <assert.h>
#include <fcntl.h>
#include <png.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include <wayland-client.h>
#include <gbm.h>
#include <drm_fourcc.h>
#include <xf86drm.h>
#include <sys/types.h>
#include "linux-dmabuf.h"
#include "ext-foreign-toplevel-list.h"
#include "ext-image-capture-source.h"
#include "ext-image-copy-capture.h"

static struct wl_shm *shm;
static struct zwp_linux_dmabuf_v1 *dmabuf;
static uint32_t dma_format;
static dev_t capture_device;
static struct ext_foreign_toplevel_list_v1 *list;
static struct ext_foreign_toplevel_handle_v1 *target;
static struct ext_foreign_toplevel_image_capture_source_manager_v1 *sources;
static struct ext_image_copy_capture_manager_v1 *captures;
static uint32_t width, height, format = UINT32_MAX;
static bool constraints, complete, failed;
static const char *target_name="dev.ferrydock.RuneLiveContainers";

static void closed(void *d, struct ext_foreign_toplevel_handle_v1 *h) {}
static void done(void *d, struct ext_foreign_toplevel_handle_v1 *h) {}
static void title(void *d, struct ext_foreign_toplevel_handle_v1 *h, const char *s) {if(!strcmp(s,target_name)) target=h;}
static void identifier(void *d, struct ext_foreign_toplevel_handle_v1 *h, const char *s) {}
static void app_id(void *d, struct ext_foreign_toplevel_handle_v1 *h, const char *s) {
    if (!strcmp(s, target_name)) target = h;
}
static const struct ext_foreign_toplevel_handle_v1_listener top_listener = {
    .closed=closed, .done=done, .title=title, .app_id=app_id, .identifier=identifier,
};
static void toplevel(void *d, struct ext_foreign_toplevel_list_v1 *l, struct ext_foreign_toplevel_handle_v1 *h) {
    ext_foreign_toplevel_handle_v1_add_listener(h, &top_listener, NULL);
}
static void finished(void *d, struct ext_foreign_toplevel_list_v1 *l) {}
static const struct ext_foreign_toplevel_list_v1_listener list_listener = {.toplevel=toplevel, .finished=finished};
static void global(void *d, struct wl_registry *r, uint32_t n, const char *i, uint32_t v) {
    if (!strcmp(i, wl_shm_interface.name)) shm = wl_registry_bind(r, n, &wl_shm_interface, 1);
    if (!strcmp(i, zwp_linux_dmabuf_v1_interface.name)) dmabuf = wl_registry_bind(r,n,&zwp_linux_dmabuf_v1_interface,3);
    if (!strcmp(i, ext_foreign_toplevel_list_v1_interface.name)) {
        list = wl_registry_bind(r,n,&ext_foreign_toplevel_list_v1_interface,1);
        ext_foreign_toplevel_list_v1_add_listener(list,&list_listener,NULL);
    }
    if (!strcmp(i, ext_foreign_toplevel_image_capture_source_manager_v1_interface.name))
        sources = wl_registry_bind(r,n,&ext_foreign_toplevel_image_capture_source_manager_v1_interface,1);
    if (!strcmp(i, ext_image_copy_capture_manager_v1_interface.name))
        captures = wl_registry_bind(r,n,&ext_image_copy_capture_manager_v1_interface,1);
}
static void removed(void *d, struct wl_registry *r, uint32_t n) {}
static const struct wl_registry_listener registry_listener = {.global=global,.global_remove=removed};
static void buffer_size(void *d, struct ext_image_copy_capture_session_v1 *s, uint32_t w, uint32_t h) {width=w;height=h;}
static void shm_format(void *d, struct ext_image_copy_capture_session_v1 *s, uint32_t f) {
    if (f==WL_SHM_FORMAT_ARGB8888 || (f==WL_SHM_FORMAT_XRGB8888 && format==UINT32_MAX)) format=f;
}
static void device(void *d, struct ext_image_copy_capture_session_v1 *s, struct wl_array *a) {assert(a->size==sizeof(capture_device));memcpy(&capture_device,a->data,sizeof(capture_device));}
static void dmabuf_format(void *d, struct ext_image_copy_capture_session_v1 *s, uint32_t f, struct wl_array *a) {
    uint64_t *modifier;
    if(f==DRM_FORMAT_ARGB8888 || f==DRM_FORMAT_ABGR8888)
        wl_array_for_each(modifier,a) if(*modifier==DRM_FORMAT_MOD_LINEAR) dma_format=f;
}
static void session_done(void *d, struct ext_image_copy_capture_session_v1 *s) {constraints=true;}
static void stopped(void *d, struct ext_image_copy_capture_session_v1 *s) {failed=true;}
static const struct ext_image_copy_capture_session_v1_listener session_listener = {
    .buffer_size=buffer_size,.shm_format=shm_format,.dmabuf_device=device,.dmabuf_format=dmabuf_format,.done=session_done,.stopped=stopped,
};
static void transform(void *d, struct ext_image_copy_capture_frame_v1 *f, uint32_t t) {if(t!=WL_OUTPUT_TRANSFORM_NORMAL) failed=true;}
static void damage(void *d, struct ext_image_copy_capture_frame_v1 *f, int32_t x,int32_t y,int32_t w,int32_t h) {}
static void presentation(void *d, struct ext_image_copy_capture_frame_v1 *f, uint32_t h,uint32_t l,uint32_t n) {}
static void ready(void *d, struct ext_image_copy_capture_frame_v1 *f) {complete=true;}
static void frame_failed(void *d, struct ext_image_copy_capture_frame_v1 *f, uint32_t reason) {fprintf(stderr,"capture failed: %u\n",reason);failed=true;}
static const struct ext_image_copy_capture_frame_v1_listener frame_listener = {
    .transform=transform,.damage=damage,.presentation_time=presentation,.ready=ready,.failed=frame_failed,
};
int main(int argc,char **argv) {
    assert(argc==2 || argc==3);
    if(argc==3) target_name=argv[2];
    alarm(10);
    struct wl_display *display=wl_display_connect(NULL);
    assert(display);
    struct wl_registry *registry=wl_display_get_registry(display);
    wl_registry_add_listener(registry,&registry_listener,NULL);
    assert(wl_display_roundtrip(display)>=0);
    assert(wl_display_roundtrip(display)>=0);
    assert(shm && sources && captures);
    while(!target) assert(wl_display_dispatch(display)>=0);
    struct ext_image_capture_source_v1 *source=ext_foreign_toplevel_image_capture_source_manager_v1_create_source(sources,target);
    struct ext_image_copy_capture_session_v1 *session=ext_image_copy_capture_manager_v1_create_session(captures,source,0);
    ext_image_copy_capture_session_v1_add_listener(session,&session_listener,NULL);
    while(!constraints && !failed) assert(wl_display_dispatch(display)>=0);
    assert(!failed && width && height && width<16384 && height<16384);
    size_t size=(size_t)width*height*4;
    int fd=-1;
    void *pixels=NULL,*map_data=NULL;
    uint32_t stride=width*4;
    struct gbm_bo *bo=NULL;
    struct wl_buffer *buffer;
    if(format!=UINT32_MAX) {
        fd=memfd_create("rune-window-capture",MFD_CLOEXEC);
        assert(fd>=0 && ftruncate(fd,size)==0);
        pixels=mmap(NULL,size,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
        assert(pixels!=MAP_FAILED);
        struct wl_shm_pool *pool=wl_shm_create_pool(shm,fd,size);
        buffer=wl_shm_pool_create_buffer(pool,0,width,height,width*4,format);
    } else {
        fprintf(stderr,"DMA format: %x\n",dma_format);
        assert(dmabuf && dma_format);
        drmDevicePtr description=NULL;
        assert(drmGetDeviceFromDevId(capture_device,0,&description)==0);
        assert(description->available_nodes & (1<<DRM_NODE_RENDER));
        int gpu=open(description->nodes[DRM_NODE_RENDER],O_RDWR|O_CLOEXEC);
        drmFreeDevice(&description);
        assert(gpu>=0);
        struct gbm_device *device=gbm_create_device(gpu);
        assert(device);
        bo=gbm_bo_create(device,width,height,dma_format,GBM_BO_USE_LINEAR|GBM_BO_USE_RENDERING);
        assert(bo);
        struct zwp_linux_buffer_params_v1 *params=zwp_linux_dmabuf_v1_create_params(dmabuf);
        fd=gbm_bo_get_fd(bo);
        uint64_t modifier=gbm_bo_get_modifier(bo);
        zwp_linux_buffer_params_v1_add(params,fd,0,0,gbm_bo_get_stride(bo),modifier>>32,modifier&0xffffffff);
        buffer=zwp_linux_buffer_params_v1_create_immed(params,width,height,dma_format,0);
    }
    struct ext_image_copy_capture_frame_v1 *frame=ext_image_copy_capture_session_v1_create_frame(session);
    ext_image_copy_capture_frame_v1_add_listener(frame,&frame_listener,NULL);
    ext_image_copy_capture_frame_v1_attach_buffer(frame,buffer);
    ext_image_copy_capture_frame_v1_damage_buffer(frame,0,0,width,height);
    ext_image_copy_capture_frame_v1_capture(frame);
    while(!complete && !failed) assert(wl_display_dispatch(display)>=0);
    assert(!failed);
    if(bo) {
        pixels=gbm_bo_map(bo,0,0,width,height,GBM_BO_TRANSFER_READ,&stride,&map_data);
        assert(pixels);
    }
    if(format==WL_SHM_FORMAT_XRGB8888) for(size_t i=3;i<size;i+=4) ((uint8_t*)pixels)[i]=255;
    png_image image={.version=PNG_IMAGE_VERSION,.width=width,.height=height,.format=dma_format==DRM_FORMAT_ABGR8888 ? PNG_FORMAT_RGBA : PNG_FORMAT_BGRA};
    assert(png_image_write_to_file(&image,argv[1],0,pixels,stride,NULL));
    printf("Captured Wayland surface: %u x %u\n",width,height);
    if(bo) gbm_bo_unmap(bo,map_data); else munmap(pixels,size);
    close(fd);
    wl_display_disconnect(display);
}
