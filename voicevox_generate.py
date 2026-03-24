#!/usr/bin/env python3
"""
VOICEVOX 음성 생성 스크립트

입력 형식 (한 줄에 하나):
    1_本編の前に、チャンネル登録といいね_13
    2_をお願いします。_13
    3_「ありがとうございます」と彼女は言った。_2

형식: {번호}_{문장}_{speaker_id}
출력: ~/Documents/voice/{번호}_{speaker_name}_{문장앞부분}.wav
"""

import sys
import os
import json
import urllib.request
import urllib.parse
import re

VOICEVOX_HOST = "http://localhost:50021"
OUTPUT_DIR = os.path.expanduser("~/Documents/voice")


def get_speaker_name(speaker_id):
    """speaker_id로 캐릭터 이름+스타일 가져오기"""
    try:
        req = urllib.request.Request(f"{VOICEVOX_HOST}/speakers")
        with urllib.request.urlopen(req) as resp:
            speakers = json.loads(resp.read())
        for sp in speakers:
            for style in sp["styles"]:
                if style["id"] == speaker_id:
                    return f'{sp["name"]}（{style["name"]}）'
    except:
        pass
    return f"speaker{speaker_id}"


def is_question(text):
    """의문문인지 판별"""
    clean = text.rstrip()
    if clean.endswith("？") or clean.endswith("?"):
        return True
    # 일본어 의문 종조사
    question_endings = ["の？", "か？", "の?", "か?", "のか", "ですか", "ますか",
                        "だろう", "でしょう", "かな", "かしら", "って？", "って?"]
    for ending in question_endings:
        if clean.endswith(ending):
            return True
    return False


def generate_voice(text, speaker_id):
    """VOICEVOX API로 음성 생성, WAV 바이너리 반환"""
    # 1. audio_query
    params = urllib.parse.urlencode({"text": text, "speaker": speaker_id})
    req = urllib.request.Request(
        f"{VOICEVOX_HOST}/audio_query?{params}",
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        query = json.loads(resp.read())

    # 青山龍星 (13, 81-86)은 0.9배 속도
    if speaker_id in {13, 81, 82, 83, 84, 85, 86}:
        query["speedScale"] = 0.9

    # 의문문이면 파라미터 조절
    if is_question(text):
        query["intonationScale"] = 1.3
        query["pitchScale"] = 0.05

    # 2. synthesis
    params = urllib.parse.urlencode({
        "speaker": speaker_id,
        "enable_interrogative_upspeak": "true" if is_question(text) else "false"
    })
    req = urllib.request.Request(
        f"{VOICEVOX_HOST}/synthesis?{params}",
        data=json.dumps(query).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        return resp.read()


def parse_line(line):
    """'1_文章_13' 형식 파싱 → (번호, 문장, speaker_id)"""
    line = line.strip()
    if not line:
        return None

    # 마지막 _ 이후가 speaker_id
    last_sep = line.rfind("_")
    if last_sep == -1:
        return None
    speaker_id_str = line[last_sep + 1:]
    rest = line[:last_sep]

    # 첫 번째 _ 이전이 번호
    first_sep = rest.find("_")
    if first_sep == -1:
        return None
    num_str = rest[:first_sep]
    text = rest[first_sep + 1:]

    try:
        num = int(num_str)
        speaker_id = int(speaker_id_str)
    except ValueError:
        return None

    return (num, text, speaker_id)


def sanitize_filename(text, max_len=20):
    """파일명에 쓸 수 있도록 정리"""
    # 파일명 금지 문자 제거
    clean = re.sub(r'[/\\:*?"<>|]', '', text)
    if len(clean) > max_len:
        clean = clean[:max_len]
    return clean


INTRO_DIR = os.path.join(os.path.expanduser("~/Documents"), "intro")


def main():
    intro_input = input("인트로인가요? (y/n): ").strip().lower()
    is_intro = intro_input in ("y", "yes")
    output_dir = INTRO_DIR if is_intro else OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    print("음성 생성할 텍스트를 입력하세요 (입력 끝나면 빈 줄 또는 Ctrl+D):")
    lines = []
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                if lines:
                    break
                continue
            lines.append(line)
    except EOFError:
        pass

    if not lines:
        print("입력이 없습니다.")
        return

    # 파싱
    entries = []
    for line in lines:
        parsed = parse_line(line)
        if parsed:
            entries.append(parsed)
        else:
            print(f"  파싱 실패 (스킵): {line}")

    if not entries:
        print("유효한 입력이 없습니다.")
        return

    # speaker 이름 캐시
    speaker_names = {}

    print(f"\n{len(entries)}개 음성 생성 시작 → {output_dir}\n")

    failed = []
    for num, text, speaker_id in entries:
        if speaker_id not in speaker_names:
            speaker_names[speaker_id] = get_speaker_name(speaker_id)
        name = speaker_names[speaker_id]
        safe_text = sanitize_filename(text, max_len=50)
        default_ids = {13, 81, 82, 83, 84, 85, 86}
        suffix = "_dialogue" if speaker_id not in default_ids else ""
        filename = f"{num}_{safe_text}{suffix}.wav"
        filepath = os.path.join(output_dir, filename)

        q_mark = " [疑問文]" if is_question(text) else ""
        print(f"  [{num:03d}] {name} | {text}{q_mark}")

        try:
            wav_data = generate_voice(text, speaker_id)
            with open(filepath, "wb") as f:
                f.write(wav_data)
            print(f"        → {filename} ({len(wav_data) // 1024}KB)")
        except Exception as e:
            print(f"        → 오류: {e}")
            failed.append((num, text, str(e)))

    print(f"\n완료! {output_dir} 에 저장되었습니다.")
    if failed:
        print(f"\n오류 발생 ({len(failed)}건):")
        for num, text, err in failed:
            print(f"  [{num:03d}] {text} → {err}")


if __name__ == "__main__":
    main()
