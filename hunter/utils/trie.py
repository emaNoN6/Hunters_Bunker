#  ==========================================================
#  Hunter's Command Console
#  #
#  File: trie.py
#  Last Modified: 10/3/25, 9:49 PM
#  #
#  Copyright (c) 2025, M. Stilson & Codex
#  #
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the MIT License.
#  #
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  LICENSE file for more details.
#  ==========================================================
# !/usr/bin/python
# -*- coding: utf-8 -*-
#
# Original Perl module: Regexp::Trie
# Original Copyright (C) 2006 by Dan Kogai
#
# This Python translation is a derivative work based on Regexp::Trie
# Copyright (c) 2010 by rex
# Copyright (c) 2017 by fcicq, atiking and EricDuminil
# This Python code is licensed under the Artistic License 2.0 (AL2.0).
# A copy of the Artistic License 2.0 can be found at:
# https://opensource.org/licenses/Artistic-2.0

import re


class Trie:
	"""Regexp::Trie in python. Creates a Trie out of a list of words.
	The trie can be exported to a Regexp pattern.
	The corresponding Regexp should match much faster than a simple Regexp union."""

	def __init__(self):
		self.data = {}

	def add(self, word):
		"""Add a word to the trie."""
		ref = self.data
		for char in word:
			# Optimized: Use dict.setdefault instead of conditional
			ref = ref.setdefault(char, {})
		ref[''] = 1

	def dump(self):
		"""Return the internal trie structure."""
		return self.data

	@staticmethod
	def quote(char):
		"""Escape special regex characters."""
		return re.escape(char)

	def _pattern(self, pData):
		"""Recursively build the regex pattern from trie data."""
		# Base case: only terminator
		if "" in pData and len(pData) == 1:
			return None

		alt = []
		cc = []
		has_terminator = "" in pData

		# Process all non-terminator keys
		for char in sorted(pData.keys()):
			if char == "":
				continue

			child = pData[char]
			if isinstance(child, dict):
				recurse = self._pattern(child)
				if recurse is None:
					# Child is just a terminator, treat as single char
					cc.append(self.quote(char))
				else:
					alt.append(self.quote(char) + recurse)
		# Note: else case removed as pData[char] should always be dict

		# Optimize character class handling
		if cc:
			if len(cc) == 1:
				alt.append(cc[0])
			else:
				alt.append('[' + ''.join(cc) + ']')

		# Build the result pattern
		if not alt:
			return None

		if len(alt) == 1:
			result = alt[0]
		else:
			result = "(?:" + "|".join(alt) + ")"

		# Make optional if there's a terminator and we have alternatives
		if has_terminator:
			if not cc or alt:
				result = "(?:%s)?" % result
			else:
				result += "?"

		return result

	def pattern(self):
		"""Generate the optimized regex pattern from the trie."""
		result = self._pattern(self.dump())
		return result if result else ""


if __name__ == '__main__':
	t = Trie()
	for w in ['foobar', 'foobah', 'fooxar', 'foozap', 'fooza']:
		t.add(w)
	print(t.pattern())
	# => "foo(?:ba[hr]|xar|zap?)"

	# Additional test cases
	print("\nAdditional tests:")

	t2 = Trie()
	for w in ['a', 'ab', 'abc']:
		t2.add(w)
	print(f"a, ab, abc: {t2.pattern()}")

	t3 = Trie()
	for w in ['test', 'testing', 'tester']:
		t3.add(w)
	print(f"test, testing, tester: {t3.pattern()}")