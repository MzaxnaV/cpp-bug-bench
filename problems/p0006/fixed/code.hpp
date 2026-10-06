#pragma once
#include <mutex>

// Running statistics. Safe to use from several threads at once.
class Stats {
public:
    void record(long value) {
        std::lock_guard<std::mutex> lock(m_);
        sum_ += value;
        ++count_;
    }

    // Mean of the recorded values, or 0 if there are none.
    double mean() const {
        std::lock_guard<std::mutex> lock(m_);
        if (count_ == 0) return 0.0;
        return static_cast<double>(sum_) / count_;
    }

private:
    mutable std::mutex m_;
    long sum_ = 0;
    long count_ = 0;
};
