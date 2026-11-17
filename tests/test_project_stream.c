/* SPDX-License-Identifier: GPL-3.0-only */
#include "Preset/ProjectStream.h"
#include "lxr_test.h"

static FIL file;
static ProjectStream stream;
static uint8_t media[16384], input[10003], output[10003];
static size_t length, cursor;
static unsigned reads, writes;
static FRESULT failure;
static int short_write;

static void reset(void)
{
    length = cursor = reads = writes = 0;
    failure = FR_OK;
    short_write = 0;
}

FRESULT f_read(FIL *fp, void *data, UINT size, UINT *done)
{
    CHECK(fp == &file);
    reads++;
    *done = 0;
    if (failure != FR_OK) return failure;
    if (size > length - cursor) size = (UINT)(length - cursor);
    memcpy(data, media + cursor, size);
    cursor += size;
    *done = size;
    return FR_OK;
}

FRESULT f_write(FIL *fp, const void *data, UINT size, UINT *done)
{
    CHECK(fp == &file);
    writes++;
    *done = 0;
    if (failure != FR_OK) return failure;
    if (short_write && size) size--;
    CHECK(cursor + size <= sizeof media);
    memcpy(media + cursor, data, size);
    cursor += size;
    length = cursor;
    *done = size;
    return FR_OK;
}

static void roundtrip(void)
{
    reset();
    for (size_t i = 0; i < sizeof input; i++) input[i] = (uint8_t)(i * 37);
    ProjectStream_InitWrite(&stream, &file);
    CHECK_EQ(ProjectStream_Write(&stream, NULL, 0), FR_OK);
    for (size_t i = 0; i < sizeof input; i++)
        CHECK_EQ(ProjectStream_WriteU8(&stream, input[i]), FR_OK);
    CHECK_EQ(writes, 2);
    CHECK_EQ(length, 8192);
    CHECK_EQ(ProjectStream_Flush(&stream), FR_OK);
    CHECK_EQ(writes, 3);
    CHECK_EQ(length, sizeof input);
    CHECK_EQ(ProjectStream_Flush(&stream), FR_OK);
    CHECK_EQ(writes, 3);
    cursor = 0;
    ProjectStream_InitRead(&stream, &file);
    CHECK_EQ(ProjectStream_Read(&stream, NULL, 0), FR_OK);
    for (size_t i = 0; i < sizeof output; i++)
        CHECK_EQ(ProjectStream_ReadU8(&stream, &output[i]), FR_OK);
    CHECK_EQ(reads, 3);
    CHECK_MEM_EQ(output, input, sizeof input);
    CHECK_EQ(ProjectStream_Read(&stream, output, 1), FR_DISK_ERR);
    CHECK_EQ(ProjectStream_Read(&stream, output, 1), FR_DISK_ERR);
    CHECK_EQ(reads, 3);

    reset();
    ProjectStream_InitWrite(&stream, &file);
    CHECK_EQ(ProjectStream_Write(&stream, input, sizeof input), FR_OK);
    CHECK_EQ(ProjectStream_Flush(&stream), FR_OK);
    cursor = 0;
    ProjectStream_InitRead(&stream, &file);
    CHECK_EQ(ProjectStream_Read(&stream, output, sizeof output), FR_OK);
    CHECK_MEM_EQ(output, input, sizeof input);
    CHECK_EQ(reads, 3);
    CHECK_EQ(writes, 3);
}

static void errors(void)
{
    reset();
    ProjectStream_InitRead(&stream, &file);
    CHECK_EQ(ProjectStream_Read(&stream, output, 1), FR_DISK_ERR);
    CHECK_EQ(reads, 1);
    reset();
    length = 1;
    ProjectStream_InitRead(&stream, &file);
    CHECK_EQ(ProjectStream_Read(&stream, output, 2), FR_DISK_ERR);
    CHECK_EQ(reads, 1);

    reset();
    failure = FR_NOT_READY;
    ProjectStream_InitRead(&stream, &file);
    CHECK_EQ(ProjectStream_Read(&stream, output, 1), FR_NOT_READY);
    failure = FR_OK;
    CHECK_EQ(ProjectStream_Read(&stream, output, 1), FR_NOT_READY);
    CHECK_EQ(reads, 1);

    for (int full = 0; full < 2; full++) {
        for (int underlying = 0; underlying < 2; underlying++) {
            reset();
            short_write = !underlying;
            failure = underlying ? FR_WRITE_PROTECTED : FR_OK;
            FRESULT expected = underlying ? FR_WRITE_PROTECTED : FR_DISK_ERR;
            ProjectStream_InitWrite(&stream, &file);
            CHECK_EQ(ProjectStream_Write(&stream, input, full ? sizeof input : 3),
                     full ? expected : FR_OK);
            CHECK_EQ(ProjectStream_Flush(&stream), expected);
            failure = FR_OK;
            short_write = 0;
            CHECK_EQ(ProjectStream_WriteU8(&stream, 1), expected);
            CHECK_EQ(ProjectStream_Flush(&stream), expected);
            CHECK_EQ(writes, 1);
        }
    }
    reset();
    ProjectStream_InitRead(&stream, &file);
    CHECK_EQ(ProjectStream_Flush(&stream), FR_INVALID_PARAMETER);
    CHECK_EQ(ProjectStream_Read(&stream, output, 1), FR_INVALID_PARAMETER);
    ProjectStream_InitWrite(&stream, &file);
    CHECK_EQ(ProjectStream_Read(&stream, output, 1), FR_INVALID_PARAMETER);
    CHECK_EQ(ProjectStream_WriteU8(&stream, 1), FR_INVALID_PARAMETER);
    CHECK_EQ(reads + writes, 0);
}

static void little_endian(void)
{
    uint16_t value = 0;
    reset();
    ProjectStream_InitWrite(&stream, &file);
    /* Put the two-byte value across a refill boundary. */
    CHECK_EQ(ProjectStream_Write(&stream, input, 4095), FR_OK);
    CHECK_EQ(ProjectStream_WriteU16LE(&stream, 0xab12), FR_OK);
    CHECK_EQ(ProjectStream_Flush(&stream), FR_OK);
    CHECK_EQ(media[4095], 0x12);
    CHECK_EQ(media[4096], 0xab);
    cursor = 0;
    ProjectStream_InitRead(&stream, &file);
    CHECK_EQ(ProjectStream_Read(&stream, output, 4095), FR_OK);
    CHECK_EQ(ProjectStream_ReadU16LE(&stream, &value), FR_OK);
    CHECK_EQ(value, 0xab12);
    CHECK_EQ(reads, 2);
    cursor = 4096;
    ProjectStream_InitRead(&stream, &file);
    CHECK_EQ(ProjectStream_ReadU16LE(&stream, &value), FR_DISK_ERR);
    CHECK_EQ(value, 0xab12);
}

int main(void)
{
    RUN_TEST(roundtrip);
    RUN_TEST(errors);
    RUN_TEST(little_endian);
    return TEST_REPORT();
}
