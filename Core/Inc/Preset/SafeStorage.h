/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef LXR_SAFE_STORAGE_H
#define LXR_SAFE_STORAGE_H
#include "ff.h"
/* Directory cleanup always owns its workspace; never appends to caller memory. */
FRESULT storage_emptyDirectory(const char *folder);
FRESULT storage_removeDirectory(const char *folder);
/* Restore the previous committed directory if canonical is missing.
 * Never promote an unverified staging directory. Errors preserve candidates. */
FRESULT storage_recoverProject(unsigned slot);
typedef FRESULT (*StorageProjectWriter)(void);
FRESULT storage_saveProject(unsigned slot, StorageProjectWriter writeProject, unsigned char *cleanupWarning);
#endif
