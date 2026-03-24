#!/usr/bin/env python3
"""
YouTube 영상 자동 생성 스크립트

구조: 1.인트로 → 2.구독영상 → 3.본문(음성+이미지+자막) → 4.마지막영상
"""

import os
import re
import random
import subprocess
import glob
import tempfile
import shutil

# ========== 경로 설정 ==========
DOCS = os.path.expanduser("~/Documents")
INTRO_DIR = os.path.join(DOCS, "intro")
YOUTUBE_DIR = os.path.join(DOCS, "youtube")
VOICE_DIR = os.path.join(DOCS, "voice")
IMAGE_DIR = os.path.join(DOCS, "image")

def get_next_output_path():
    youtube_dir = os.path.join(os.path.expanduser("~/Documents"), "youtube")
    max_num = 0
    for f in os.listdir(youtube_dir):
        m = re.match(r'^(\d+)', f)
        if m:
            max_num = max(max_num, int(m.group(1)))
    return os.path.join(youtube_dir, f"{max_num + 1}.mp4")

OUTPUT_FILE = get_next_output_path()

BGM_PATH = os.path.join(YOUTUBE_DIR, "Lullaby - JVNA.mp3")
BGM_FADE_DURATION = 3

# 영상 설정
WIDTH = 1280
HEIGHT = 720
FPS = 30
FONT_SIZE = 103
BORDER_SIZE = 5
SUBTITLE_MARGIN_LR = 20
MAX_CHARS_PER_LINE = 13
VOICE_GAP = 0.15  # 본문 음성 간 텀 (초)
INTRO_GAP = 0.5   # 인트로 장면 간 텀 (초)


def run_ffmpeg(cmd_str):
    result = subprocess.run(cmd_str, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"    ffmpeg 오류: {result.stderr[-400:]}")
    return result.returncode == 0


def get_duration(filepath):
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", filepath],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())


def has_audio_stream(filepath):
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "a",
         "-show_entries", "stream=codec_type", "-of", "csv=p=0", filepath],
        capture_output=True, text=True
    )
    return bool(result.stdout.strip())


def wrap_text(text, max_chars=None):
    if max_chars is None:
        max_chars = MAX_CHARS_PER_LINE
    if len(text) <= max_chars:
        return text

    # 2줄 이내 목표: 절반 근처 구두점에서 자르기
    half = len(text) // 2
    # 절반 근처에서 구두점 찾기
    best_cut = None
    for dist in range(0, half):
        for pos in [half + dist, half - dist]:
            if 0 < pos < len(text) and text[pos - 1] in '、。，．！？」）』 ':
                # 양쪽 다 max_chars 이내인지 확인
                if pos <= max_chars and len(text) - pos <= max_chars:
                    best_cut = pos
                    break
        if best_cut:
            break

    # 구두점에서 못 찾으면 절반에서 강제 자르기 (max_chars 이내 보장)
    if not best_cut:
        best_cut = min(half, max_chars)

    line1 = text[:best_cut]
    line2 = text[best_cut:]

    # 각 줄이 max_chars 넘으면 강제로 자르기 (안전장치)
    if len(line1) > max_chars:
        line1 = line1[:max_chars]
        line2 = text[max_chars:]
    if len(line2) > max_chars:
        line2 = line2[:max_chars]

    return line1 + "\\N" + line2


