CC = gcc
CFLAGS = -Wall -Wextra -g -fsanitize=address
LDFLAGS = -fsanitize=address

SRC = src/cmap_parser.c src/stream_reader.c src/pdf_extract.c
OBJ = $(SRC:.c=.o)
TARGET = libpdfextract

all: $(TARGET)

$(TARGET): $(OBJ)
	$(CC) $(LDFLAGS) -o $@ $^

clean:
	rm -f $(OBJ) $(TARGET)

test: $(TARGET)
	./$(TARGET) test/sample.pdf

.PHONY: all clean test
