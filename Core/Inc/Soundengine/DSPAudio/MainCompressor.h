#ifndef MAIN_COMPRESSOR_H
#define MAIN_COMPRESSOR_H
#include <stdint.h>
/* IDs 302..305: threshold, ratio, attack, release; invalid IDs ignored.
 * Targets are snapshotted once per render block. Pair uses int16-unit floats. */
/* Publish one complete preset target; preserves the caller's interrupt mask. */
void MainCompressor_setControls(const uint8_t controls[4]);
void MainCompressor_setParameter(uint16_t parameter, uint8_t value);
/* Nonzero while enabled OR draining the finite bypass ramp. Keep processing
 * pairs through that block; settled ratio1 returns zero and is exact bypass. */
unsigned MainCompressor_beginBlock(void);
void MainCompressor_processPair(float pair[2]);
#endif
