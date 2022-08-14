// SPDX-License-Identifier: MIT
// Copyright (c) 2020-2022 Advanced Micro Devices, Inc. All rights reserved.
#include "auxiliary.h"

#include <iostream>

int gpufortrt::internal::LOG_LEVEL = 0;

void gpufortrt::internal::set_from_environment(int& variable,const char* env_var) {
  char* val = getenv(env_var);
  if ( val != nullptr ) {
    variable = std::stoi(val);
  }
}

void gpufortrt::internal::set_from_environment(size_t& variable,const char* env_var) {
  char* val = getenv(env_var);
  if ( val != nullptr ) {
    variable = std::stol(val);
  }
}

void gpufortrt::internal::set_from_environment(double& variable,const char* env_var) {
  char* val = getenv(env_var);
  if ( val != nullptr ) {
    variable = std::stod(val);
  }
}
    
void gpufortrt::internal::log_info(const int level,const std::string& msg) {
  std::cerr << "[gpufortrt][" << level << "] " << msg << std::endl;
}

void gpufortrt::internal::log_error(const std::string& msg) {
  std::cerr << "[gpufortrt] ERROR: " << msg << std::endl;
  std::terminate();
}
