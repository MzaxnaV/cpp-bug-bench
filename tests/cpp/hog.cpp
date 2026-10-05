#include <vector>
#include <cstring>

int main() {
    std::vector<char*> v;
    for (;;) {
        char* p = new char[64 << 20];
        std::memset(p, 1, 64 << 20); v.push_back(p);
    }
}
