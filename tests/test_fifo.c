/*
 * test_fifo.c - tests for the byte FIFOs used by the MIDI UART (FIFO.c)
 *
 * Copyright (C) 2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */

#include "lxr_test.h"
#include "Soundengine/FIFO.h"

static void test_empty_fifo_returns_nothing(void)
{
	Fifo f;
	uint8_t b = 0xaa;
	fifo_init(&f);
	CHECK_EQ(fifo_bufferOut(&f, &b), 0);
	CHECK_EQ(b, 0xaa);
}

static void test_bytes_come_out_in_order(void)
{
	Fifo f;
	uint8_t b;
	fifo_init(&f);
	CHECK_EQ(fifo_bufferIn(&f, 0x90), 1);
	CHECK_EQ(fifo_bufferIn(&f, 0x3c), 1);
	CHECK_EQ(fifo_bufferIn(&f, 0x64), 1);
	CHECK_EQ(fifo_bufferOut(&f, &b), 1);
	CHECK_EQ(b, 0x90);
	CHECK_EQ(fifo_bufferOut(&f, &b), 1);
	CHECK_EQ(b, 0x3c);
	CHECK_EQ(fifo_bufferOut(&f, &b), 1);
	CHECK_EQ(b, 0x64);
	CHECK_EQ(fifo_bufferOut(&f, &b), 0);
}

// One slot is kept free to tell "full" from "empty".
static void test_holds_size_minus_one_bytes(void)
{
	Fifo f;
	uint8_t b;
	fifo_init(&f);
	for (int i = 0; i < BUFFER_SIZE - 1; i++)
		CHECK_EQ(fifo_bufferIn(&f, (uint8_t)i), 1);
	CHECK_EQ(fifo_bufferIn(&f, 0xff), 0);
	for (int i = 0; i < BUFFER_SIZE - 1; i++) {
		CHECK_EQ(fifo_bufferOut(&f, &b), 1);
		CHECK_EQ(b, (uint8_t)i);
	}
	CHECK_EQ(fifo_bufferOut(&f, &b), 0);
}

static void test_wraps_around(void)
{
	Fifo f;
	uint8_t b;
	fifo_init(&f);
	for (int i = 0; i < 3 * BUFFER_SIZE; i++) {
		CHECK_EQ(fifo_bufferIn(&f, (uint8_t)(i * 7)), 1);
		CHECK_EQ(fifo_bufferOut(&f, &b), 1);
		CHECK_EQ(b, (uint8_t)(i * 7));
	}
}

static void test_clear_discards_pending_bytes(void)
{
	Fifo f;
	uint8_t b;
	fifo_init(&f);
	fifo_bufferIn(&f, 1);
	fifo_bufferIn(&f, 2);
	fifo_clear(&f);
	CHECK_EQ(fifo_bufferOut(&f, &b), 0);
	CHECK_EQ(fifo_bufferIn(&f, 3), 1);
	CHECK_EQ(fifo_bufferOut(&f, &b), 1);
	CHECK_EQ(b, 3);
}

static void test_big_fifo(void)
{
	FifoBig f;
	uint8_t b;
	fifoBig_init(&f);
	for (int i = 0; i < BUFFER_SIZE_BIG - 1; i++)
		CHECK_EQ(fifoBig_bufferIn(&f, (uint8_t)i), 1);
	CHECK_EQ(fifoBig_bufferIn(&f, 0xff), 0);
	CHECK_EQ(fifoBig_bufferOut(&f, &b), 1);
	CHECK_EQ(b, 0);
	fifoBig_clear(&f);
	CHECK_EQ(fifoBig_bufferOut(&f, &b), 0);
}

int main(void)
{
	RUN_TEST(test_empty_fifo_returns_nothing);
	RUN_TEST(test_bytes_come_out_in_order);
	RUN_TEST(test_holds_size_minus_one_bytes);
	RUN_TEST(test_wraps_around);
	RUN_TEST(test_clear_discards_pending_bytes);
	RUN_TEST(test_big_fifo);
	return TEST_REPORT();
}
