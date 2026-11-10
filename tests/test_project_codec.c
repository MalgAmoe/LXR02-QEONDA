/* SPDX-License-Identifier: GPL-3.0-only */
#include "Preset/ProjectCodec.h"
#include "lxr_test.h"

static FIL file;
static ProjectStream stream;
static uint8_t media[PROJECT_CODEC_FILE_BYTES + 1];
static size_t cursor, length;
static unsigned reads, writes;
static FRESULT failure;
static PatternSet patterns;
static uint8_t kits[NUM_KIT_SLOTS][END_OF_SOUND_PARAMETERS];
static uint8_t songs[NUM_KIT_SLOTS][MAX_SONG_LENGTH], globals[30], compressor[4];
static char names[NUM_KIT_SLOTS][4][8], projectName[8];
static ProjectCodecData data = {kits, &patterns, songs, names, projectName, globals, compressor};

FRESULT f_read(FIL *fp, void *dst, UINT count, UINT *done)
{
    CHECK(fp == &file); reads++; *done = 0;
    if (failure != FR_OK) return failure;
    if (count > length - cursor) count = (UINT)(length - cursor);
    memcpy(dst, media + cursor, count); cursor += count; *done = count;
    return FR_OK;
}
FRESULT f_write(FIL *fp, const void *src, UINT count, UINT *done)
{
    CHECK(fp == &file); writes++; *done = 0;
    if (failure != FR_OK) return failure;
    CHECK(cursor + count <= sizeof media);
    memcpy(media + cursor, src, count); cursor += count; length = cursor; *done = count;
    return FR_OK;
}
static void fill(unsigned seed)
{
    for (unsigned i = 0; i < 30; ++i) globals[i] = (uint8_t)(seed + i);
    for (unsigned i = 0; i < 4; ++i) compressor[i] = (uint8_t)(seed + i * 17);
    for (unsigned i = 0; i < 8; ++i) projectName[i] = (char)(seed + i);
    for (unsigned p = 0; p < NUM_KIT_SLOTS; ++p) {
        for (unsigned k = 0; k < END_OF_SOUND_PARAMETERS; ++k) kits[p][k] = (uint8_t)(seed + p + k * 13);
        for (unsigned n = 0; n < MAX_SONG_LENGTH; ++n) songs[p][n] = (uint8_t)(seed + n + p);
        for (unsigned kind = 0; kind < 3; ++kind)
            for (unsigned n = 0; n < 8; ++n) names[p][kind][n] = (char)(seed + p + kind + n);
        patterns.shuffle[p] = (uint8_t)(seed + p);
        patterns.kitNr[p] = (uint8_t)p;
        patterns.used[p] = (uint8_t)(p & 1); /* silent-used must survive too */
        for (unsigned t = 0; t < NUM_TRACKS; ++t) {
            patterns.length[p][t] = (uint8_t)(seed + t + p);
            for (unsigned b = 0; b < NUM_BARS; ++b)
                patterns.seq_mainSteps[b][p][t] = (uint16_t)(seed + b * 0x101 + p * 17 + t);
            for (unsigned n = 0; n < NUM_STEPS; ++n) {
                unsigned v = seed + p * 19 + t * 7 + n;
                Step *s = &patterns.seq_subStepPattern[p][t][n];
                s->volume = v; s->prob = v + 1; s->note = v + 2;
                s->param1Nr = v + 3; s->param1Val = v + 4;
                s->param2Nr = v + 5; s->param2Val = v + 6;
                patterns.seq_stepTiming[p][t][n].flam = v & 15;
                patterns.seq_stepTiming[p][t][n].shift = (v >> 4) & 15;
            }
        }
    }
    for (unsigned b = 0; b < NUM_BARS; ++b)
        memset(patterns.seq_mainSteps[b][1], 0, sizeof patterns.seq_mainSteps[b][1]);
}
static FRESULT load(uint32_t size)
{
    cursor = 0; ProjectStream_InitRead(&stream, &file);
    return ProjectCodec_Read(&stream, &data, size);
}
static uint8_t encoded[PROJECT_CODEC_FILE_BYTES];
int main(void)
{
    CHECK_EQ(END_OF_SOUND_PARAMETERS, 247);
    CHECK_EQ(PROJECT_CODEC_FILE_BYTES, 255118);
    fill(37);
    ProjectStream_InitWrite(&stream, &file);
    CHECK_EQ(ProjectCodec_Write(&stream, &data), FR_OK);
    CHECK_EQ(length, PROJECT_CODEC_FILE_BYTES);
    CHECK_EQ(writes, (length + 4095) / 4096);
    CHECK(!memcmp(media, "QEONDAPR\1\0\44\0\100\0\7\0\100\0\4\0\367\0\100\0\36\0\10\0\7\0\1\0", 32));
    CHECK_EQ(media[32], PROJECT_CODEC_PAYLOAD_BYTES & 255);
    /* First step follows project/global/comp data, kit name/data, pattern name. */
    size_t first = 36 + 8 + 30 + 4 + 8 + 247 + 8;
    for (unsigned i = 0; i < 7; ++i) CHECK_EQ(media[first + i], 37 + i);
    size_t hits = first + NUM_TRACKS * NUM_STEPS * 8;
    CHECK_EQ(media[hits], 37); CHECK_EQ(media[hits + 1], 0);
    memcpy(encoded, media, sizeof encoded);
    fill(99);
    CHECK_EQ(load((uint32_t)length), FR_OK);
    CHECK_EQ(reads, (length + 4095) / 4096);
    /* Re-encode compares every meaningful field, not padding or ignored names. */
    cursor = 0; ProjectStream_InitWrite(&stream, &file);
    CHECK_EQ(ProjectCodec_Write(&stream, &data), FR_OK);
    CHECK(!memcmp(encoded, media, sizeof encoded));
    for (unsigned i = 0; i < 36; ++i) {
        media[i] ^= 1;
        globals[0] = 222;
        CHECK_EQ(load((uint32_t)length), FR_INVALID_PARAMETER);
        CHECK_EQ(globals[0], 222); /* reject before touching project RAM */
        media[i] ^= 1;
    }
    CHECK_EQ(load((uint32_t)length - 1), FR_INVALID_PARAMETER);
    CHECK_EQ(load((uint32_t)length + 1), FR_INVALID_PARAMETER);
    /* A short device read after a valid header is an I/O failure, not success. */
    length -= 19;
    CHECK_EQ(load(PROJECT_CODEC_FILE_BYTES), FR_DISK_ERR);
    length = PROJECT_CODEC_FILE_BYTES;
    failure = FR_NOT_READY;
    CHECK_EQ(load(PROJECT_CODEC_FILE_BYTES), FR_NOT_READY);
    cursor = 0; ProjectStream_InitWrite(&stream, &file);
    CHECK_EQ(ProjectCodec_Write(&stream, &data), FR_NOT_READY);
    return 0;
}
