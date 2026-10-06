#pragma once
#include <cstddef>

// Returns the number of fields in a comma-separated record of len bytes.
// The record is not null-terminated.
inline std::size_t count_fields(const char* data, std::size_t len) {
    std::size_t fields = 1;
    std::size_t i = 0;
    while (true) {
        while (data[i] != ',' && i < len) ++i;
        if (i == len) return fields;
        ++fields;
        ++i;
    }
}
