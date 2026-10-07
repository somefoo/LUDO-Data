#include <ImfFrameBuffer.h>
#include <ImfPixelType.h>
#include <OpenEXR/ImfArray.h>
#include <OpenEXR/ImfChannelList.h>
#include <OpenEXR/ImfInputFile.h>
#include <OpenEXR/ImfRgbaFile.h>
#include <OpenEXR/OpenEXRConfig.h>

#include <array>
#include <cstddef>
#include <fstream>
#include <iostream>
#include <limits>
#include <ostream>
#include <random>

#include "input_parser.hpp"

// Variables which can be set
static float upper_cut = std::numeric_limits<float>::infinity();
static float lower_cut = -std::numeric_limits<float>::infinity();
static float keep_fraction = 1.0;
static float variance = 0.0;

static float sensor_width = 4.0f;  // mm diagonal
static float focal_length = 2.8f;  // mm
static float rgb = 4.2108e+06;

// Ye, this ain't gonna win performance awards!
const std::array<float, 3> get_transformed(
    const Imf::Array2D<float> &depth_pixels, const int x, const int y, const float noise) {
  const float aspect_ratio =
      static_cast<float>(depth_pixels.width()) / depth_pixels.height();

  const float sensor_height = sensor_width / aspect_ratio;

  const float x_position_on_sensor =
      sensor_width * static_cast<float>(x) / depth_pixels.width();
  const float y_position_on_sensor =
      sensor_height * static_cast<float>(y) / depth_pixels.height();

  const float centered_x_position_on_sensor =
      x_position_on_sensor - sensor_width / 2;
  const float centered_y_position_on_sensor =
      y_position_on_sensor - sensor_height / 2;
  const float z_sensor_position = -focal_length;

  std::array<float, 3> origin{centered_x_position_on_sensor,
                              -centered_y_position_on_sensor,
                              z_sensor_position};
  std::array<float, 3> focal_point{0, 0, 0};
  std::array<float, 3> direction{origin[0] - focal_point[0],
                                 origin[1] - focal_point[1],
                                 origin[2] - focal_point[2]};
#if 0  // This branch will not correct spherical distortion
  const float direction_length =
      std::sqrt(std::pow(direction[0], 2) + std::pow(direction[1], 2) +
                std::pow(direction[2], 2));
   direction[0] /= direction_length;
   direction[1] /= direction_length;
   direction[2] /= direction_length;
#else
  direction[0] /= focal_length;
  direction[1] /= focal_length;
  direction[2] /= focal_length;
#endif

  // We assume (0,0,0) to be the center of the camera (the focal point is at
  // this position)

  const float depth = depth_pixels[y][x] + noise;
  return {direction[0] * depth, direction[1] * depth, direction[2] * depth};
}

// See http://pointclouds.org/documentation/tutorials/pcd_file_format.html
void print_pcd(const Imf::Array2D<float> &r_pixels,
               const Imf::Array2D<float> &g_pixels,
               const Imf::Array2D<float> &b_pixels,
               const Imf::Array2D<float> &a_pixels,
               const Imf::Array2D<float> &z_pixels,
               std::ostream &ostream = std::cout) {
  std::random_device rd{};
  std::mt19937 gen{rd()};
  std::normal_distribution<> d{0, variance};
  std::uniform_real_distribution<> u{0.0, 1.0};

  std::ostringstream header_stream;
  std::ostringstream point_stream;

  std::size_t point_count = 0;

  for (std::size_t y = 0; y < z_pixels.height(); ++y) {
    for (std::size_t x = 0; x < z_pixels.width(); ++x) {
      float value = z_pixels[y][x];
      float alpha = a_pixels[y][x];
      bool is_inside =
          value < upper_cut && value > lower_cut;  // Within valid depth
      bool is_kept = u(gen) <= keep_fraction;
      bool is_visible = alpha > 0.0;

      if (is_inside && is_kept && is_visible) {
        float rgb_color = 0.0;
        unsigned char *argb = reinterpret_cast<unsigned char *>(&rgb_color);
        argb[2] = static_cast<unsigned char>(r_pixels[y][x] * 255);
        argb[1] = static_cast<unsigned char>(g_pixels[y][x] * 255);
        argb[0] = static_cast<unsigned char>(b_pixels[y][x] * 255);
        //argb[3] = 255;
        std::array<float, 3> position = get_transformed(z_pixels, x, y, d(gen));
        point_stream << position[0] << " " << position[1] << " " << position[2] << " " << rgb_color << '\n';
        point_count++;
      }
    }
  }

  header_stream << "# .PCD v.7 - Point Cloud Data file format\n";
  header_stream << "VERSION .7\n";
  header_stream << "FIELDS x y z rgb\n";
  header_stream << "SIZE 4 4 4 4\n";
  header_stream << "TYPE F F F F\n";
  header_stream << "COUNT 1 1 1 1\n";
  header_stream << "WIDTH " << point_count << '\n';
  header_stream << "HEIGHT 1\n";
  header_stream << "VIEWPOINT 0 0 0 1 0 0 0\n";
  header_stream << "POINTS " << point_count << '\n';
  header_stream << "DATA ascii\n";

  ostream << header_stream.str();
  ostream << point_stream.str();
  ostream.flush();
}

