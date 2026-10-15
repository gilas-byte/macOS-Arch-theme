cmake_minimum_required(VERSION 3.20)
project(tahoecursor LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(QT_MAJOR_VERSION 6)
find_package(ECM REQUIRED NO_MODULE)
list(APPEND CMAKE_MODULE_PATH ${ECM_MODULE_PATH})

include(KDEInstallDirs)
include(KDECMakeSettings)
include(KDECompilerSettings NO_POLICY_SCOPE)

find_package(Qt6 REQUIRED COMPONENTS Core Gui Widgets Quick DBus)
find_package(KF6 REQUIRED COMPONENTS Config CoreAddons)
find_package(KWin REQUIRED)

set(CMAKE_AUTORCC ON)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)

kcoreaddons_add_plugin(tahoecursor INSTALL_NAMESPACE "kwin/effects/plugins")
target_sources(tahoecursor PRIVATE main.cpp tahoecursor.cpp tahoecursor.qrc)
target_link_libraries(tahoecursor PRIVATE KWin::kwin KF6::ConfigCore KF6::CoreAddons)
