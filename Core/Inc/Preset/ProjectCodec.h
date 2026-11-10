/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef LXR_PROJECT_CODEC_H
#define LXR_PROJECT_CODEC_H

#include "Preset/ProjectStream.h"
#include "Soundengine/Sequencer/sequencer.h"

#define PROJECT_CODEC_GLOBAL_BYTES 30u
#define PROJECT_CODEC_HEADER_BYTES 36u
#define PROJECT_CODEC_PATTERN_BYTES (8u + NUM_TRACKS * NUM_STEPS * 8u + NUM_TRACKS * NUM_BARS * 2u + 1u + NUM_TRACKS + 2u)
#define PROJECT_CODEC_PAYLOAD_BYTES (8u + PROJECT_CODEC_GLOBAL_BYTES + 4u + NUM_KIT_SLOTS * (8u + END_OF_SOUND_PARAMETERS + PROJECT_CODEC_PATTERN_BYTES + 8u + MAX_SONG_LENGTH))
#define PROJECT_CODEC_FILE_BYTES (PROJECT_CODEC_HEADER_BYTES + PROJECT_CODEC_PAYLOAD_BYTES)

/* Borrowed project RAM, not an additional project-sized staging buffer.
 * names uses PresetManager's KIT, PATTERN, SONG, PROJECT order; only projectName
 * is used for the project name. Compressor values are threshold/ratio/attack/release.
 * Caller owns file lifetime, audio servicing, publication and edit-buffer capture.
 */
typedef struct {
    uint8_t (*kits)[END_OF_SOUND_PARAMETERS];
    PatternSet *patterns;
    uint8_t (*songs)[MAX_SONG_LENGTH];
    char (*names)[4][8];
    char *projectName;
    uint8_t *globals;
    uint8_t *compressor;
} ProjectCodecData;

/* Version 1 only; explicit LE integers and individual Step/timing fields.
 * Read validates header dimensions and exact file length before changing RAM.
 * A subsequent I/O failure can leave partially loaded RAM; no rollback is implied.
 * The caller supplies the length observed on the open file (f_size).
 */
FRESULT ProjectCodec_Write(ProjectStream *stream, const ProjectCodecData *data);
FRESULT ProjectCodec_Read(ProjectStream *stream, ProjectCodecData *data, uint32_t fileBytes);
#endif
