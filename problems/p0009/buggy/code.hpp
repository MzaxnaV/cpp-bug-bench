#pragma once
#include <condition_variable>
#include <cstddef>
#include <deque>
#include <mutex>
#include <utility>

// A first-in first-out queue. Safe to use from several threads at once.
// pop() waits until an item is available.
template <class T>
class BlockingQueue {
public:
    void push(T value) {
        {
            std::lock_guard<std::mutex> lock(m_);
            items_.push_back(std::move(value));
        }
        ready_.notify_one();
    }

    T pop() {
        std::unique_lock<std::mutex> lock(m_);
        ready_.wait(lock, [this] { return !items_.empty(); });
        T value = std::move(items_.front());
        items_.pop_front();
        return value;
    }

    std::size_t size() const {
        std::lock_guard<std::mutex> lock(m_);
        return items_.size();
    }

private:
    mutable std::mutex m_;
    std::condition_variable ready_;
    std::deque<T> items_;
};
