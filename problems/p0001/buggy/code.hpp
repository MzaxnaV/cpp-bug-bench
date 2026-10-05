#pragma once
#include <vector>

// Appends a copy of every element that satisfies pred to the end of v.
template <class T, class Pred>
void duplicate_if(std::vector<T>& v, Pred pred) {
    for (auto it = v.begin(), end = v.end(); it != end; ++it)
        if (pred(*it)) v.push_back(*it);
}
