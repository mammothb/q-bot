import re

def replace_multiple(replacement, string):
    """Replace multiple substrings in one pass
    https://stackoverflow.com/questions/6116978

    Keyword arguments:
    replacement -- various substrings and their replacements
    string -- the original string which contains the substrings that need
        replacing
    """
    replacement = dict((re.escape(key), val)
                       for key, val in replacement.items())
    pattern = re.compile("|".join(replacement.keys()))
    return pattern.sub(lambda m: replacement[re.escape(m.group(0))], string)

def try_parse_int64(string):
    try:
        ret = int(string)
    except ValueError:
        return None
    return None if ret < -2 ** 64 or ret >= 2 ** 64 else ret
