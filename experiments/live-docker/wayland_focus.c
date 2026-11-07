#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <wayland-client.h>
#include "ext-foreign-toplevel-list.h"
#include "cosmic-toplevel-info.h"
#include "cosmic-toplevel-management.h"

/* Workspace requests are not used by this helper. */
const struct wl_interface zcosmic_workspace_handle_v1_interface={.name="zcosmic_workspace_handle_v1",.version=1};
const struct wl_interface ext_workspace_handle_v1_interface={.name="ext_workspace_handle_v1",.version=1};
static struct wl_seat *seat;
static struct zcosmic_toplevel_info_v1 *info;
static struct zcosmic_toplevel_manager_v1 *manager;
static struct ext_foreign_toplevel_handle_v1 *target;
static const char *target_name;
static bool active;
static void closed(void *d,struct ext_foreign_toplevel_handle_v1 *h){}
static void done(void *d,struct ext_foreign_toplevel_handle_v1 *h){}
static void identifier(void *d,struct ext_foreign_toplevel_handle_v1 *h,const char *s){}
static void name(void *d,struct ext_foreign_toplevel_handle_v1 *h,const char *s){if(!strcmp(s,target_name))target=h;}
static const struct ext_foreign_toplevel_handle_v1_listener top_listener={.closed=closed,.done=done,.title=name,.app_id=name,.identifier=identifier};
static void toplevel(void *d,struct ext_foreign_toplevel_list_v1 *l,struct ext_foreign_toplevel_handle_v1 *h){ext_foreign_toplevel_handle_v1_add_listener(h,&top_listener,NULL);}
static void finished(void *d,struct ext_foreign_toplevel_list_v1 *l){}
static const struct ext_foreign_toplevel_list_v1_listener list_listener={.toplevel=toplevel,.finished=finished};
static void capabilities(void *d,struct zcosmic_toplevel_manager_v1 *m,struct wl_array *a){}
static const struct zcosmic_toplevel_manager_v1_listener manager_listener={.capabilities=capabilities};
static void ignored_top(void *d,struct zcosmic_toplevel_info_v1 *i,struct zcosmic_toplevel_handle_v1 *h){}
static void info_finished(void *d,struct zcosmic_toplevel_info_v1 *i){}
static void info_done(void *d,struct zcosmic_toplevel_info_v1 *i){}
static const struct zcosmic_toplevel_info_v1_listener info_listener={.toplevel=ignored_top,.finished=info_finished,.done=info_done};
static void seat_caps(void *d,struct wl_seat *s,uint32_t c){}
static const struct wl_seat_listener seat_listener={.capabilities=seat_caps};
static void global(void *d,struct wl_registry *r,uint32_t n,const char *i,uint32_t v){
    if(!strcmp(i,wl_seat_interface.name)){seat=wl_registry_bind(r,n,&wl_seat_interface,1);wl_seat_add_listener(seat,&seat_listener,NULL);}
    if(!strcmp(i,zcosmic_toplevel_info_v1_interface.name)){info=wl_registry_bind(r,n,&zcosmic_toplevel_info_v1_interface,2);zcosmic_toplevel_info_v1_add_listener(info,&info_listener,NULL);}
    if(!strcmp(i,zcosmic_toplevel_manager_v1_interface.name)){manager=wl_registry_bind(r,n,&zcosmic_toplevel_manager_v1_interface,1);zcosmic_toplevel_manager_v1_add_listener(manager,&manager_listener,NULL);}
    if(!strcmp(i,ext_foreign_toplevel_list_v1_interface.name)){struct ext_foreign_toplevel_list_v1 *list=wl_registry_bind(r,n,&ext_foreign_toplevel_list_v1_interface,1);ext_foreign_toplevel_list_v1_add_listener(list,&list_listener,NULL);}
}
static void removed(void *d,struct wl_registry *r,uint32_t n){}
static const struct wl_registry_listener registry_listener={.global=global,.global_remove=removed};
static void handle_closed(void *d,struct zcosmic_toplevel_handle_v1 *h){}
static void handle_done(void *d,struct zcosmic_toplevel_handle_v1 *h){}
static void handle_name(void *d,struct zcosmic_toplevel_handle_v1 *h,const char *s){}
static void output(void *d,struct zcosmic_toplevel_handle_v1 *h,struct wl_output *o){}
static void workspace(void *d,struct zcosmic_toplevel_handle_v1 *h,struct zcosmic_workspace_handle_v1 *w){}
static void ext_workspace(void *d,struct zcosmic_toplevel_handle_v1 *h,struct ext_workspace_handle_v1 *w){}
static void geometry(void *d,struct zcosmic_toplevel_handle_v1 *h,struct wl_output *o,int32_t x,int32_t y,int32_t w,int32_t ht){}
static void state(void *d,struct zcosmic_toplevel_handle_v1 *h,struct wl_array *states){uint32_t *s;active=false;wl_array_for_each(s,states)if(*s==ZCOSMIC_TOPLEVEL_HANDLE_V1_STATE_ACTIVATED)active=true;}
static const struct zcosmic_toplevel_handle_v1_listener handle_listener={.closed=handle_closed,.done=handle_done,.title=handle_name,.app_id=handle_name,.output_enter=output,.output_leave=output,.workspace_enter=workspace,.workspace_leave=workspace,.state=state,.geometry=geometry,.ext_workspace_enter=ext_workspace,.ext_workspace_leave=ext_workspace};
int main(int argc,char **argv){
    assert(argc==2);target_name=argv[1];alarm(8);
    struct wl_display *display=wl_display_connect(NULL);assert(display);
    struct wl_registry *registry=wl_display_get_registry(display);wl_registry_add_listener(registry,&registry_listener,NULL);
    assert(wl_display_roundtrip(display)>=0);assert(wl_display_roundtrip(display)>=0);
    assert(info&&manager&&seat);
    while(!target)assert(wl_display_dispatch(display)>=0);
    struct zcosmic_toplevel_handle_v1 *handle=zcosmic_toplevel_info_v1_get_cosmic_toplevel(info,target);
    zcosmic_toplevel_handle_v1_add_listener(handle,&handle_listener,NULL);
    assert(wl_display_roundtrip(display)>=0);
    zcosmic_toplevel_manager_v1_activate(manager,handle,seat);
    assert(wl_display_roundtrip(display)>=0);
    while(!active)assert(wl_display_dispatch(display)>=0);
    puts("Owned Wayland window activated");wl_display_disconnect(display);
}
