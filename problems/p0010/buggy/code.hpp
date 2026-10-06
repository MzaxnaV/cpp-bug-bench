#pragma once
#include <climits>

// Returns a + b, clamped to [INT_MIN, INT_MAX] instead of overflowing.
inline int saturating_add(int a, int b) {
    if (b > 0 && a > INT_MAX - b) return INT_MAX;
    if (b < 0 && a < INT_MIN - b) return INT_MIN;
    return a + b;
}

// Returns the average of a and b, rounded toward negative infinity, for any two ints.
inline int floor_average(int a, int b) {
    return (a & b) + ((a ^ b) >> 1);
}
