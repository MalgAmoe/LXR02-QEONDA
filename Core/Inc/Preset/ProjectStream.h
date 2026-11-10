/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef LXR_PROJECT_STREAM_H
#define LXR_PROJECT_STREAM_H

#include <stddef.h>
#include <stdint.h>
#include "ff.h"

#define PROJECT_STREAM_BUFFER_SIZE 4096u

/* Caller owns both this object (prefer static storage) and the open FIL.
 * One direction per initialization; no seek, close, sync or publication here.
 * Do not access the FIL independently while buffered data remains.
 */
typedef struct {
    FIL *file;
    FRESULT result;
    size_t position;
    size_t used;
    uint8_t writing;
    uint8_t eof;
    uint8_t buffer[PROJECT_STREAM_BUFFER_SIZE];
} ProjectStream;

void ProjectStream_InitRead(ProjectStream *stream, FIL *file);
void ProjectStream_InitWrite(ProjectStream *stream, FIL *file);
/* Exact transfers. First error is sticky until reinitialization; no further I/O.
 * Short exact reads/writes become FR_DISK_ERR. On failure, a destination or
 * file may already be partially modified; no rollback or retry is performed.
 * Nonzero lengths require valid pointers; zero length permits NULL data.
 */
FRESULT ProjectStream_Read(ProjectStream *stream, void *data, size_t size);
FRESULT ProjectStream_Write(ProjectStream *stream, const void *data, size_t size);
/* Drain write tail only (not f_sync). Caller must flush before closing.
 * Wrong-direction operations latch FR_INVALID_PARAMETER.
 */
FRESULT ProjectStream_Flush(ProjectStream *stream);
FRESULT ProjectStream_ReadU8(ProjectStream *stream, uint8_t *value);
FRESULT ProjectStream_ReadU16LE(ProjectStream *stream, uint16_t *value);
FRESULT ProjectStream_WriteU8(ProjectStream *stream, uint8_t value);
FRESULT ProjectStream_WriteU16LE(ProjectStream *stream, uint16_t value);

#endif
