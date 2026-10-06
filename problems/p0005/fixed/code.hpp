#pragma once
#include <cstdint>

// Returns count bits of word starting at bit offset (bit 0 is the least significant).
// Requires offset + count <= 32.
inline std::uint32_t extract_bits(std::uint32_t word, unsigned offset, unsigned count) {
    if (count == 0) return 0;
    return (word >> offset) & (0xFFFFFFFFu >> (32 - count));
}
