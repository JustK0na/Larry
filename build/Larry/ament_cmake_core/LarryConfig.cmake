# generated from ament/cmake/core/templates/nameConfig.cmake.in

# prevent multiple inclusion
if(_Larry_CONFIG_INCLUDED)
  # ensure to keep the found flag the same
  if(NOT DEFINED Larry_FOUND)
    # explicitly set it to FALSE, otherwise CMake will set it to TRUE
    set(Larry_FOUND FALSE)
  elseif(NOT Larry_FOUND)
    # use separate condition to avoid uninitialized variable warning
    set(Larry_FOUND FALSE)
  endif()
  return()
endif()
set(_Larry_CONFIG_INCLUDED TRUE)

# output package information
if(NOT Larry_FIND_QUIETLY)
  message(STATUS "Found Larry: 0.0.0 (${Larry_DIR})")
endif()

# warn when using a deprecated package
if(NOT "" STREQUAL "")
  set(_msg "Package 'Larry' is deprecated")
  # append custom deprecation text if available
  if(NOT "" STREQUAL "TRUE")
    set(_msg "${_msg} ()")
  endif()
  # optionally quiet the deprecation message
  if(NOT Larry_DEPRECATED_QUIET)
    message(DEPRECATION "${_msg}")
  endif()
endif()

# flag package as ament-based to distinguish it after being find_package()-ed
set(Larry_FOUND_AMENT_PACKAGE TRUE)

# include all config extra files
set(_extras "")
foreach(_extra ${_extras})
  include("${Larry_DIR}/${_extra}")
endforeach()
