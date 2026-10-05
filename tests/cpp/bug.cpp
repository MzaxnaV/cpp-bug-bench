#include <vector>

int main() 
{ 
    std::vector<int> v(3); 
    return v.data()[3]; // reads one past the end
}