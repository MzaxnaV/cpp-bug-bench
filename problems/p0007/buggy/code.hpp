#pragma once
#include <mutex>

// Holds one T, created on first use. get() is safe to call from several threads at once.
template <class T>
class Lazy {
public:
    Lazy() = default;
    Lazy(const Lazy&) = delete;
    Lazy& operator=(const Lazy&) = delete;
    ~Lazy() { delete ptr_; }

    T& get() {
        if (ptr_ == nullptr) {
            std::lock_guard<std::mutex> lock(m_);
            if (ptr_ == nullptr) ptr_ = new T();
        }
        return *ptr_;
    }

private:
    std::mutex m_;
    T* ptr_ = nullptr;
};
