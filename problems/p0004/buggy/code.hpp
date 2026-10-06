#pragma once

// Returns the smallest x in [lo, hi) for which pred(x) is true, or hi if there is none.
// pred must be false for every x below some point and true from that point on.
template <class Pred>
int first_true(int lo, int hi, Pred pred) {
    while (lo < hi) {
        int mid = (lo + hi) / 2;
        if (pred(mid))
            hi = mid;
        else
            lo = mid + 1;
    }
    return lo;
}
