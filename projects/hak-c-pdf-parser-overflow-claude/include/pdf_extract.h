#ifndef PDF_EXTRACT_H
#define PDF_EXTRACT_H

#define ERROR_OK 0
#define ERROR_CORRUPTED -1
#define ERROR_BUFFER_OVERFLOW -2
#define ERROR_UNSUPPORTED_ENCODING -3

int pdf_extract_text(const char *filepath, char **output, size_t *output_len);
void pdf_free(char *buffer);

#endif
