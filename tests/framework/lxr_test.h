/*
 * lxr_test.h - minimal unit-test helpers for the host tests
 *
 * Copyright (C) 2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 *
 * Each test program is one .c file:
 *
 *   #include "lxr_test.h"
 *
 *   static void test_something(void)
 *   {
 *       CHECK(1 + 1 == 2);
 *       CHECK_EQ(fifo_bufferOut(&f, &b), 1);
 *   }
 *
 *   int main(void)
 *   {
 *       RUN_TEST(test_something);
 *       return TEST_REPORT();
 *   }
 *
 * A failed check prints file, line and the values and lets the test carry on,
 * so one run shows every failure. The program's exit code is non-zero if any
 * check failed, which is what CTest looks at.
 */

#ifndef LXR_TEST_H
#define LXR_TEST_H

#include <stdio.h>
#include <string.h>

static int lxr_test_checks;
static int lxr_test_failures;
static const char *lxr_test_current = "";

#define CHECK(cond)                                                              \
	do {                                                                         \
		lxr_test_checks++;                                                       \
		if (!(cond)) {                                                           \
			lxr_test_failures++;                                                 \
			printf("%s:%d: %s: CHECK(%s) failed\n", __FILE__, __LINE__,          \
			       lxr_test_current, #cond);                                     \
		}                                                                        \
	} while (0)

/* Compares two integer values (any integer type) and prints both on failure. */
#define CHECK_EQ(actual, expected)                                               \
	do {                                                                         \
		const long long lxr_a_ = (long long)(actual);                            \
		const long long lxr_e_ = (long long)(expected);                          \
		lxr_test_checks++;                                                       \
		if (lxr_a_ != lxr_e_) {                                                  \
			lxr_test_failures++;                                                 \
			printf("%s:%d: %s: CHECK_EQ(%s, %s) failed: got %lld, expected %lld\n", \
			       __FILE__, __LINE__, lxr_test_current, #actual, #expected,     \
			       lxr_a_, lxr_e_);                                              \
		}                                                                        \
	} while (0)

/* Compares two byte buffers of length n. */
#define CHECK_MEM_EQ(actual, expected, n)                                        \
	do {                                                                         \
		lxr_test_checks++;                                                       \
		if (memcmp((actual), (expected), (n)) != 0) {                            \
			lxr_test_failures++;                                                 \
			printf("%s:%d: %s: CHECK_MEM_EQ(%s, %s, %s) failed\n", __FILE__,     \
			       __LINE__, lxr_test_current, #actual, #expected, #n);          \
		}                                                                        \
	} while (0)

#define RUN_TEST(fn)                                                             \
	do {                                                                         \
		lxr_test_current = #fn;                                                  \
		fn();                                                                    \
	} while (0)

#define TEST_REPORT()                                                            \
	(printf("%d checks, %d failed\n", lxr_test_checks, lxr_test_failures),       \
	 lxr_test_failures ? 1 : 0)

#endif /* LXR_TEST_H */
