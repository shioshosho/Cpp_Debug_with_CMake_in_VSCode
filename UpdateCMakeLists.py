#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path


def get_cpp_files():
    """同階層のcppファイルを取得"""
    cpp_files = []
    for file in os.listdir("."):
        if file.endswith(".cpp"):
            cpp_files.append(file)
    return sorted(cpp_files)


def get_vcxproj_file():
    """同階層のvcxprojファイルを取得"""
    for file in os.listdir("."):
        if file.endswith(".vcxproj"):
            return file
    return None


def convert_windows_path_to_wsl(path):
    """WindowsパスをWSL2パスに変換"""
    # C:/path/to/file -> /mnt/c/path/to/file
    if path.startswith("C:/") or path.startswith("C:\\"):
        path = path.replace("C:/", "/mnt/c/").replace("C:\\", "/mnt/c/")
    elif path.startswith("c:/") or path.startswith("c:\\"):
        path = path.replace("c:/", "/mnt/c/").replace("c:\\", "/mnt/c/")

    # バックスラッシュをスラッシュに変換
    path = path.replace("\\", "/")

    return path


def parse_vcxproj(vcxproj_file):
    """vcxprojファイルからIncludePathとLibraryPathを取得"""
    include_paths = []
    library_paths = []

    try:
        tree = ET.parse(vcxproj_file)
        root = tree.getroot()

        # 名前空間を処理
        ns = {"ns": root.tag.split("}")[0].strip("{")} if "}" in root.tag else {}

        # PropertyGroupを検索
        for prop_group in root.findall(
            ".//ns:PropertyGroup" if ns else ".//PropertyGroup", ns
        ):
            condition = prop_group.get("Condition", "")
            if "'$(Configuration)|$(Platform)'=='Debug|x64'" in condition:
                # IncludePathを取得
                include_path_elem = prop_group.find(
                    "ns:IncludePath" if ns else "IncludePath", ns
                )
                if include_path_elem is not None and include_path_elem.text:
                    paths = include_path_elem.text.split(";")
                    for path in paths:
                        path = path.strip()
                        if path:
                            include_paths.append(path)

                # LibraryPathを取得
                library_path_elem = prop_group.find(
                    "ns:LibraryPath" if ns else "LibraryPath", ns
                )
                if library_path_elem is not None and library_path_elem.text:
                    paths = library_path_elem.text.split(";")
                    for path in paths:
                        path = path.strip()
                        if path:
                            library_paths.append(path)

    except Exception as e:
        print(f"vcxprojファイルの解析エラー: {e}")

    return include_paths, library_paths


def format_path_for_cmake(path):
    """パスをCMake形式にフォーマット"""
    # WSLパスに変換
    path = convert_windows_path_to_wsl(path)

    # $(...)形式でない場合は""で囲む
    if not re.search(r"\$\([^)]+\)", path):
        path = f'"{path}"'

    return path


def find_matching_parenthesis(content, start_pos):
    """括弧の入れ子を考慮して、対応する閉じ括弧の位置を見つける"""
    counter = 1  # 最初の開き括弧はすでにカウント
    pos = start_pos

    while pos < len(content) and counter > 0:
        if content[pos] == "(":
            counter += 1
        elif content[pos] == ")":
            counter -= 1
        pos += 1

    if counter == 0:
        return pos - 1  # 閉じ括弧の位置を返す
    else:
        return -1  # 対応する閉じ括弧が見つからない


def find_set_block(content, variable_name, include_commented=False):
    """set()ブロックを正確に見つける"""
    # set(variable_name の部分を探す
    if include_commented:
        # コメントアウトされたものも含めて検索
        pattern = rf"^(\s*)(#\s*)?(set\s*\(\s*{variable_name}\s*)"
    else:
        # コメントアウトされていないもののみ検索
        pattern = rf"^(\s*)(set\s*\(\s*{variable_name}\s*)"

    for match in re.finditer(pattern, content, re.MULTILINE):
        if not include_commented:
            # コメントアウトされていないもののみを対象とする場合
            line_start = content.rfind("\n", 0, match.start()) + 1
            line_prefix = content[line_start : match.start()]

            # コメントアウトされているかチェック
            if "#" in line_prefix:
                continue

        if include_commented and match.group(2):  # コメントアウトされている
            prefix = match.group(3)
            start_pos = match.end()
        else:
            prefix = match.group(2) if not include_commented else match.group(3)
            start_pos = match.end()

        # 対応する閉じ括弧を見つける
        end_pos = find_matching_parenthesis(content, start_pos)

        if end_pos == -1:
            continue

        # 閉じ括弧の前の空白を含める
        suffix_start = end_pos
        while suffix_start > start_pos and content[suffix_start - 1].isspace():
            suffix_start -= 1

        return {
            "start": match.start(3)
            if include_commented and match.group(2)
            else match.start(2),
            "end": end_pos + 1,
            "prefix": prefix.strip(),
            "content": content[start_pos:suffix_start],
            "suffix": content[suffix_start : end_pos + 1],
            "full_match_start": match.start(),
            "indent": match.group(1),
            "is_commented": include_commented and match.group(2) is not None,
        }

    return None