def make_ass_file(text, style, duration, ass_path):
    text = wrap_text(text)
    h = int(duration // 3600)
    m = int((duration % 3600) // 60)
    s = duration % 60
    end_time = f"{h}:{m:02d}:{s:05.2f}"

    border = BORDER_SIZE
    if style == "narration":
        primary = "&H00FFFFFF"
        outline = "&H00000000"
        bold = -1
        italic = 0
        border = 8  # 나레이션 border 두껍게
    elif style == "dialogue":
        # 대사: 연한 노란색, 진갈색 border, 이탤릭+Bold
        primary = "&H00A8FFFF"
        outline = "&H00204080"
        bold = -1
        italic = -1
    elif style == "intro":
        primary = "&H0000DCFF"
        outline = "&H00000000"
        bold = 0
        italic = -1
        border = 8  # 인트로도 border 두껍게
    else:
        primary = "&H00FFFFFF"
        outline = "&H00000000"
        bold = 0
        italic = 0

    # ScaleY=90으로 줄간 간격 줄이기
    ass_content = f"""[Script Info]
Title: Subtitle
ScriptType: v4.00+
PlayResX: {WIDTH}
PlayResY: {HEIGHT}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Noto Sans CJK JP,{FONT_SIZE},{primary},&H000000FF,{outline},&H00000000,{bold},{italic},0,0,100,93,0,0,1,{border},0,2,{SUBTITLE_MARGIN_LR},{SUBTITLE_MARGIN_LR},70,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,{end_time},Default,,0,0,0,,{text}
"""
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_content)


def parse_voice_filename(filename):
    name = os.path.splitext(filename)[0]
    is_dialogue = name.endswith("_dialogue")
    if is_dialogue:
        name = name[:-len("_dialogue")]
    first_sep = name.find("_")
    if first_sep == -1:
        return None
    try:
        num = int(name[:first_sep])
    except ValueError:
        return None
    text = name[first_sep + 1:]
    return (num, text, is_dialogue)


def find_image_for_number(num):
    for base_dir in [IMAGE_DIR, os.path.join(IMAGE_DIR, "success")]:
        for ext in ['.png', '.jpg', '.jpeg', '.webp', '.bmp']:
            pattern = os.path.join(base_dir, f"{num}_*{ext}")
            matches = glob.glob(pattern)
            if matches:
                return matches[0]
    return None


def get_ken_burns_filter(duration, effect_index=None):
    """Ken Burns 효과. 모든 효과가 점진적으로 시작해서 깜빡임 없음"""
    frames = int(duration * FPS) + 5
    # on은 0부터 시작. on/frames = 0.0 → 1.0 진행률
    # 모든 효과를 "시작상태에서 점진적으로 변화"하는 방식으로 통일

    effects = [
        # zoom in: 1.0 → 1.35 (중앙 기준)
        f"zoompan=z='1+0.35*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS}",
        # zoom out: 1.35 → 1.0 (중앙 기준)
        f"zoompan=z='1.35-0.35*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS}",
        # zoom in + pan up: 확대하면서 위로
        f"zoompan=z='1+0.2*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)-ih*0.08*on/{frames}':d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS}",
        # zoom in + pan down: 확대하면서 아래로
        f"zoompan=z='1+0.2*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)+ih*0.08*on/{frames}':d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS}",
        # zoom in + pan left: 확대하면서 왼쪽으로
        f"zoompan=z='1+0.2*on/{frames}':x='iw/2-(iw/zoom/2)-iw*0.08*on/{frames}':y='ih/2-(ih/zoom/2)':d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS}",
        # zoom in + pan right: 확대하면서 오른쪽으로
        f"zoompan=z='1+0.2*on/{frames}':x='iw/2-(iw/zoom/2)+iw*0.08*on/{frames}':y='ih/2-(ih/zoom/2)':d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS}",
    ]
    if effect_index is not None:
        return effects[effect_index % len(effects)]
    return random.choice(effects)


def shquote(path):
    return "'" + path.replace("'", "'\\''") + "'"


def make_segment_image_voice(voice_path, image_path, subtitle_text,
                              is_dialogue, seg_path, tmpdir, effect_index=None):
    """이미지 + 음성 + 자막 → 세그먼트 (음성 뒤 짧은 텀 포함)"""
    duration = get_duration(voice_path) + VOICE_GAP
    ass_path = os.path.join(tmpdir, f"sub_{random.randint(0,999999)}.ass")
    style = "dialogue" if is_dialogue else "narration"
    make_ass_file(subtitle_text, style, duration - VOICE_GAP, ass_path)

    ken_burns = get_ken_burns_filter(duration, effect_index)
    ass_esc = ass_path.replace(":", "\\:")

    # 음성 뒤에 무음 패딩 추가
    cmd = (
        f"ffmpeg -y "
        f"-loop 1 -framerate {FPS} -i {shquote(image_path)} "
        f"-i {shquote(voice_path)} "
        f"-f lavfi -t {VOICE_GAP} -i anullsrc=r=44100:cl=stereo "
        f"-filter_complex \"[1:a][2:a]concat=n=2:v=0:a=1[a];[0:v]scale=4000:-1,{ken_burns},format=yuv420p,ass='{ass_esc}'[v]\" "
        f"-map '[v]' -map '[a]' "
        f"-c:v libx264 -preset fast -crf 23 -bsf:v h264_mp4toannexb "
        f"-c:a aac -b:a 192k -ar 44100 -ac 2 "
        f"-t {duration} "
        f"-f mpegts "
        f"{shquote(seg_path)}"
    )
    run_ffmpeg(cmd)
    if os.path.exists(ass_path):
        os.remove(ass_path)


def make_intro_segment(video_path, voice_path, subtitle_text, seg_path, tmpdir):
    voice_dur = get_duration(voice_path)
    duration = voice_dur + INTRO_GAP  # 인트로 장면 간 텀
    ass_path = os.path.join(tmpdir, f"intro_{random.randint(0,999999)}.ass")
    make_ass_file(subtitle_text, "intro", voice_dur, ass_path)

    ass_esc = ass_path.replace(":", "\\:")

    cmd = (
        f"ffmpeg -y "
        f"-ss 0 -t {duration} -i {shquote(video_path)} "
        f"-i {shquote(voice_path)} "
        f"-f lavfi -t {INTRO_GAP} -i anullsrc=r=44100:cl=stereo "
        f"-filter_complex \"[1:a][2:a]concat=n=2:v=0:a=1[a];"
        f"[0:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2,setsar=1,"
        f"fps={FPS},format=yuv420p,ass='{ass_esc}'[v]\" "
        f"-map '[v]' -map '[a]' "
        f"-c:v libx264 -preset fast -crf 23 -bsf:v h264_mp4toannexb "
        f"-c:a aac -b:a 192k -ar 44100 -ac 2 "
        f"-t {duration} "
        f"-f mpegts "
        f"{shquote(seg_path)}"
    )
    run_ffmpeg(cmd)
    if os.path.exists(ass_path):
        os.remove(ass_path)


def normalize_video(input_path, output_path):
    """영상을 mpegts로 정규화 (텀 없는 concat을 위해)"""
    has_audio = has_audio_stream(input_path)

    vf = (f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
          f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2,setsar=1,"
          f"fps={FPS},format=yuv420p")

    # mpegts로 출력 (concat protocol 사용 가능)
    ts_path = output_path  # .mp4 대신 .ts로 저장
    if has_audio:
        cmd = (
            f"ffmpeg -y -fflags +genpts -i {shquote(input_path)} "
            f"-vf \"{vf}\" "
            f"-c:v libx264 -preset fast -crf 23 -bsf:v h264_mp4toannexb "
            f"-c:a aac -b:a 192k -ar 44100 -ac 2 "
            f"-f mpegts "
            f"{shquote(ts_path)}"
        )
    else:
        cmd = (
            f"ffmpeg -y -fflags +genpts -i {shquote(input_path)} "
            f"-f lavfi -i anullsrc=r=44100:cl=stereo "
            f"-vf \"{vf}\" "
            f"-c:v libx264 -preset fast -crf 23 -bsf:v h264_mp4toannexb "
            f"-c:a aac -b:a 192k "
            f"-map 0:v -map 1:a -shortest "
            f"-f mpegts "
            f"{shquote(ts_path)}"
        )
    run_ffmpeg(cmd)


def concat_segments(seg_list, output_path):
    """mpegts concat protocol로 합치기 (텀 없음)"""
    if not seg_list:
        return
    if len(seg_list) == 1:
        # 단일 ts → mp4 변환
        cmd = (
            f"ffmpeg -y -i {shquote(seg_list[0])} "
            f"-c copy -movflags +faststart "
            f"{shquote(output_path)}"
        )
        run_ffmpeg(cmd)
        return

    # concat protocol: "concat:file1.ts|file2.ts|..."
    concat_input = "concat:" + "|".join(seg_list)

    cmd = (
        f"ffmpeg -y -i \"{concat_input}\" "
        f"-c copy -movflags +faststart "
        f"{shquote(output_path)}"
    )
    run_ffmpeg(cmd)


def main():
    # 시작점 확인할 번호 입력 (쉼표로 구분)
    seek_input = input("시작점을 확인할 본문 번호 (쉼표 구분, 없으면 Enter): ").strip()
    seek_nums = set()
    if seek_input:
        for s in seek_input.split(","):
            s = s.strip()
            if s.isdigit():
                seek_nums.add(int(s))

    tmpdir = tempfile.mkdtemp(prefix="video_build_")
    print(f"작업 디렉토리: {tmpdir}")
    segments = []
    seg_index = 0
    pre_bgm_count = 0
    # 세그먼트별 (label, duration) 기록 — 시작점 계산용
    seg_info = []  # [(label, duration_sec), ...]

    # ========== 1. 인트로 ==========
    print("\n[1/4] 인트로 생성...")
    intro_videos = sorted(glob.glob(os.path.join(INTRO_DIR, "*.mp4")))
    intro_voices = sorted(glob.glob(os.path.join(INTRO_DIR, "*.wav")))

    if intro_videos and intro_voices:
        intro_map = {}
        for v in intro_videos:
            m = re.match(r'^(\d+)', os.path.basename(v))
            if m:
                intro_map.setdefault(int(m.group(1)), {})["video"] = v
        for v in intro_voices:
            m = re.match(r'^(\d+)', os.path.basename(v))
            if m:
                intro_map.setdefault(int(m.group(1)), {})["voice"] = v

        for num in sorted(intro_map.keys()):
            entry = intro_map[num]
            if "video" not in entry or "voice" not in entry:
                continue
            voice_name = os.path.splitext(os.path.basename(entry["voice"]))[0]
            first_sep = voice_name.find("_")
            subtitle = voice_name[first_sep + 1:] if first_sep != -1 else voice_name

            seg_path = os.path.join(tmpdir, f"seg_{seg_index:04d}.ts")
            print(f"  인트로 {num}: {subtitle[:40]}...")
            make_intro_segment(entry["video"], entry["voice"], subtitle, seg_path, tmpdir)
            if os.path.exists(seg_path) and os.path.getsize(seg_path) > 0:
                segments.append(seg_path)
                seg_info.append((f"intro_{num}", get_duration(seg_path)))
                seg_index += 1
                pre_bgm_count += 1
    else:
        print("  인트로 파일 없음. 스킵.")

    # ========== 2. 구독영상 ==========
    print("\n[2/4] 구독영상 추가...")
    subscribe_path = os.path.join(YOUTUBE_DIR, "구독영상.mp4")
    if os.path.exists(subscribe_path):
        seg_path = os.path.join(tmpdir, f"seg_{seg_index:04d}.ts")
        normalize_video(subscribe_path, seg_path)
        if os.path.exists(seg_path):
            segments.append(seg_path)
            seg_info.append(("subscribe", get_duration(seg_path)))
            seg_index += 1
            pre_bgm_count += 1
            print("  완료.")
            # 구독영상 뒤 짧은 텀 (검은화면 + 무음)
            gap_path = os.path.join(tmpdir, f"seg_{seg_index:04d}.ts")
            gap_cmd = (
                f"ffmpeg -y "
                f"-f lavfi -i color=c=black:s={WIDTH}x{HEIGHT}:r={FPS}:d=0.5 "
                f"-f lavfi -i anullsrc=r=44100:cl=stereo "
                f"-c:v libx264 -preset fast -crf 23 -bsf:v h264_mp4toannexb "
                f"-c:a aac -b:a 192k -t 0.5 "
                f"-f mpegts {shquote(gap_path)}"
            )
            run_ffmpeg(gap_cmd)
            if os.path.exists(gap_path):
                segments.append(gap_path)
                seg_info.append(("gap", 0.5))
                seg_index += 1
                pre_bgm_count += 1
    else:
        print("  구독영상 없음. 스킵.")

    # ========== 3. 본문 ==========
    print("\n[3/4] 본문 생성...")
    voice_files = glob.glob(os.path.join(VOICE_DIR, "*.wav"))
    voice_entries = []
    for vf in voice_files:
        parsed = parse_voice_filename(os.path.basename(vf))
        if parsed:
            num, text, is_dialogue = parsed
            image = find_image_for_number(num)
            voice_entries.append((num, text, is_dialogue, vf, image))

    voice_entries.sort(key=lambda x: x[0])

    # 이미지 없으면 이전 이미지 사용
    last_image = None
    for i, (num, text, is_dialogue, vf, image) in enumerate(voice_entries):
        if image:
            last_image = image
        elif last_image:
            voice_entries[i] = (num, text, is_dialogue, vf, last_image)

    # 같은 이미지가 연속이면 같은 Ken Burns 효과 유지
    image_effect_map = {}  # image_path -> effect_index

    total = len(voice_entries)
    for i, (num, text, is_dialogue, voice_path, image_path) in enumerate(voice_entries):
        dtype = "대사" if is_dialogue else "나레이션"
        print(f"  [{i+1}/{total}] #{num} ({dtype}) {text[:30]}...")

        if not image_path:
            print(f"    이미지 없음. 스킵.")
            continue

        # 이미지별 효과 결정: 새 이미지면 새 랜덤 효과
        if image_path not in image_effect_map:
            image_effect_map[image_path] = random.randint(0, 5)
        effect_idx = image_effect_map[image_path]

        seg_path = os.path.join(tmpdir, f"seg_{seg_index:04d}.ts")
        make_segment_image_voice(
            voice_path, image_path, text, is_dialogue, seg_path, tmpdir,
            effect_index=effect_idx
        )
        if os.path.exists(seg_path) and os.path.getsize(seg_path) > 0:
            seg_dur = get_duration(voice_path) + VOICE_GAP
            segments.append(seg_path)
            seg_info.append((f"body_{num}", seg_dur))
            seg_index += 1
        else:
            print(f"    세그먼트 생성 실패!")

    # ========== 4. 마지막영상 ==========
    print("\n[4/4] 마지막영상 추가...")
    last_path = os.path.join(YOUTUBE_DIR, "마지막영상.mp4")
    if os.path.exists(last_path):
        seg_path = os.path.join(tmpdir, f"seg_{seg_index:04d}.ts")
        normalize_video(last_path, seg_path)
        if os.path.exists(seg_path):
            segments.append(seg_path)
            seg_info.append(("last_video", get_duration(seg_path)))
            seg_index += 1
            print("  완료.")
    else:
        print("  마지막영상 없음. 스킵.")

    # ========== 합치기 ==========
    if not segments:
        print("\n생성된 세그먼트가 없습니다!")
        shutil.rmtree(tmpdir)
        return

    pre_bgm_segments = segments[:pre_bgm_count]
    body_segments = segments[pre_bgm_count:]

    # 전체 합치기 먼저
    all_merged = os.path.join(tmpdir, "all_merged.mp4")
    print(f"\n전체 {len(segments)}개 세그먼트 합치는 중...")
    concat_segments(segments, all_merged)

    if not os.path.exists(all_merged):
        print("합치기 실패!")
        shutil.rmtree(tmpdir)
        return

    # BGM 믹싱: 본문 시작 지점부터 마지막영상 직전까지
    if os.path.exists(BGM_PATH) and body_segments:
        print("BGM 믹싱 중...")

        # 인트로+구독 구간 길이 계산
        pre_dur = 0
        for seg in pre_bgm_segments:
            pre_dur += get_duration(seg)

        # 마지막영상 길이
        last_dur = 0
        if os.path.exists(last_path):
            last_dur = get_duration(segments[-1])

        total_dur = get_duration(all_merged)
        bgm_start = pre_dur
        bgm_end = total_dur - last_dur
        bgm_duration = bgm_end - bgm_start

        if bgm_duration > 0:
            fade_out_start = max(0, bgm_duration - BGM_FADE_DURATION)

            # BGM을 정확한 구간에만 믹싱
            cmd = (
                f"ffmpeg -y "
                f"-i {shquote(all_merged)} "
                f"-stream_loop -1 -i {shquote(BGM_PATH)} "
                f"-filter_complex "
                f"\"[1:a]atrim=0:{bgm_duration},asetpts=PTS-STARTPTS,"
                f"aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                f"volume=0.15,"
                f"afade=t=in:st=0:d={BGM_FADE_DURATION},"
                f"afade=t=out:st={fade_out_start}:d={BGM_FADE_DURATION},"
                f"adelay={int(bgm_start*1000)}|{int(bgm_start*1000)}[bgm];"
                f"[0:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[main];"
                f"[main][bgm]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[aout]\" "
                f"-map 0:v -map '[aout]' "
                f"-c:v copy -c:a aac -b:a 192k "
                f"-movflags +faststart "
                f"{shquote(OUTPUT_FILE)}"
            )
            if run_ffmpeg(cmd):
                print("  BGM 믹싱 완료.")
            else:
                print("  BGM 믹싱 실패, BGM 없이 저장")
                shutil.copy2(all_merged, OUTPUT_FILE)
        else:
            shutil.copy2(all_merged, OUTPUT_FILE)
    else:
        shutil.copy2(all_merged, OUTPUT_FILE)

    if os.path.exists(OUTPUT_FILE):
        size_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
        duration = get_duration(OUTPUT_FILE)
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        print(f"\n완료! {OUTPUT_FILE}")
        print(f"  길이: {minutes}분 {seconds}초")
        print(f"  크기: {size_mb:.1f}MB")
    else:
        print(f"\n최종 합치기 실패!")

    # 시작점 출력
    if seek_nums and seg_info:
        print(f"\n--- 시작점 ---")
        elapsed = 0.0
        for label, dur in seg_info:
            if label.startswith("body_"):
                body_num = int(label.split("_")[1])
                if body_num in seek_nums:
                    m = int(elapsed // 60)
                    s = elapsed % 60
                    print(f"  #{body_num}: {m}:{s:05.2f} ({elapsed:.2f}초)")
            elapsed += dur

    shutil.rmtree(tmpdir)
    print("임시 파일 정리 완료.")


if __name__ == "__main__":
    main()
