#!/usr/bin/env python3
"""
Vrew 웹사이트에서 이미지 자동 삽입 스크립트
Documents/image 폴더의 이미지 파일명으로 검색 후 해당 위치에 이미지 삽입

하이브리드 방식:
- JavaScript로 웹 요소 조작 (클래스/ID 기반)
- AppleScript로 브라우저에 JS 주입
- pyautogui로 파일 선택 대화상자 처리
"""

import os
import time
import glob
import subprocess
import random
import shutil
import pyautogui
import pyperclip

# 설정
IMAGE_FOLDER = os.path.expanduser("~/Documents/image")
SUCCESS_FOLDER = os.path.join(IMAGE_FOLDER, "success")
SUPPORTED_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']

# 대기 시간 설정 (초)
SHORT_WAIT = 0.5
MEDIUM_WAIT = 1.0
LONG_WAIT = 2.0

# pyautogui 설정
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1


def get_image_files():
    """이미지 폴더에서 지원하는 이미지 파일 목록 가져오기"""
    image_files = []
    for ext in SUPPORTED_EXTENSIONS:
        image_files.extend(glob.glob(os.path.join(IMAGE_FOLDER, f"*{ext}")))
        image_files.extend(glob.glob(os.path.join(IMAGE_FOLDER, f"*{ext.upper()}")))
    return sorted(image_files)


def get_search_name(filepath):
    """파일 경로에서 검색용 이름 추출 (확장자 제외)"""
    filename = os.path.basename(filepath)
    name_without_ext = os.path.splitext(filename)[0]
    return name_without_ext


def ensure_success_folder():
    """success 폴더가 없으면 생성"""
    if not os.path.exists(SUCCESS_FOLDER):
        os.makedirs(SUCCESS_FOLDER)
        print(f"  success 폴더 생성: {SUCCESS_FOLDER}")


def move_to_success(filepath):
    """성공한 이미지를 success 폴더로 이동"""
    ensure_success_folder()
    filename = os.path.basename(filepath)
    dest_path = os.path.join(SUCCESS_FOLDER, filename)

    # 동일한 파일이 있으면 덮어쓰기
    if os.path.exists(dest_path):
        os.remove(dest_path)

    shutil.move(filepath, dest_path)
    print(f"    이미지 이동: {filename} -> success/")