// Prints the help text
void print_help() {
  std::cout << "depth-to-pointcloud - OpenEXR with Z Buffer to CSV point "
               "cloud converter.\n";
  std::cout << '\n';
  std::cout << "Usage: depth-to-pointcloud --input [FILE1] --output [FILE2]\n";
  std::cout << "Reads FILE1 to generate a .pcd file FILE2\n";
  std::cout << '\n';

  std::cout << "Options: \n";
  std::cout
      << "  --focal-length <float>[=<50>]     Pinhole-camera focal length\n";
  std::cout
      << "  --sensor-width  <float>[=<36>]    Pinhole-camera sensor size\n";
  std::cout
      << "  --upper-cut <float>[=<infinity>]  Cuts off points too far away\n";
  std::cout
      << "  --lower-cut <float>[=<-infinity>] Cuts off points too close\n";
  std::cout
      << "  --keep-fraction <float>[=<1.0>]   Percentage of points used\n";
  std::cout << "                                     has to be in [0,1]\n";
  std::cout << "  --add-noise <float>[=<0.0>]       Adds gaussian noise\n";
  std::cout
      << "                                     has to be in [0,infinity]\n";
  std::cout << "  --rgb <float>[=<4.2108e+06>]      Sets color of the points\n";
  std::cout << '\n';
  std::cout << " -h, --help                         Prints this message\n";
  std::cout << '\n';
  std::cout << '\n';

  std::cout << "Example 1:\n";
  std::cout << "./depth-to-pointcloud --input image.exr --output "
               "pointcloud.pcd\n";
  std::cout << '\n';
  std::cout
      << "Example 2 (keep 50\% of points, add noise with variance of 2.0):\n";
  std::cout << "./depth-to-pointcloud --input image.exr --output "
               "pointcloud.pcd \\\n";
  std::cout << "  --sensor-width 10 --focal-length 42 --keep-fraction 0.5 "
               "--add-noise 2.0 \\\n";
  std::cout << "  --lower-cut 100 --upper-cut 65500 \n";
  std::cout << '\n';
  std::cout << "Example 3 (output will default to image.pcd):\n";
  std::cout << "./depth-to-pointcloud --input image.exr\n";
  std::cout << std::endl;
}

int main(int argc, char *argv[]) {
  // Do input parsing

  if (argc == 1 || parse_args_set(argc, argv, "-h") ||
      parse_args_set(argc, argv, "--help")) {
    print_help();
    exit(0);
  }

  const std::string input_path =
      parse_args<std::string>(argc, argv, "--input", "");
  if (input_path == "") {
    std::cerr << "Error, no input file given.\n";
    exit(1);
  }

  std::string output_path(input_path);
  output_path = output_path.substr(0, output_path.length() - 4) + ".pcd";
  output_path = parse_args<std::string>(argc, argv, "--output", output_path);

  sensor_width = parse_args<float>(argc, argv, "--sensor-width", sensor_width);
  focal_length = parse_args<float>(argc, argv, "--focal-length", focal_length);
  keep_fraction =
      parse_args<float>(argc, argv, "--keep-fraction", keep_fraction);
  variance = parse_args<float>(argc, argv, "--add-noise", variance);
  lower_cut = parse_args<float>(argc, argv, "--lower-cut", lower_cut);
  upper_cut = parse_args<float>(argc, argv, "--upper-cut", upper_cut);
  rgb = parse_args<float>(argc, argv, "--rgb", rgb);

  // Load the file
  Imf::InputFile file(input_path.c_str());
  const Imf::ChannelList &channels = file.header().channels();

  if (channels.findChannel("Z") == nullptr) {
    std::cerr << "Error, the image does not contain a Z Buffer.\n";
    exit(1);
  }

  Imath::Box2i dim = file.header().dataWindow();

  const int width = dim.max.x - dim.min.x + 1;
  const int height = dim.max.y - dim.min.y + 1;

  Imf::Array2D<float> r_pixels(height, width);
  Imf::Array2D<float> g_pixels(height, width);
  Imf::Array2D<float> b_pixels(height, width);
  Imf::Array2D<float> a_pixels(height, width);
  Imf::Array2D<float> z_pixels(height, width);
  const auto r_base_ptr =
      (char *)(&r_pixels[0][0] - dim.min.x - dim.min.y * width);
  const auto g_base_ptr =
      (char *)(&g_pixels[0][0] - dim.min.x - dim.min.y * width);
  const auto b_base_ptr =
      (char *)(&b_pixels[0][0] - dim.min.x - dim.min.y * width);
  const auto a_base_ptr =
      (char *)(&a_pixels[0][0] - dim.min.x - dim.min.y * width);
  const auto z_base_ptr =
      (char *)(&z_pixels[0][0] - dim.min.x - dim.min.y * width);
  const std::size_t x_stride = sizeof(z_pixels[0][0]);
  const std::size_t y_stride = sizeof(z_pixels[0][0]) * width;

  Imf::FrameBuffer frame_buffer;
  frame_buffer.insert(
      "R", Imf::Slice(Imf::FLOAT, r_base_ptr, x_stride, y_stride, 1, 1,
                      std::numeric_limits<float>::max()));
  frame_buffer.insert(
      "G", Imf::Slice(Imf::FLOAT, g_base_ptr, x_stride, y_stride, 1, 1,
                      std::numeric_limits<float>::max()));
  frame_buffer.insert(
      "B", Imf::Slice(Imf::FLOAT, b_base_ptr, x_stride, y_stride, 1, 1,
                      std::numeric_limits<float>::max()));
  frame_buffer.insert(
      "A", Imf::Slice(Imf::FLOAT, a_base_ptr, x_stride, y_stride, 1, 1,
                      std::numeric_limits<float>::max()));
  frame_buffer.insert(
      "Z", Imf::Slice(Imf::FLOAT, z_base_ptr, x_stride, y_stride, 1, 1,
                      std::numeric_limits<float>::max()));

  file.setFrameBuffer(frame_buffer);
  file.readPixels(dim.min.y, dim.max.y);

  // Create point cloud
  std::ofstream stream_pcd(output_path, std::ofstream::binary);
  print_pcd(r_pixels, g_pixels, b_pixels, a_pixels, z_pixels, stream_pcd);
}