def comment_out_block(content, variable_name):
    """set()ブロックをコメントアウトする"""
    block = find_set_block(content, variable_name)
    if not block:
        return content

    # ブロック全体を取得
    block_start = block["full_match_start"]
    block_end = block["end"]

    # 各行をコメントアウト
    block_content = content[block_start:block_end]
    lines = block_content.split("\n")
    commented_lines = []

    for line in lines:
        if line.strip():  # 空行でない場合
            commented_lines.append("# " + line)
        else:
            commented_lines.append(line)

    commented_block = "\n".join(commented_lines)

    # 置換
    return content[:block_start] + commented_block + content[block_end:]


def comment_out_line(content, pattern):
    """特定のパターンにマッチする行をコメントアウトする"""
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if re.search(pattern, line) and not line.strip().startswith("#"):
            lines[i] = "# " + line
    return "\n".join(lines)


def add_cmake_blocks(content, vcxproj_exists, include_paths, library_paths):
    """必要なCMakeブロックを追加"""
    lines = content.split("\n")

    # add_executable行を探す
    add_exec_index = -1
    for i, line in enumerate(lines):
        if "add_executable" in line:
            add_exec_index = i
            break

    if add_exec_index == -1:
        # add_executableが見つからない場合は末尾に追加
        insert_index = len(lines)
    else:
        # add_executableの前に挿入
        insert_index = add_exec_index

    # 挿入する内容を準備
    new_lines = []

    # 既存のブロックを確認（コメントアウトされたものも含めて）
    include_dirs_exists = (
        find_set_block(content, "INCLUDE_DIRS", include_commented=True) is not None
    )
    library_dirs_exists = (
        find_set_block(content, "LIBRARY_DIRS", include_commented=True) is not None
    )

    # INCLUDE_DIRSが存在しない場合のみ追加
    if not include_dirs_exists:
        if vcxproj_exists and include_paths:
            new_lines.append("set(INCLUDE_DIRS")
            for path in include_paths:
                formatted_path = format_path_for_cmake(path)
                new_lines.append(f"    {formatted_path}")
            new_lines.append(")")
            new_lines.append("include_directories(${INCLUDE_DIRS})")
        else:
            new_lines.append("# set(INCLUDE_DIRS")
            new_lines.append("#     # Add include directories here")
            new_lines.append("# )")
            new_lines.append("# include_directories(${INCLUDE_DIRS})")
        new_lines.append("")

    # LIBRARY_DIRSが存在しない場合のみ追加
    if not library_dirs_exists:
        if vcxproj_exists and library_paths:
            new_lines.append("set(LIBRARY_DIRS")
            for path in library_paths:
                formatted_path = format_path_for_cmake(path)
                new_lines.append(f"    {formatted_path}")
            new_lines.append(")")
            new_lines.append("link_directories(${LIBRARY_DIRS})")
        else:
            new_lines.append("# set(LIBRARY_DIRS")
            new_lines.append("#     # Add library directories here")
            new_lines.append("# )")
            new_lines.append("# link_directories(${LIBRARY_DIRS})")
        new_lines.append("")

    # 内容を挿入
    if new_lines:
        lines[insert_index:insert_index] = new_lines

    return "\n".join(lines)


