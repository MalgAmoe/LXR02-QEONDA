/* SPDX-License-Identifier: GPL-3.0-only */
#include "Preset/ProjectCodec.h"
#include <string.h>

/* Header: magic[8], twelve LE16 values, payload length LE32.
 * Values: version, header size, slots, tracks, steps, bars, kit parameters,
 * song length, globals, name length, step fields, timing bytes.
 */
static void header(uint8_t bytes[PROJECT_CODEC_HEADER_BYTES])
{
    const uint16_t dimensions[] = {1, PROJECT_CODEC_HEADER_BYTES, NUM_KIT_SLOTS,
        NUM_TRACKS, NUM_STEPS, NUM_BARS, END_OF_SOUND_PARAMETERS,
        MAX_SONG_LENGTH, PROJECT_CODEC_GLOBAL_BYTES, 8, 7, 1};
    memcpy(bytes, "QEONDAPR", 8);
    for (unsigned i = 0; i < sizeof dimensions / sizeof dimensions[0]; ++i) {
        bytes[8 + i * 2] = (uint8_t)dimensions[i];
        bytes[9 + i * 2] = (uint8_t)(dimensions[i] >> 8);
    }
    for (unsigned i = 0; i < 4; ++i)
        bytes[32 + i] = (uint8_t)(PROJECT_CODEC_PAYLOAD_BYTES >> (i * 8));
}

static FRESULT bytes(ProjectStream *s, void *data, size_t count, uint8_t writing)
{
    return writing ? ProjectStream_Write(s, data, count) : ProjectStream_Read(s, data, count);
}

static FRESULT body(ProjectStream *s, const ProjectCodecData *d, uint8_t writing)
{
#define BYTES(ptr, count) do { if (bytes(s, (ptr), (count), writing) != FR_OK) return s->result; } while (0)
    BYTES(d->projectName, 8);
    BYTES(d->globals, PROJECT_CODEC_GLOBAL_BYTES);
    BYTES(d->compressor, 4);
    for (unsigned p = 0; p < NUM_KIT_SLOTS; ++p) {
        BYTES(d->names[p][0], 8);
        BYTES(d->kits[p], END_OF_SOUND_PARAMETERS);
        BYTES(d->names[p][1], 8);
        for (unsigned t = 0; t < NUM_TRACKS; ++t) {
            for (unsigned n = 0; n < NUM_STEPS; ++n) {
                Step *step = &d->patterns->seq_subStepPattern[p][t][n];
                /* Never serialize sizeof(Step): layout/padding is not the format. */
                uint8_t fields[7];
                if (writing) {
                    fields[0] = step->volume; fields[1] = step->prob;
                    fields[2] = step->note; fields[3] = step->param1Nr;
                    fields[4] = step->param1Val; fields[5] = step->param2Nr;
                    fields[6] = step->param2Val;
                }
                BYTES(fields, sizeof fields);
                if (!writing) {
                    step->volume = fields[0]; step->prob = fields[1];
                    step->note = fields[2]; step->param1Nr = fields[3];
                    step->param1Val = fields[4]; step->param2Nr = fields[5];
                    step->param2Val = fields[6];
                }
            }
            for (unsigned n = 0; n < NUM_STEPS; ++n) {
                StepTiming *timing = &d->patterns->seq_stepTiming[p][t][n];
                uint8_t value = 0;
                if (writing) value = (uint8_t)(timing->flam | (timing->shift << 4));
                BYTES(&value, 1);
                if (!writing) { timing->flam = value & 15; timing->shift = value >> 4; }
            }
        }
        for (unsigned t = 0; t < NUM_TRACKS; ++t) {
            for (unsigned b = 0; b < NUM_BARS; ++b) {
                uint16_t *hits = &d->patterns->seq_mainSteps[b][p][t];
                FRESULT result = writing ? ProjectStream_WriteU16LE(s, *hits) : ProjectStream_ReadU16LE(s, hits);
                if (result != FR_OK) return result;
            }
        }
        BYTES(&d->patterns->shuffle[p], 1);
        BYTES(d->patterns->length[p], NUM_TRACKS);
        BYTES(&d->patterns->kitNr[p], 1);
        BYTES(&d->patterns->used[p], 1);
        BYTES(d->names[p][2], 8);
        BYTES(d->songs[p], MAX_SONG_LENGTH);
    }
#undef BYTES
    return s->result;
}

FRESULT ProjectCodec_Write(ProjectStream *s, const ProjectCodecData *d)
{
    uint8_t expected[PROJECT_CODEC_HEADER_BYTES];
    header(expected);
    if (ProjectStream_Write(s, expected, sizeof expected) != FR_OK) return s->result;
    if (body(s, d, 1) != FR_OK) return s->result;
    return ProjectStream_Flush(s);
}

FRESULT ProjectCodec_Read(ProjectStream *s, ProjectCodecData *d, uint32_t fileBytes)
{
    uint8_t expected[PROJECT_CODEC_HEADER_BYTES], actual[PROJECT_CODEC_HEADER_BYTES];
    header(expected);
    if (fileBytes != PROJECT_CODEC_FILE_BYTES) return FR_INVALID_PARAMETER;
    if (ProjectStream_Read(s, actual, sizeof actual) != FR_OK) return s->result;
    if (memcmp(actual, expected, sizeof actual)) return FR_INVALID_PARAMETER;
    return body(s, d, 0);
}
