#pragma once
#include <cstddef>
#include <vector>

// Removes every element of v that satisfies pred. Returns how many were removed.
template <class T, class Pred>
std::size_t erase_where(std::vector<T>& v, Pred pred) {
    std::size_t removed = 0;
    for (auto it = v.begin(); it != v.end();) {
        if (pred(*it)) {
            it = v.erase(it);
            ++removed;
        } else {
            ++it;
        }
    }
    return removed;
}
