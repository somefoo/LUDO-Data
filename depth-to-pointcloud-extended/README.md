# depth-to-pointcloud
A simple tool to convert a linear depth image (z-depth) to a point cloud (OpenEXR to PCD)

# Requirements
* A compiler with basic C++20 support *(GCC 9.3.0 from the Ubuntu 20.04 repository works)*
* meson
* libopenexr-dev
* ninja
* That is pretty much it, other dependencies will be downloaded and compiled automatically by CMake/[Hunter](https://github.com/cpp-pm/hunter).

## Compile
``` bash
cd depth-to-pointcloud
meson setup build
cd build
ninja
```
## Application usage
```
depth-to-pointcloud - OpenEXR with Z Buffer to PCD point cloud converter.

Usage: depth-to-pointcloud --input [FILE1] --output [FILE2]
Reads FILE1 to generate a .pcd file FILE2

Options:
  --focal-length <float>[=<50>]     Pinhole-camera focal length
  --sensor-width  <float>[=<36>]    Pinhole-camera sensor size
  --upper-cut <float>[=<infinity>]  Cuts off points too far away
  --lower-cut <float>[=<-infinity>] Cuts off points too close
  --keep-fraction <float>[=<1.0>]   Percentage of points used
                                     has to be in [0,1]
  --add-noise <float>[=<0.0>]       Adds gaussian noise
                                     has to be in [0,infinity]
  --rgb <float>[=<4.2108e+06>]      Sets color of the points

 -h, --help                         Prints this message


Example 1:
./depth-to-pointcloud --input image.exr --output pointcloud.pcd

Example 2 (keep 50% of points, add noise with variance of 2.0):
./depth-to-pointcloud --input image.exr --output pointcloud.pcd \
  --sensor-width 10 --focal-length 42 --keep-fraction 0.5 --add-noise 2.0 \
  --lower-cut 100 --upper-cut 65500

Example 3 (output will default to image.pcd):
./depth-to-pointcloud --input image.exr

```

