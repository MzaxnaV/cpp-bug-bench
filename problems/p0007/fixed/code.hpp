#pragma once
#include <atomic>
#include <mutex>

// Holds one T, created on first use. get() is safe to call from several threads at once.
template <class T>
class Lazy {
public:
    Lazy() = default;
    Lazy(const Lazy&) = delete;
    Lazy& operator=(const Lazy&) = delete;
    ~Lazy() { delete ptr_.load(); }

    T& get() {
        T* p = ptr_.load(std::memory_order_acquire);
        if (p == nullptr) {
            std::lock_guard<std::mutex> lock(m_);
            p = ptr_.load(std::memory_order_relaxed);
            if (p == nullptr) {
                p = new T();
                ptr_.store(p, std::memory_order_release);
            }
        }
        return *p;
    }

private:
    std::mutex m_;
    std::atomic<T*> ptr_{nullptr};
};
