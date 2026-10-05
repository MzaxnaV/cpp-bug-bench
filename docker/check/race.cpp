#include <thread>

int n = 0;
int main() {
    std::thread t([]{ ++n; });
    ++n;
    t.join();
}
