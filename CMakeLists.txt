# CMakeのバージョンを設定
cmake_minimum_required(VERSION 3.20)
enable_language(CXX) # C++言語を有効化
set(CMAKE_CXX_STANDARD 14) # C++14...
set(CMAKE_CXX_STANDARD_REQUIRED ON) #...is required...
set(CMAKE_CXX_EXTENSIONS OFF) #...without compiler extensions like gnu++11
# コンパイラのフラグを設定
set(CCFLAGS "-g")
set(CFLAGS ${CCFLAGS})

# デバッグビルドのためのフラグを設定
option(Debug "Debug" OFF)

set(src_files
	main.cpp
)

# インクルードパスを設定
# set(INCLUDE_DIRS
#   ${CMAKE_SOURCE_DIR}/include
#   ${CMAKE_SOURCE_DIR}/src
# )
# include_directories(${INCLUDE_DIRS})

# ライブラリパスを設定
# set(LIBRARY_DIRS
#   ${CMAKE_SOURCE_DIR}/lib1
#   ${CMAKE_SOURCE_DIR}/lib2
# )
# link_directories(${LIBRARY_DIRS})

## Use the variable PROJECT_NAME for changing the target name
set(PROJECT_NAME "a.out")

# プロジェクト名を設定
project(${PROJECT_NAME})

# コンパイラの警告レベルを設定
# MSVCの場合は/W4を使用し、GNUコンパイラの場合は-Wall -Wextra -Wno-long-long -pedanticを使用
if(Debug)
    if(MSVC)
    # Force to always compile with W4
        if(CMAKE_CXX_FLAGS MATCHES "/W[0-4]")
            string(REGEX REPLACE "/W[0-4]" "/W4" CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${CFLAGS}")
        else()
            set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${CFLAGS} /W4")
        endif()
    elseif(CMAKE_COMPILER_IS_GNUCC OR CMAKE_COMPILER_IS_GNUCXX)
        # Update if necessary
        set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${CFLAGS} -Wall -Wextra -Wno-long-long -pedantic")
    endif()
else()
    if(MSVC)
    # Force to always compile with W4
        if(CMAKE_CXX_FLAGS MATCHES "/W[0-4]")
            string(REGEX REPLACE "/W[0-4]" "/W4" CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS}")
        else()
            set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} /W4")
        endif()
    elseif(CMAKE_COMPILER_IS_GNUCC OR CMAKE_COMPILER_IS_GNUCXX)
    # Update if necessary
        set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -Wextra -Wno-long-long -pedantic")
    endif()
endif()

# Adds an executable target named 'test' using the source files specified in the 'src_files' variable.
add_executable(${PROJECT_NAME} ${src_files})
# ライブラリをリンクする場合は以下のように記述
# find_library(library_name NAMES)
# target_link_libraries(${PROJECT_NAME} library_name)