def run_js_in_chrome(js_code):
    """AppleScript를 사용해 Chrome에서 JavaScript 실행"""
    import json
    # JavaScript 코드 이스케이프 - JSON 인코딩으로 특수문자 안전하게 처리
    # 먼저 문자열을 JSON으로 인코딩한 후, AppleScript용 이스케이프 적용
    js_escaped = js_code.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

    applescript = f'''
    tell application "Google Chrome"
        tell active tab of front window
            execute javascript "{js_escaped}"
        end tell
    end tell
    '''

    try:
        result = subprocess.run(
            ['osascript', '-e', applescript],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            print(f"    JS 실행 오류: {result.stderr}")
            return None
    except subprocess.TimeoutExpired:
        print("    JS 실행 타임아웃")
        return None
    except Exception as e:
        print(f"    AppleScript 오류: {e}")
        return None


def run_js_in_safari(js_code):
    """AppleScript를 사용해 Safari에서 JavaScript 실행"""
    js_escaped = js_code.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

    applescript = f'''
    tell application "Safari"
        do JavaScript "{js_escaped}" in front document
    end tell
    '''

    try:
        result = subprocess.run(
            ['osascript', '-e', applescript],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except:
        return None


def run_js(js_code, browser='chrome'):
    """브라우저에서 JavaScript 실행"""
    if browser.lower() == 'safari':
        return run_js_in_safari(js_code)
    else:
        return run_js_in_chrome(js_code)


# ========== JavaScript 코드 조각 ==========

JS_OPEN_SEARCH = '''
(function() {
    // Cmd+F 키 이벤트 시뮬레이션
    document.dispatchEvent(new KeyboardEvent('keydown', {
        key: 'f', code: 'KeyF', metaKey: true, bubbles: true
    }));
    return 'ok';
})();
'''

JS_SEARCH_TEXT = '''
(function(text) {
    // 검색 입력창 찾기
    const selectors = [
        'input[placeholder*="검색"]',
        'input[placeholder*="찾기"]',
        '.search-input input',
        'input[type="search"]',
    ];

    let input = null;
    for (const sel of selectors) {
        input = document.querySelector(sel);
        if (input && input.offsetParent !== null) break;
    }

    if (!input) {
        // 모든 visible text input 확인
        const inputs = document.querySelectorAll('input[type="text"], input:not([type])');
        for (const inp of inputs) {
            if (inp.offsetParent !== null) {
                input = inp;
                break;
            }
        }
    }

    if (!input) return 'not_found';

    // 텍스트 입력
    input.focus();
    input.value = text;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', {
        key: 'Enter', code: 'Enter', bubbles: true
    }));

    return 'ok';
})('%s');
'''

JS_CLICK_FIRST_RESULT = '''
(function() {
    // 검색 결과 찾기 (자막줄 탭의 첫 번째 결과)
    const el = document.querySelector('.searched-clip-wrapper');
    if (el && el.offsetParent !== null) {
        el.click();
        return 'ok';
    }
    return 'no_result';
})();
'''

JS_GET_SEARCH_RESULT_COUNT = '''
(function() {
    // 검색 결과 개수 반환
    const results = document.querySelectorAll('.searched-clip-wrapper');
    return results.length;
})();
'''

JS_CLICK_MATCHING_RESULT = '''
(function(targetName) {
    // 검색 결과 중 파일명 전체가 포함된 것만 클릭
    const results = document.querySelectorAll('.searched-clip-wrapper');
    if (results.length === 0) return 'no_result';

    // 공백 제거 및 유니코드 정규화 함수
    function normalize(str) {
        // 유니코드 정규화 (NFD/NFC 차이 해결 - 일본어 탁점 등)
        str = str.normalize('NFC');
        let result = '';
        for (let i = 0; i < str.length; i++) {
            const c = str.charCodeAt(i);
            // 공백 문자 제외 (space, tab, newline, carriage return, nbsp, 전각공백)
            if (c !== 32 && c !== 9 && c !== 10 && c !== 13 && c !== 160 && c !== 12288) {
                result += str[i];
            }
        }
        return result;
    }

    const normalizedTarget = normalize(targetName);

    // 각 결과에서 자막 텍스트에 파일명 전체가 포함되는지 확인
    for (const el of results) {
        const captionEl = el.querySelector('.searched-clip-caption');
        if (!captionEl) continue;

        const captionText = normalize(captionEl.textContent || '');

        // 파일명 전체가 자막에 포함되어야만 클릭
        if (captionText.includes(normalizedTarget)) {
            el.click();
            return 'ok_matched';
        }
    }

    // 디버그: 첫 번째 결과의 자막 텍스트와 검색 대상 반환
    const firstCaption = results[0]?.querySelector('.searched-clip-caption');
    const debugCaption = firstCaption ? normalize(firstCaption.textContent || '') : 'no_caption';
    return 'no_match|caption:' + debugCaption.substring(0, 50) + '|target:' + normalizedTarget.substring(0, 50);
})('%s');
'''

JS_CLICK_ROW_NUMBER = '''
(function() {
    // 선택된 클립의 행 번호 클릭
    const el = document.querySelector('.c-jtvrbl.c-jtvrbl-fHayrg-selected-true');
    if (el && el.offsetParent !== null) {
        // 마우스 이벤트 시퀀스 발생
        const rect = el.getBoundingClientRect();
        const x = rect.left + rect.width / 2;
        const y = rect.top + rect.height / 2;
        const opts = { bubbles: true, cancelable: true, view: window, clientX: x, clientY: y };
        el.dispatchEvent(new MouseEvent('mousedown', opts));
        el.dispatchEvent(new MouseEvent('mouseup', opts));
        el.dispatchEvent(new MouseEvent('click', opts));
        return 'ok';
    }
    return 'not_found';
})();
'''

JS_CLICK_INSERT_BUTTON = '''
(function() {
    // 플로팅 메뉴의 삽입 버튼 찾기
    const menu = document.querySelector('.context-floating-menu');
    if (!menu) return 'no_menu';

    // '삽입' 텍스트 찾기
    const elements = menu.querySelectorAll('*');
    for (const el of elements) {
        if (el.textContent && el.textContent.trim() === '삽입') {
            el.click();
            return 'ok';
        }
    }

    // 클래스로 찾기
    const btn = menu.querySelector('.c-iAoqJH');
    if (btn) {
        btn.click();
        return 'ok';
    }

    return 'not_found';
})();
'''

JS_GET_PC_LOAD_POSITION = '''
(function() {
    // "PC에서 불러오기" 텍스트를 포함한 요소 찾기
    const allDivs = document.querySelectorAll('div');
    let btn = null;
    for (const div of allDivs) {
        if (div.textContent.trim() === 'PC에서 불러오기') {
            btn = div.closest('.c-geHaPZ') || div;
            break;
        }
    }

    if (btn && btn.offsetParent !== null) {
        const rect = btn.getBoundingClientRect();
        // 뷰포트 좌표 + 브라우저 창 위치 + 브라우저 크롬(툴바) 높이
        const chromeHeight = window.outerHeight - window.innerHeight;
        const x = Math.round(window.screenX + rect.left + rect.width / 2);
        const y = Math.round(window.screenY + chromeHeight + rect.top + rect.height / 2);
        return x + ',' + y;
    }

    return 'not_found';
})();
'''

JS_GET_ASSET_IMAGE_POSITION = '''
(function() {
    // 현재 선택된 클립(current)의 asset 이미지 찾기
    const currentClip = document.querySelector('.caption-wrapper.current');
    if (!currentClip) return 'no_current_clip';

    // current 클립의 부모에서 asset 이미지 찾기
    const parent = currentClip.closest('.c-byzcXA');
    if (!parent) return 'no_parent';

    const img = parent.querySelector('.asset-wrapper img');
    if (img && img.offsetParent !== null) {
        const rect = img.getBoundingClientRect();
        const chromeHeight = window.outerHeight - window.innerHeight;
        const x = Math.round(window.screenX + rect.left + rect.width / 2);
        const y = Math.round(window.screenY + chromeHeight + rect.top + rect.height / 2);
        return x + ',' + y;
    }
    return 'not_found';
})();
'''

JS_GET_FILL_MENU_POSITION = '''
(function() {
    // "채우기" 메뉴 찾기
    const allDivs = document.querySelectorAll('.c-cYUTvc');
    for (const div of allDivs) {
        if (div.textContent.trim() === '채우기') {
            const rect = div.getBoundingClientRect();
            const chromeHeight = window.outerHeight - window.innerHeight;
            const x = Math.round(window.screenX + rect.left + rect.width / 2);
            const y = Math.round(window.screenY + chromeHeight + rect.top + rect.height / 2);
            return x + ',' + y;
        }
    }
    return 'not_found';
})();
'''

JS_GET_CROP_FILL_POSITION = '''
(function() {
    // "잘라서 채우기" 메뉴 찾기
    const allDivs = document.querySelectorAll('.c-cYUTvc');
    for (const div of allDivs) {
        if (div.textContent.trim() === '잘라서 채우기') {
            const rect = div.getBoundingClientRect();
            const chromeHeight = window.outerHeight - window.innerHeight;
            const x = Math.round(window.screenX + rect.left + rect.width / 2);
            const y = Math.round(window.screenY + chromeHeight + rect.top + rect.height / 2);
            return x + ',' + y;
        }
    }
    return 'not_found';
})();
'''

JS_GET_FILL_BUTTON_POSITION = '''
(function() {
    // "채우기" 버튼 찾기 (c-jKTWEU 클래스)
    const allDivs = document.querySelectorAll('.c-jKTWEU');
    for (const div of allDivs) {
        if (div.textContent.trim() === '채우기') {
            const rect = div.getBoundingClientRect();
            const chromeHeight = window.outerHeight - window.innerHeight;
            const x = Math.round(window.screenX + rect.left + rect.width / 2);
            const y = Math.round(window.screenY + chromeHeight + rect.top + rect.height / 2);
            return x + ',' + y;
        }
    }
    return 'not_found';
})();
'''

JS_GET_ANIMATION_POSITION = '''
(function() {
    // "애니메이션" 메뉴 찾기
    const allDivs = document.querySelectorAll('.c-cYUTvc');
    for (const div of allDivs) {
        if (div.textContent.trim() === '애니메이션') {
            const rect = div.getBoundingClientRect();
            const chromeHeight = window.outerHeight - window.innerHeight;
            const x = Math.round(window.screenX + rect.left + rect.width / 2);
            const y = Math.round(window.screenY + chromeHeight + rect.top + rect.height / 2);
            return x + ',' + y;
        }
    }
    return 'not_found';
})();
'''

JS_GET_ZOOM_POSITION = '''
(function() {
    // "확대" 탭 찾기
    const allDivs = document.querySelectorAll('.c-hqIxFZ');
    for (const div of allDivs) {
        if (div.textContent.trim() === '확대') {
            const rect = div.getBoundingClientRect();
            const chromeHeight = window.outerHeight - window.innerHeight;
            const x = Math.round(window.screenX + rect.left + rect.width / 2);
            const y = Math.round(window.screenY + chromeHeight + rect.top + rect.height / 2);
            return x + ',' + y;
        }
    }
    return 'not_found';
})();
'''

JS_GET_MOVE_OR_PUSH_POSITION = '''
(function(choice) {
    // "움직이기" 또는 "밀어내기" 찾기
    const target = choice === 0 ? '움직이기' : '밀어내기';
    const allDivs = document.querySelectorAll('.c-ejwjsy');
    for (const div of allDivs) {
        if (div.textContent.trim() === target) {
            const rect = div.getBoundingClientRect();
            const chromeHeight = window.outerHeight - window.innerHeight;
            const x = Math.round(window.screenX + rect.left + rect.width / 2);
            const y = Math.round(window.screenY + chromeHeight + rect.top + rect.height / 2);
            return x + ',' + y;
        }
    }
    return 'not_found';
})(%s);
'''

JS_GET_DIRECTION_POSITION = '''
(function(index) {
    // 방향 버튼 찾기
    const buttons = document.querySelectorAll('.c-cYWwBE');
    if (buttons.length > index) {
        const btn = buttons[index];
        const rect = btn.getBoundingClientRect();
        const chromeHeight = window.outerHeight - window.innerHeight;
        const x = Math.round(window.screenX + rect.left + rect.width / 2);
        const y = Math.round(window.screenY + chromeHeight + rect.top + rect.height / 2);
        return x + ',' + y;
    }
    return 'not_found';
})(%s);
'''

JS_GET_APPLY_RANGE_POSITION = '''
(function() {
    // "적용 범위 변경" 메뉴 찾기
    const allDivs = document.querySelectorAll('.c-cYUTvc');
    for (const div of allDivs) {
        if (div.textContent.includes('적용 범위 변경')) {
            const rect = div.getBoundingClientRect();
            const chromeHeight = window.outerHeight - window.innerHeight;
            const x = Math.round(window.screenX + rect.left + rect.width / 2);
            const y = Math.round(window.screenY + chromeHeight + rect.top + rect.height / 2);
            return x + ',' + y;
        }
    }
    return 'not_found';
})();
'''

JS_GET_FROM_CURRENT_TO_END_POSITION = '''
(function() {
    // "현재 클립부터 끝까지" 메뉴 찾기
    const allDivs = document.querySelectorAll('.c-cYUTvc');
    for (const div of allDivs) {
        if (div.textContent.trim() === '현재 클립부터 끝까지') {
            const rect = div.getBoundingClientRect();
            const chromeHeight = window.outerHeight - window.innerHeight;
            const x = Math.round(window.screenX + rect.left + rect.width / 2);
            const y = Math.round(window.screenY + chromeHeight + rect.top + rect.height / 2);
            return x + ',' + y;
        }
    }
    return 'not_found';
})();
'''


def select_file_dialog(filepath):
    """macOS 파일 대화상자에서 파일 선택"""
    time.sleep(LONG_WAIT)

    # Cmd+Shift+G로 경로 입력 창 열기
    pyautogui.hotkey('command', 'shift', 'g')
    time.sleep(MEDIUM_WAIT)

    # 경로 입력
    pyperclip.copy(filepath)
    pyautogui.hotkey('command', 'v')
    time.sleep(SHORT_WAIT)

    # 이동
    pyautogui.press('enter')
    time.sleep(MEDIUM_WAIT)

    # 열기
    pyautogui.press('enter')
    time.sleep(LONG_WAIT)


def process_single_image(filepath, browser='chrome'):
    """단일 이미지 처리. 반환: (성공여부, 실패사유)"""
    search_name = get_search_name(filepath)
    print(f"\n  처리 중: {search_name}")

    # 0. 크롬 활성화 및 검색 패널 열기 (Cmd+F)
    subprocess.run(['osascript', '-e', 'tell application "Google Chrome" to activate'], capture_output=True)
    time.sleep(MEDIUM_WAIT)
    # ESC 눌러서 기존 메뉴/팝업 닫기
    pyautogui.press('escape')
    time.sleep(SHORT_WAIT)
    pyautogui.hotkey('command', 'f')
    time.sleep(MEDIUM_WAIT)

    # 1. 검색어 입력 및 결과 찾기 (없으면 한 글자씩 줄여서 재시도)
    current_search = search_name
    search_found = False

    while len(current_search) > 0:
        result = run_js(JS_SEARCH_TEXT % current_search, browser)
        if result == 'not_found':
            # 검색창이 없으면 다시 Cmd+F
            pyautogui.hotkey('command', 'f')
            time.sleep(MEDIUM_WAIT)
            result = run_js(JS_SEARCH_TEXT % current_search, browser)
            if result == 'not_found':
                print("    검색 입력창을 찾을 수 없습니다.")
                return (False, "검색 입력창 없음")

        time.sleep(LONG_WAIT)  # 검색 결과 로드 대기

        # 검색 결과 확인
        count_result = run_js(JS_GET_SEARCH_RESULT_COUNT, browser)
        try:
            result_count = int(count_result) if count_result else 0
        except:
            result_count = 0

        if result_count > 0:
            search_found = True
            print(f"    검색어 '{current_search}'로 {result_count}개 결과 발견")
            break

        # 결과 없으면 한 글자 줄여서 재시도
        current_search = current_search[:-1]
        if current_search:
            print(f"    검색 결과 없음. '{current_search}'로 재시도...")

    if not search_found:
        print("    검색 결과가 없습니다. 스킵합니다.")
        return (False, "검색 결과 없음")

    # 2. 검색 결과 클릭 (여러 개면 이름 일치하는 것 클릭)
    result = run_js(JS_CLICK_MATCHING_RESULT % search_name, browser)
    if not result or not result.startswith('ok'):
        if result and result.startswith('no_match'):
            print(f"    검색 결과 중 '{search_name}'와 일치하는 항목 없음. 스킵합니다.")
            # 디버그 정보 출력
            if '|' in result:
                parts = result.split('|')
                for part in parts[1:]:
                    print(f"    [DEBUG] {part}")
            return (False, "일치하는 검색 결과 없음")
        print("    검색 결과 클릭 실패. 다음 이미지로 넘어갑니다.")
        return (False, "검색 결과 클릭 실패")
    print(f"    검색 결과 클릭: {result}")
    time.sleep(MEDIUM_WAIT)

    # 3. 행 번호 클릭 (플로팅 메뉴 표시)
    result = run_js(JS_CLICK_ROW_NUMBER, browser)
    time.sleep(MEDIUM_WAIT)

    # 4. 삽입 버튼 클릭
    result = run_js(JS_CLICK_INSERT_BUTTON, browser)
    if result == 'no_menu':
        print("    플로팅 메뉴가 없습니다. 행 번호를 다시 클릭합니다.")
        run_js(JS_CLICK_ROW_NUMBER, browser)
        time.sleep(MEDIUM_WAIT)
        result = run_js(JS_CLICK_INSERT_BUTTON, browser)

    if result == 'not_found':
        print("    삽입 버튼을 찾을 수 없습니다.")
        return (False, "삽입 버튼 없음")
    time.sleep(SHORT_WAIT)

    # 5. PC에서 불러오기 클릭 (동적 좌표 + pyautogui)
    result = run_js(JS_GET_PC_LOAD_POSITION, browser)
    if result == 'not_found' or not result or ',' not in str(result):
        print("    PC에서 불러오기 버튼을 찾을 수 없습니다.")
        return (False, "PC에서 불러오기 버튼 없음")

    x, y = map(int, result.split(','))
    pyautogui.click(x, y)

    # 6. 파일 선택 대화상자 (pyautogui)
    select_file_dialog(filepath)

    # 7. 이미지 첨부 확인 및 클릭
    time.sleep(MEDIUM_WAIT)
    result = run_js(JS_GET_ASSET_IMAGE_POSITION, browser)
    if result == 'not_found' or not result or ',' not in str(result):
        print("    이미지가 첨부되지 않았습니다.")
        return (False, "이미지 첨부 실패")

    x, y = map(int, result.split(','))
    pyautogui.click(x, y)
    time.sleep(SHORT_WAIT)

    # 8. 채우기 클릭
    result = run_js(JS_GET_FILL_MENU_POSITION, browser)
    if result == 'not_found' or not result or ',' not in str(result):
        print("    채우기 메뉴를 찾을 수 없습니다.")
        return (False, "채우기 메뉴 없음")

    x, y = map(int, result.split(','))
    pyautogui.click(x, y)
    time.sleep(SHORT_WAIT)

    # 9. 잘라서 채우기 클릭
    result = run_js(JS_GET_CROP_FILL_POSITION, browser)
    if result == 'not_found' or not result or ',' not in str(result):
        print("    잘라서 채우기 메뉴를 찾을 수 없습니다.")
        return (False, "잘라서 채우기 메뉴 없음")

    x, y = map(int, result.split(','))
    pyautogui.click(x, y)
    time.sleep(SHORT_WAIT)

    # 10. 채우기 버튼 클릭
    result = run_js(JS_GET_FILL_BUTTON_POSITION, browser)
    if result == 'not_found' or not result or ',' not in str(result):
        print("    채우기 버튼을 찾을 수 없습니다.")
        return (False, "채우기 버튼 없음")

    x, y = map(int, result.split(','))
    pyautogui.click(x, y)
    time.sleep(SHORT_WAIT)

    # 11. 애니메이션 클릭
    result = run_js(JS_GET_ANIMATION_POSITION, browser)
    if result == 'not_found' or not result or ',' not in str(result):
        print("    애니메이션 메뉴를 찾을 수 없습니다.")
        return (False, "애니메이션 메뉴 없음")

    x, y = map(int, result.split(','))
    pyautogui.click(x, y)
    time.sleep(SHORT_WAIT)

    # 12. 확대 탭 클릭
    result = run_js(JS_GET_ZOOM_POSITION, browser)
    if result == 'not_found' or not result or ',' not in str(result):
        print("    확대 탭을 찾을 수 없습니다.")
        return (False, "확대 탭 없음")

    x, y = map(int, result.split(','))
    pyautogui.click(x, y)
    time.sleep(SHORT_WAIT)

    # 13. 움직이기/밀어내기 랜덤 클릭
    move_choice = random.randint(0, 1)
    result = run_js(JS_GET_MOVE_OR_PUSH_POSITION % move_choice, browser)
    if result == 'not_found' or not result or ',' not in str(result):
        print("    움직이기/밀어내기를 찾을 수 없습니다.")
        return (False, "움직이기/밀어내기 없음")

    x, y = map(int, result.split(','))
    pyautogui.click(x, y)
    time.sleep(SHORT_WAIT)

    # 14. 방향 버튼 랜덤 클릭
    direction_choice = random.randint(0, 1)
    result = run_js(JS_GET_DIRECTION_POSITION % direction_choice, browser)
    if result == 'not_found' or not result or ',' not in str(result):
        print("    방향 버튼을 찾을 수 없습니다.")
        return (False, "방향 버튼 없음")

    x, y = map(int, result.split(','))
    pyautogui.click(x, y)
    time.sleep(SHORT_WAIT)

    # 15. 적용 범위 변경 클릭
    result = run_js(JS_GET_APPLY_RANGE_POSITION, browser)
    if result == 'not_found' or not result or ',' not in str(result):
        print("    적용 범위 변경 메뉴를 찾을 수 없습니다.")
        return (False, "적용 범위 변경 메뉴 없음")

    x, y = map(int, result.split(','))
    pyautogui.click(x, y)
    time.sleep(SHORT_WAIT)

    # 16. 현재 클립부터 끝까지 클릭
    result = run_js(JS_GET_FROM_CURRENT_TO_END_POSITION, browser)
    if result == 'not_found' or not result or ',' not in str(result):
        print("    현재 클립부터 끝까지 메뉴를 찾을 수 없습니다.")
        return (False, "현재 클립부터 끝까지 메뉴 없음")

    x, y = map(int, result.split(','))
    pyautogui.click(x, y)
    time.sleep(SHORT_WAIT)

    print(f"  완료: {search_name}")
    return (True, None)


def run_automation(browser='chrome'):
    """자동화 실행"""
    image_files = get_image_files()

    if not image_files:
        print(f"오류: {IMAGE_FOLDER}에서 이미지 파일을 찾을 수 없습니다.")
        return

    print(f"\n발견된 이미지 파일 ({len(image_files)}개):")
    for f in image_files:
        print(f"  - {os.path.basename(f)}")

    print("\n3초 후 시작합니다. 브라우저 창을 활성화하세요!")
    for i in range(3, 0, -1):
        print(f"  {i}...")
        time.sleep(1)

    print("\n스크립트 시작!")

    # 검색 패널 열기
    print("검색 패널 열기...")
    run_js(JS_OPEN_SEARCH, browser)
    time.sleep(MEDIUM_WAIT)

    success_count = 0
    fail_count = 0
    failed_images = []

    for i, filepath in enumerate(image_files, 1):
        print(f"\n[{i}/{len(image_files)}]", end="")
        try:
            success, reason = process_single_image(filepath, browser)
            if success:
                success_count += 1
                # 성공한 이미지를 success 폴더로 이동
                try:
                    move_to_success(filepath)
                except Exception as e:
                    print(f"    파일 이동 실패: {e}")
            else:
                fail_count += 1
                failed_images.append((get_search_name(filepath), reason))
        except pyautogui.FailSafeException:
            print("\n\n사용자에 의해 중지됨 (FailSafe)")
            break
        except Exception as e:
            print(f"  오류 발생: {e}")
            fail_count += 1
            failed_images.append((get_search_name(filepath), str(e)))
            continue

        time.sleep(MEDIUM_WAIT)

    print("\n" + "=" * 60)
    print(f"완료! 성공: {success_count}, 실패: {fail_count}")

    if failed_images:
        print("\n실패한 이미지:")
        for name, reason in failed_images:
            print(f"  - {name}: {reason}")

    print("=" * 60)

    # 실패가 없으면 vrew_image_order.py 실행
    if fail_count == 0 and success_count > 0:
        print("\n모든 이미지 처리 성공! vrew_image_order.py 실행합니다...")
        order_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vrew_image_order.py")
        if os.path.exists(order_script):
            subprocess.run(['python3', order_script])
        else:
            print(f"  오류: {order_script} 파일을 찾을 수 없습니다.")


def main():
    print("=" * 60)
    print("  Vrew 이미지 자동 삽입 스크립트")
    print("=" * 60)
    run_automation('chrome')


if __name__ == "__main__":
    main()
