#pragma once
#include <string>
#include <string_view>

// Returns the file name in path without its directories and extension.
// For example, "/var/log/app.log" gives "app".
inline std::string_view stem(std::string_view path) {
    std::string_view name = path.substr(path.find_last_of('/') + 1);
    name = name.substr(0, name.find('.'));
    return name;
}
