/*
 * test_euklid.c - tests for the Euclidean pattern generator (EuklidGenerator.c)
 *
 * Copyright (C) 2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */

#include "lxr_test.h"
#include "Soundengine/Sequencer/EuklidGenerator.h"
#include "Soundengine/Sequencer/sequencer.h"

// Defined in sequencer.c, which isn't part of this test.
PatternSet seq_patternSet;

enum { TRACK = 2, PATTERN = 5 };

// The generated main steps of TRACK in PATTERN as one 64-bit word, bit n = step n.
static uint64_t generatedSteps(void)
{
	uint64_t steps = 0;
	for (int bar = 0; bar < NUM_BARS; bar++)
		steps |= (uint64_t)seq_patternSet.seq_mainSteps[bar][PATTERN][TRACK] << (16 * bar);
	return steps;
}

static uint64_t generate(uint8_t length, uint8_t steps, uint8_t rotation)
{
	memset(&seq_patternSet, 0, sizeof seq_patternSet);
	euklid_init();
	euklid_setLength(TRACK, length);
	euklid_setRotation(TRACK, rotation, PATTERN);
	euklid_setSteps(TRACK, steps, PATTERN);
	return generatedSteps();
}

static uint64_t fromString(const char *s)	// "x..x" -> step 0 is the first character
{
	uint64_t r = 0;
	for (int i = 0; s[i]; i++)
		if (s[i] == 'x')
			r |= (uint64_t)1 << i;
	return r;
}

static void test_known_patterns(void)
{
	CHECK_EQ(generate(16, 4, 0), fromString("x...x...x...x..."));
	CHECK_EQ(generate(8, 3, 0), fromString("x..x..x."));
	CHECK_EQ(generate(5, 5, 0), fromString("xxxxx"));
	CHECK_EQ(generate(1, 1, 0), fromString("x"));
}

// Every length 1-16 and step count 1-length: the right number of hits, all
// inside the track, first step a hit, and gaps between hits that differ by at
// most one step (that is what makes a pattern Euclidean).
static void test_hits_are_evenly_spread(void)
{
	for (int length = 1; length <= 16; length++) {
		for (int steps = 1; steps <= length; steps++) {
			const uint64_t p = generate((uint8_t)length, (uint8_t)steps, 0);
			CHECK_EQ(__builtin_popcountll(p), steps);
			CHECK_EQ(p >> length, 0);
			CHECK(p & 1);

			int minGap = 64, maxGap = 0, last = -1, first = -1;
			for (int i = 0; i < length; i++) {
				if (!(p & ((uint64_t)1 << i)))
					continue;
				if (last >= 0) {
					const int gap = i - last;
					minGap = gap < minGap ? gap : minGap;
					maxGap = gap > maxGap ? gap : maxGap;
				} else {
					first = i;
				}
				last = i;
			}
			const int wrapGap = length - last + first;
			minGap = wrapGap < minGap ? wrapGap : minGap;
			maxGap = wrapGap > maxGap ? wrapGap : maxGap;
			if (maxGap - minGap > 1)
				printf("  length %d steps %d: gaps %d..%d\n", length, steps, minGap, maxGap);
			CHECK(maxGap - minGap <= 1);
		}
	}
}

static void test_rotation_moves_hits_later(void)
{
	CHECK_EQ(generate(16, 4, 1), fromString(".x...x...x...x.."));
	CHECK_EQ(generate(8, 3, 2), fromString("x.x..x.."));
	// A full turn is no rotation.
	CHECK_EQ(generate(8, 3, 8), generate(8, 3, 0));
}

static void test_steps_are_limited_to_length(void)
{
	CHECK_EQ(generate(4, 9, 0), fromString("xxxx"));
	CHECK_EQ(euklid_getSteps(TRACK), 4);
	// 0 steps is turned into 1.
	CHECK_EQ(generate(4, 0, 0), fromString("x..."));
}

static void test_track_length_is_stored_in_the_pattern(void)
{
	generate(12, 5, 0);
	CHECK_EQ(seq_patternSet.length[PATTERN][TRACK], 12);
	// Other tracks and patterns are left alone.
	CHECK_EQ(seq_patternSet.length[PATTERN][TRACK + 1], 0);
	CHECK_EQ(seq_patternSet.length[PATTERN + 1][TRACK], 0);
}

int main(void)
{
	RUN_TEST(test_known_patterns);
	RUN_TEST(test_hits_are_evenly_spread);
	RUN_TEST(test_rotation_moves_hits_later);
	RUN_TEST(test_steps_are_limited_to_length);
	RUN_TEST(test_track_length_is_stored_in_the_pattern);
	return TEST_REPORT();
}
