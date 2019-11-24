#!/bin/sh
./clean.sh
g++ -std=c++11 sdh.cpp -fPIC -shared -o libsdh.so
mkdir sdh-install
cp libsdh.so sdh-install/
strip -s sdh-install/libsdh.so
cp sdh.py sdh-install/
cp _sdh.py sdh-install/
gdb -nx -ex "source sdh-install/sdh.py" -ex quit
