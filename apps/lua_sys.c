/* sys: two small extras for Lua on riscv-pico, compiled into the lua binary.
 *
 * Stock Lua has no way to sleep. On this machine a busy-wait pins the only CPU, and shelling out to
 * `sleep` from Lua needs fork(), which a no-MMU kernel doesn't have. This adds:
 *
 *   sys.sleep(seconds)   blocks without spinning; fractions are fine, e.g. sys.sleep(0.2)
 *   sys.ms()             milliseconds since boot as an integer, for timing loops
 *
 * Lua itself is left unmodified. lua.c is compiled with -DluaL_openlibs=pico_openlibs, which
 * renames its single call to the standard-library loader; pico_openlibs below loads the standard
 * libraries and then this one. This file is compiled without that define, so its own call reaches
 * the real luaL_openlibs. Build recipe is in PLAN.md's "apps/" section. */

#include <errno.h>
#include <time.h>

#include "lua.h"
#include "lauxlib.h"
#include "lualib.h"

void pico_openlibs(lua_State *L);

static int sys_sleep(lua_State *L)
{
    lua_Number s = luaL_checknumber(L, 1);
    struct timespec ts;

    if (s < 0)
        s = 0;
    ts.tv_sec = (time_t)s;
    ts.tv_nsec = (long)((s - (lua_Number)ts.tv_sec) * 1000000000.0);
    while (nanosleep(&ts, &ts) == -1 && errno == EINTR)
        ;
    return 0;
}

/* Integer milliseconds, not float seconds: with LUA_32BITS a Lua number is a 32-bit float, which
 * loses millisecond precision after a few hours of uptime. A 32-bit integer wraps after ~24 days. */
static int sys_ms(lua_State *L)
{
    struct timespec ts;

    clock_gettime(CLOCK_MONOTONIC, &ts);
    lua_pushinteger(L, (lua_Integer)(ts.tv_sec * 1000 + ts.tv_nsec / 1000000));
    return 1;
}

static const luaL_Reg sys_funcs[] = {
    {"sleep", sys_sleep},
    {"ms", sys_ms},
    {NULL, NULL}
};

int luaopen_sys(lua_State *L)
{
    luaL_newlib(L, sys_funcs);
    return 1;
}

void pico_openlibs(lua_State *L)
{
    luaL_openlibs(L);
    luaL_requiref(L, "sys", luaopen_sys, 1);
    lua_pop(L, 1);
}