def update_cmake_lists(cpp_files, vcxproj_exists, include_paths, library_paths):
    """CMakeLists.txtを更新"""
    cmake_file = "CMakeLists.txt"

    if not os.path.exists(cmake_file):
        print(f"{cmake_file}が見つかりません")
        return

    with open(cmake_file, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. src_filesブロックを更新
    src_block = find_set_block(content, "src_files")

    if src_block:
        # 元のブロックからインデントを検出
        original_content = content[src_block["start"] : src_block["end"]]
        lines = original_content.split("\n")
        indent = "    "  # デフォルトインデント
        for line in lines[1:]:
            match = re.match(r"^(\s+)\S", line)
            if match:
                indent = match.group(1)
                break

        # cppファイルリストを作成
        cpp_list = []
        for cpp_file in cpp_files:
            cpp_list.append(f"{indent}{cpp_file}")

        # 新しいブロックを作成
        if cpp_list:
            new_src_block = (
                f"{src_block['prefix']}\n{chr(10).join(cpp_list)}{src_block['suffix']}"
            )
        else:
            new_src_block = f"{src_block['prefix']}{src_block['suffix']}"

        content = (
            content[: src_block["start"]] + new_src_block + content[src_block["end"] :]
        )

    # 2. INCLUDE_DIRSブロックの処理
    include_block_exists = find_set_block(content, "INCLUDE_DIRS") is not None

    if not vcxproj_exists and include_block_exists:
        # vcxprojがない場合はコメントアウト
        content = comment_out_block(content, "INCLUDE_DIRS")
        # include_directoriesもコメントアウト
        content = comment_out_line(
            content, r"^\s*include_directories\s*\(\s*\$\{INCLUDE_DIRS\}\s*\)"
        )
    elif vcxproj_exists and include_block_exists:
        # vcxprojがある場合は更新
        include_block = find_set_block(content, "INCLUDE_DIRS")
        if include_block:
            # インデントを検出
            original_content = content[include_block["start"] : include_block["end"]]
            lines = original_content.split("\n")
            indent = "    "  # デフォルトインデント
            for line in lines[1:]:
                match = re.match(r"^(\s+)\S", line)
                if match:
                    indent = match.group(1)
                    break

            # インクルードパスリストを作成
            include_list = []
            for path in include_paths:
                formatted_path = format_path_for_cmake(path)
                include_list.append(f"{indent}{formatted_path}")

            # 新しいブロックを作成
            if include_list:
                new_include_block = f"{include_block['prefix']}\n{
                    chr(10).join(include_list)
                }{include_block['suffix']}"
            else:
                new_include_block = (
                    f"{include_block['prefix']}{include_block['suffix']}"
                )

            content = (
                content[: include_block["start"]]
                + new_include_block
                + content[include_block["end"] :]
            )

    # 3. LIBRARY_DIRSブロックの処理
    library_block_exists = find_set_block(content, "LIBRARY_DIRS") is not None

    if not vcxproj_exists and library_block_exists:
        # vcxprojがない場合はコメントアウト
        content = comment_out_block(content, "LIBRARY_DIRS")
        # link_directoriesもコメントアウト
        content = comment_out_line(
            content, r"^\s*link_directories\s*\(\s*\$\{LIBRARY_DIRS\}\s*\)"
        )
    elif vcxproj_exists and library_block_exists:
        # vcxprojがある場合は更新
        library_block = find_set_block(content, "LIBRARY_DIRS")
        if library_block:
            # インデントを検出
            original_content = content[library_block["start"] : library_block["end"]]
            lines = original_content.split("\n")
            indent = "    "  # デフォルトインデント
            for line in lines[1:]:
                match = re.match(r"^(\s+)\S", line)
                if match:
                    indent = match.group(1)
                    break

            # ライブラリパスリストを作成
            library_list = []
            for path in library_paths:
                formatted_path = format_path_for_cmake(path)
                library_list.append(f"{indent}{formatted_path}")

            # 新しいブロックを作成
            if library_list:
                new_library_block = f"{library_block['prefix']}\n{
                    chr(10).join(library_list)
                }{library_block['suffix']}"
            else:
                new_library_block = (
                    f"{library_block['prefix']}{library_block['suffix']}"
                )

            content = (
                content[: library_block["start"]]
                + new_library_block
                + content[library_block["end"] : :]
            )

    # 4. 必要なブロックが存在しない場合は追加（コメントアウトされたものも含めて確認）
    include_block_exists_any = (
        find_set_block(content, "INCLUDE_DIRS", include_commented=True) is not None
    )
    library_block_exists_any = (
        find_set_block(content, "LIBRARY_DIRS", include_commented=True) is not None
    )

    if not include_block_exists_any or not library_block_exists_any:
        content = add_cmake_blocks(
            content, vcxproj_exists, include_paths, library_paths
        )

    # ファイルに書き込み
    with open(cmake_file, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"{cmake_file}を更新しました")


def main():
    # cppファイルを取得
    cpp_files = get_cpp_files()
    print(f"見つかったcppファイル: {cpp_files}")

    # vcxprojファイルを取得
    vcxproj_file = get_vcxproj_file()
    vcxproj_exists = vcxproj_file is not None

    include_paths = []
    library_paths = []

    if vcxproj_exists:
        print(f"vcxprojファイル: {vcxproj_file}")
        # vcxprojファイルを解析
        include_paths, library_paths = parse_vcxproj(vcxproj_file)
        print(f"IncludePath: {include_paths}")
        print(f"LibraryPath: {library_paths}")
    else:
        print("vcxprojファイルが見つかりません")

    # CMakeLists.txtを更新
    update_cmake_lists(cpp_files, vcxproj_exists, include_paths, library_paths)


if __name__ == "__main__":
    main()
