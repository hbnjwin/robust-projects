#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    char *key;
    char *value;
} ConfigEntry;

typedef struct {
    ConfigEntry *entries;
    int count;
    int capacity;
} ConfigStore;

void config_init(ConfigStore *store) {
    store->entries = NULL; store->count = 0; store->capacity = 0;
}

void config_set(ConfigStore *store, const char *key, const char *value) {
    // BUG: memory leak - old value not freed when overwriting
    // BUG: key not copied, just pointer assigned
    if (store->count >= store->capacity) {
        store->capacity = store->capacity ? store->capacity * 2 : 16;
        store->entries = realloc(store->entries, store->capacity * sizeof(ConfigEntry));
    }
    store->entries[store->count].key = (char *)key;
    store->entries[store->count].value = strdup(value);
    store->count++;
}

int main() {
    ConfigStore store; config_init(&store);
    while (1) { config_set(&store, "heartbeat", "alive"); /* simulate running */ }
    return 0;
}
