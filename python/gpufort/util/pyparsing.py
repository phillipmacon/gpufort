# SPDX-License-Identifier: MIT
# Copyright (c) 2020-2022 Advanced Micro Devices, Inc. All rights reserved.
import pyparsing
import re

def replace_all(f_snippet,
                ppexpression,
                repl=lambda parse_result: ("", False),
                strip_search_string=True):
    """Replaces all matches for the given pyparsing expression with
    the string generated by the 'repl' function argument, 
    which takes the pyparsing parse result into account.
    """
    matched = True
    transformed = False
    used_list = []
    while matched:
        matched = False
        for tokens, begin, end in ppexpression.scanString(f_snippet):
            parse_result = tokens[0]
            subst, changed = repl(parse_result)
            transformed |= changed
            if not begin in used_list:
                if changed:
                    search_string = f_snippet[begin:end]
                    if strip_search_string:
                        search_string = search_string.strip().strip(
                            "\n").strip()
                    f_snippet = f_snippet.replace(search_string, subst)
                else:
                    used_list.append(begin) # do not check this match again
                matched = True
                break
    return f_snippet, transformed


def replace_first(f_snippet,
                  ppexpression,
                  repl=lambda parse_result: ("", False),
                  strip_search_string=True):
    """Replaces the first match for the given pyparsing expression with
    the string generated by the 'repl' function argument, 
    which takes the pyparsing parse result into account.
    """
    transformed = False
    for tokens, begin, end in ppexpression.scanString(f_snippet):
        parse_result = tokens[0]
        subst, transformed = repl(parse_result)
        if transformed:
            search_string = f_snippet[begin:end]
            if strip_search_string:
                search_string = search_string.strip().strip("\n").strip()
            f_snippet = f_snippet.replace(search_string, subst)
        break
    return f_snippet, transformed


def erase_all(f_snippet, ppexpression, strip_search_string=True):
    """Removes all matches for the given pyparsing expression
    """
    matched = True
    transformed = False
    used_list = []
    while matched:
        matched = False
        for tokens, begin, end in ppexpression.scanString(f_snippet):
            if not begin in used_list:
                search_string = f_snippet[begin:end]
                if strip_search_string:
                    search_string = search_string.strip().strip("\n").strip()
                f_snippet = f_snippet.replace(search_string, "")
                matched = True
                break
            transformed |= matched
    return f_snippet, transformed


def erase_first(f_snippet, ppexpression, strip_search_string=True):
    """Replaces the first match for the given pyparsing expression with
    the string generated by the 'repl' function argument, 
    which takes the pyparsing parse result into account.
    """
    transformed = False
    for tokens, begin, end in ppexpression.scanString(f_snippet):
        search_string = f_snippet[begin:end]
        if strip_search_string:
            search_string = search_string.strip().strip("\n").strip()
        f_snippet = f_snippet.replace(search_string, "")
        transformed = True
        break
    return f_snippet, transformed