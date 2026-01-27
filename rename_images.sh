#!/bin/bash

IMAGE_DIR="$HOME/Documents/image"

# 이미지 폴더 존재 확인
if [ ! -d "$IMAGE_DIR" ]; then
    echo "오류: $IMAGE_DIR 폴더가 존재하지 않습니다."
    exit 1
fi

# 이미지 폴더의 파일 목록 (수정시간 오래된 순으로 정렬, 파일만)
cd "$IMAGE_DIR" || exit 1
FILES=()
for f in $(ls -tr); do
    [ -f "$f" ] && FILES+=("$f")
done

# 파일 수
FILE_COUNT=${#FILES[@]}

if [ "$FILE_COUNT" -eq 0 ]; then
    echo "오류: $IMAGE_DIR 폴더에 파일이 없습니다."
    exit 1
fi

echo "이미지 폴더에 ${FILE_COUNT}개의 파일이 있습니다."
echo "새 파일명을 한 줄씩 입력하세요 (입력 완료 후 Ctrl+D):"

# 여러 줄 입력 받기 (Ctrl+D로 입력 종료)
NEW_NAMES=()
while IFS= read -r line; do
    [ -n "$line" ] && NEW_NAMES+=("$line")
done

# 입력된 줄 수
INPUT_COUNT=${#NEW_NAMES[@]}

echo ""

# 개수 비교
if [ "$INPUT_COUNT" -ne "$FILE_COUNT" ]; then
    echo "오류: 개수가 일치하지 않습니다."
    echo "입력된 이름 수: $INPUT_COUNT"
    echo "이미지 파일 수: $FILE_COUNT"
    exit 1
fi

# 파일명 변경
echo "파일명 변경 시작..."
for i in "${!FILES[@]}"; do
    OLD_NAME="${FILES[$i]}"
    NEW_NAME="${NEW_NAMES[$i]}"

    # 확장자 추출
    EXTENSION="${OLD_NAME##*.}"

    # 새 이름에 확장자가 없으면 기존 확장자 추가
    if [[ "$NEW_NAME" != *.* ]]; then
        NEW_NAME="${NEW_NAME}.${EXTENSION}"
    fi

    mv "$OLD_NAME" "$NEW_NAME"
    echo "[$((i+1))/$FILE_COUNT] $OLD_NAME -> $NEW_NAME"
done

echo ""
echo "완료: $FILE_COUNT개 파일 이름 변경됨"
