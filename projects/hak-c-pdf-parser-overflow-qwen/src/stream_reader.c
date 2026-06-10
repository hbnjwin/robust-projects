#include <stdio.h>
#include "../include/pdf_extract.h"

/* BUG: No bounds checking on xref table offsets.
 * Corrupted PDFs with invalid offsets cause fseek past EOF,
 * leading to reads of uninitialized memory. */
static int read_xref_table(FILE *fp, long offset) {
    fseek(fp, offset, SEEK_SET); /* FIXME: no bounds check */
    /* ... */
    (void)fp;
    return ERROR_OK;
}
