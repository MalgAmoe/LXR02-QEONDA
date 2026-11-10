/* SPDX-License-Identifier: GPL-3.0-only */
#include "Preset/ProjectStream.h"
#include <string.h>

static void init(ProjectStream *s, FIL *file, uint8_t writing)
{
    s->file = file;
    s->result = FR_OK;
    s->position = 0;
    s->used = 0;
    s->writing = writing;
    s->eof = 0;
}

void ProjectStream_InitRead(ProjectStream *s, FIL *file)
{
    init(s, file, 0);
}

void ProjectStream_InitWrite(ProjectStream *s, FIL *file)
{
    init(s, file, 1);
}

static FRESULT direction(ProjectStream *s, uint8_t writing)
{
    if (s->result == FR_OK && s->writing != writing)
        s->result = FR_INVALID_PARAMETER;
    return s->result;
}

FRESULT ProjectStream_Flush(ProjectStream *s)
{
    UINT done = 0;
    if (direction(s, 1) != FR_OK || s->used == 0)
        return s->result;
    s->result = f_write(s->file, s->buffer, (UINT)s->used, &done);
    if (s->result == FR_OK && done != s->used)
        s->result = FR_DISK_ERR;
    if (s->result == FR_OK)
        s->used = 0;
    return s->result;
}

FRESULT ProjectStream_Write(ProjectStream *s, const void *data, size_t size)
{
    const uint8_t *src = data;
    if (direction(s, 1) != FR_OK)
        return s->result;
    while (size) {
        size_t count = PROJECT_STREAM_BUFFER_SIZE - s->used;
        if (count > size) count = size;
        memcpy(s->buffer + s->used, src, count);
        s->used += count;
        src += count;
        size -= count;
        if (s->used == PROJECT_STREAM_BUFFER_SIZE && ProjectStream_Flush(s) != FR_OK)
            break;
    }
    return s->result;
}

FRESULT ProjectStream_Read(ProjectStream *s, void *data, size_t size)
{
    uint8_t *dst = data;
    if (direction(s, 0) != FR_OK)
        return s->result;
    while (size) {
        if (s->position == s->used) {
            UINT done = 0;
            if (s->eof) {
                s->result = FR_DISK_ERR;
                break;
            }
            s->result = f_read(s->file, s->buffer, PROJECT_STREAM_BUFFER_SIZE, &done);
            if (s->result != FR_OK) break;
            s->position = 0;
            s->used = done;
            s->eof = done < PROJECT_STREAM_BUFFER_SIZE;
            if (!done) {
                s->result = FR_DISK_ERR;
                break;
            }
        }
        size_t count = s->used - s->position;
        if (count > size) count = size;
        memcpy(dst, s->buffer + s->position, count);
        s->position += count;
        dst += count;
        size -= count;
    }
    return s->result;
}

FRESULT ProjectStream_ReadU8(ProjectStream *s, uint8_t *value)
{
    return ProjectStream_Read(s, value, 1);
}

FRESULT ProjectStream_ReadU16LE(ProjectStream *s, uint16_t *value)
{
    uint8_t bytes[2];
    if (ProjectStream_Read(s, bytes, sizeof bytes) == FR_OK)
        *value = (uint16_t)((uint16_t)bytes[0] | ((uint16_t)bytes[1] << 8));
    return s->result;
}

FRESULT ProjectStream_WriteU8(ProjectStream *s, uint8_t value)
{
    return ProjectStream_Write(s, &value, 1);
}

FRESULT ProjectStream_WriteU16LE(ProjectStream *s, uint16_t value)
{
    uint8_t bytes[2] = { (uint8_t)value, (uint8_t)(value >> 8) };
    return ProjectStream_Write(s, bytes, sizeof bytes);
}
