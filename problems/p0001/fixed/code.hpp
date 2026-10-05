#pragma once
#include <cstddef>
#include <vector>

// Appends a copy of every element that satisfies pred to the end of v.
template <class T, class Pred>
void duplicate_if(std::vector<T>& v, Pred pred) {
    const std::size_t n = v.size();
    for (std::size_t i = 0; i < n; ++i)
        if (pred(v[i])) v.push_back(v[i]);
}
