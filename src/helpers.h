#include <chrono>
#include <iostream>
#include <string>

static double GBpS(std::chrono::time_point<std::chrono::steady_clock> start, std::chrono::time_point<std::chrono::steady_clock> end, uint64_t bytes){
    auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(end-start).count();
    double Bpns = (double) bytes / (double) ns;
//    std::cout << bytes << '/' << ns << '\n';
    return Bpns;
}

struct Measurement{
public:
    std::chrono::time_point<std::chrono::steady_clock> start,end;
    std::string name;
    Measurement(const std::string& name):name(name){};
    void measureStart(){start = std::chrono::steady_clock::now();};
    void measureEnd(){end = std::chrono::steady_clock::now();};
    void printTime(){std::cout << name << ": " << std::chrono::duration_cast<std::chrono::nanoseconds>(end-start).count() << "ns \n";};
    void printTimeWithGBpS(uint64_t bytes){std::cout << name << ": " << std::chrono::duration_cast<std::chrono::nanoseconds>(end-start).count() << "ns, " 
        << GBpS(start, end, bytes) << "GB/s \n";};
};
