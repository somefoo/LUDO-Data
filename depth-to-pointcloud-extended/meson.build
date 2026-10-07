project('depth-to-pointcloud', 'cpp', 
  version: '1.0', 
  default_options: ['cpp_std=c++20']
)

# Set build type
buildtype = get_option('buildtype')
if buildtype == 'debug'
  add_project_arguments('-Og', language: 'cpp')
elif buildtype == 'release'
  add_project_arguments('-O3', language: 'cpp')
endif

# Dependency
openexr_dep = dependency('OpenEXR', required: true)

# Source files
executable(
  'depth-to-pointcloud',
  'src/main.cpp',
  dependencies: [openexr_dep]
)
