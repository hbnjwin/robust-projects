#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../include/pdf_extract.h"

/* BUG: Fixed 2-byte buffer assumes max 2-byte character encoding.
 * Adobe-Japan1 and other CJK charsets use up to 4-byte encodings,
 * causing buffer overflow when parsing CMap tables. */
static int parse_cmap_entry(const unsigned char *data, size_t len) {
    char buf[2]; /* FIXME: too small for 4-byte CJK encodings */
    /* ... parsing logic ... */
    (void)data; (void)len; (void)buf;
    return ERROR_OK;
}
