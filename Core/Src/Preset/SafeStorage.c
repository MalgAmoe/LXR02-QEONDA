/* SPDX-License-Identifier: GPL-3.0-only
 * Staged project saves, inspired by OpenElixir-02 v1.2; conservative recovery.
 * No claim of atomicity across arbitrary FAT metadata/card power failure.
 */
#include "Preset/SafeStorage.h"
#include <string.h>
#include <stdio.h>

#define STORAGE_PATH_SIZE 64
static FRESULT emptyPath(char *path, unsigned capacity)
{
    const unsigned base = strlen(path);
    if(base + 1 >= capacity) return FR_INVALID_NAME;
    for(;;)
    {
        DIR dir;
        FRESULT res = f_opendir(&dir, path);
        if(res != FR_OK) return res;
        for(;;)
        {
            FILINFO info;
            res = f_readdir(&dir, &info);
            if(res != FR_OK || !info.fname[0])
            {
                const FRESULT closed = f_closedir(&dir);
                return res != FR_OK ? res : closed;
            }
            if(info.fname[0] == '.') continue;
            unsigned nameLen = 0;
            while(nameLen < sizeof(info.fname) && info.fname[nameLen]) ++nameLen;
            if(nameLen == sizeof(info.fname) || base + 1 + nameLen >= capacity)
            {
                f_closedir(&dir);
                return FR_INVALID_NAME;
            }
            path[base] = '/';
            memcpy(path + base + 1, info.fname, nameLen + 1);
            if(info.fattrib & AM_DIR)
            {
                // _FS_LOCK=1: release the parent before opening a child.
                res = f_closedir(&dir);
                if(res == FR_OK) res = emptyPath(path, capacity);
                if(res == FR_OK) res = f_unlink(path);
                path[base] = 0;
                if(res != FR_OK) return res;
                break; // Reopen parent after recursion; ordinary files need no restart.
            }
            // FatFs advances the cursor before returning a filename. Unlink marks
            // that entry deleted without shifting others, and needs no lock slot.
            res = f_unlink(path);
            path[base] = 0;
            if(res != FR_OK)
            {
                f_closedir(&dir);
                return res;
            }
        }
    }
}
FRESULT storage_emptyDirectory(const char *folder)
{
    char path[STORAGE_PATH_SIZE];
    if(strlen(folder) >= sizeof(path)) return FR_INVALID_NAME;
    strcpy(path, folder);
    return emptyPath(path, sizeof(path));
}
FRESULT storage_removeDirectory(const char *folder)
{
    FILINFO info;
    FRESULT res = f_stat(folder, &info);
    if(res == FR_NO_FILE) return FR_OK;
    if(res != FR_OK) return res;
    if(!(info.fattrib & AM_DIR)) return FR_INVALID_NAME;
    res = storage_emptyDirectory(folder);
    return res == FR_OK ? f_unlink(folder) : res;
}
static FRESULT projectPaths(unsigned slot, char *current, char *next, char *old)
{
    if(slot >= 64) return FR_INVALID_NAME;
    sprintf(current, "/proj%02u", slot);
    sprintf(next, "/proj%02un", slot);
    sprintf(old, "/proj%02uo", slot);
    return FR_OK;
}
static FRESULT exists(const char *path, int *present)
{
    FILINFO info;
    FRESULT res = f_stat(path, &info);
    *present = res == FR_OK;
    if(res == FR_NO_FILE) return FR_OK;
    if(res == FR_OK && !(info.fattrib & AM_DIR)) return FR_INVALID_NAME;
    return res;
}
FRESULT storage_recoverProject(unsigned slot)
{
    char current[12], next[12], old[12];
    FRESULT res = projectPaths(slot, current, next, old);
    if(res != FR_OK) return res;
    int present;
    res = exists(current, &present);
    if(res != FR_OK || present) return res;
    res = exists(old, &present);
    if(res != FR_OK) return res;
    if(present) return f_rename(old, current); /* checked; keep staging intact */
    res = exists(next, &present);
    if(res != FR_OK) return res;
    /* No previous copy and unknown staging completeness: manual recovery needed. */
    return present ? FR_DENIED : FR_OK;
}
FRESULT storage_saveProject(unsigned slot, StorageProjectWriter writer, unsigned char *warning)
{
    char current[12], next[12], old[12];
    *warning = 0;
    FRESULT res = projectPaths(slot, current, next, old);
    if(res != FR_OK) return res;
    res = f_chdir("/");
    if(res != FR_OK) return res;
    res = storage_recoverProject(slot);
    if(res != FR_OK) return res; /* never clean up after unresolved recovery */
    int hasCurrent;
    res = exists(current, &hasCurrent);
    if(res != FR_OK) return res;
    if(hasCurrent)
    {
        res = storage_removeDirectory(next);
        if(res != FR_OK) return res;
        res = storage_removeDirectory(old);
        if(res != FR_OK) return res;
    }
    res = f_mkdir(next);
    if(res != FR_OK) return res;
    res = f_chdir(next);
    if(res != FR_OK) return res;
    res = writer();
    FRESULT back = f_chdir("/");
    if(res != FR_OK) return res; /* preserve partial staging for inspection */
    if(back != FR_OK) return back;
    if(hasCurrent)
    {
        res = f_rename(current, old);
        if(res != FR_OK) return res;
    }
    res = f_rename(next, current);
    if(res != FR_OK)
    {
        if(hasCurrent)
        {
            FRESULT rollback = f_rename(old, current);
            if(rollback != FR_OK) return rollback; /* preserve BOTH candidates */
        }
        return res; /* staging remains, whether rollback worked or not */
    }
    /* New project committed; cleanup failure must not be reported as save failure. */
    if(hasCurrent && storage_removeDirectory(old) != FR_OK) *warning = 1;
    return FR_OK;
}
