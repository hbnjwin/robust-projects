CC = gcc
CFLAGS = -Wall -g -O2
TARGET = gateway

all: $(TARGET)

$(TARGET): main.o
	$(CC) -o $@ $^

clean:
	rm -f $(TARGET) *.o
