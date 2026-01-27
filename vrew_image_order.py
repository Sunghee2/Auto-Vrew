#!/usr/bin/env python3
"""
Vrew 이미지 순서 자동화 스크립트
- AppleScript를 통해 기존 Chrome에서 JavaScript 실행
"""

import subprocess
import time
import json


def run_js_in_chrome(js_code):
    """AppleScript를 통해 Chrome에서 JavaScript 실행"""
    # JavaScript 코드를 이스케이프
    escaped_js = js_code.replace('\\', '\\\\').replace('"', '\\"')

    applescript = f'''
    tell application "Google Chrome"
        execute front window's active tab javascript "{escaped_js}"
    end tell
    '''

    result = subprocess.run(
        ['osascript', '-e', applescript],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"오류: {result.stderr}")
        return None

    return result.stdout.strip()


def scroll_to_top():
    """스크롤을 맨 위로"""
    js = '''
    (function() {
        var container = document.querySelector('.transcript');
        if (container) {
            container.scrollTop = 0;
            return 'scrolled';
        }
        window.scrollTo(0, 0);
        return 'window';
    })()
    '''
    result = run_js_in_chrome(js)
    print(f"스크롤을 맨 위로 이동했습니다. ({result})")


def get_image_count():
    """클립 이미지 개수 확인"""
    js = '''
    document.querySelectorAll('img.PJLV.PJLV-iPJLV-css.c-kzWEgz.c-kzWEgz-dUYFHp-rangeType-clip').length
    '''
    result = run_js_in_chrome(js)
    try:
        return int(result) if result else 0
    except:
        return 0


def get_image_ids():
    """모든 이미지의 asset-id 목록 반환"""
    js = '''
    JSON.stringify(
        Array.from(document.querySelectorAll('img.PJLV.PJLV-iPJLV-css.c-kzWEgz.c-kzWEgz-dUYFHp-rangeType-clip'))
        .map(img => img.getAttribute('data-asset-id'))
        .filter(id => id)
    )
    '''
    result = run_js_in_chrome(js)
    try:
        return json.loads(result) if result else []
    except:
        return []


def click_image_by_id(asset_id):
    """특정 asset-id를 가진 이미지 클릭"""
    js = f'''
    (function() {{
        var img = document.querySelector('img[data-asset-id="{asset_id}"]');
        if (img) {{
            img.scrollIntoView({{block: 'center'}});
            img.click();
            return 'clicked';
        }}
        return 'not_found';
    }})()
    '''
    result = run_js_in_chrome(js)
    return result == 'clicked'


def click_order_menu():
    """순서 메뉴 클릭"""
    js = '''
    (function() {
        var items = document.querySelectorAll('div.c-cYUTvc');
        for (var i = 0; i < items.length; i++) {
            if (items[i].textContent.trim() === '순서') {
                items[i].click();
                return 'clicked';
            }
        }
        return 'not_found';
    })()
    '''
    result = run_js_in_chrome(js)
    return result == 'clicked'


def click_bring_to_front():
    """맨 앞으로 가져오기 클릭"""
    js = '''
    (function() {
        var items = document.querySelectorAll('.react-contextmenu-item');
        for (var i = 0; i < items.length; i++) {
            if (items[i].textContent.includes('맨 앞으로 가져오기')) {
                items[i].click();
                return 'clicked';
            }
        }
        // fallback
        var divs = document.querySelectorAll('div');
        for (var i = 0; i < divs.length; i++) {
            if (divs[i].textContent.trim() === '맨 앞으로 가져오기') {
                divs[i].click();
                return 'clicked_div';
            }
        }
        return 'not_found';
    })()
    '''
    result = run_js_in_chrome(js)
    return 'clicked' in str(result)


def close_menu():
    """메뉴 닫기 - ESC 키 또는 다른 곳 클릭"""
    js = '''
    document.body.click();
    '''
    run_js_in_chrome(js)


def scroll_down(amount=300):
    """페이지 스크롤 다운"""
    js = f'''
    (function() {{
        var container = document.querySelector('.transcript');
        if (container) {{
            container.scrollTop += {amount};
            return 'scrolled';
        }}
        window.scrollBy(0, {amount});
        return 'window';
    }})()
    '''
    run_js_in_chrome(js)


def get_scroll_info():
    """스크롤 정보 반환"""
    js = '''
    (function() {
        var container = document.querySelector('.transcript');
        if (container) {
            return JSON.stringify({
                current: container.scrollTop,
                max: container.scrollHeight - container.clientHeight
            });
        }
        return JSON.stringify({
            current: window.pageYOffset,
            max: document.documentElement.scrollHeight - window.innerHeight
        });
    })()
    '''
    result = run_js_in_chrome(js)
    try:
        return json.loads(result)
    except:
        return {'current': 0, 'max': 0}


def process_image(asset_id):
    """이미지 클릭 후 순서 > 맨 앞으로 가져오기 실행"""
    # 이미지 클릭
    if not click_image_by_id(asset_id):
        print("  - 이미지를 찾을 수 없음")
        return False

    print("  - 이미지 클릭")
    time.sleep(0.5)

    # 순서 메뉴 클릭
    if not click_order_menu():
        print("  - '순서' 메뉴를 찾을 수 없음")
        close_menu()
        return False

    print("  - '순서' 메뉴 클릭")
    time.sleep(0.3)

    # 맨 앞으로 가져오기 클릭
    if not click_bring_to_front():
        print("  - '맨 앞으로 가져오기'를 찾을 수 없음")
        close_menu()
        return False

    print("  - '맨 앞으로 가져오기' 클릭")
    time.sleep(0.3)

    close_menu()
    return True


def main():
    print("Vrew 이미지 순서 자동화 시작")
    print("=" * 50)

    # 스크롤을 맨 위로
    scroll_to_top()
    time.sleep(0.5)

    processed_count = 0
    processed_ids = set()

    while True:
        # 현재 보이는 이미지들의 ID 가져오기
        image_ids = get_image_ids()

        if not image_ids:
            print("처리할 이미지가 없습니다.")
            scroll_info = get_scroll_info()

            if scroll_info['current'] >= scroll_info['max'] - 10:
                print("페이지 끝에 도달했습니다.")
                break

            scroll_down()
            time.sleep(0.5)
            continue

        # 새로운 이미지만 처리
        found_new = False
        for asset_id in image_ids:
            if asset_id not in processed_ids:
                found_new = True
                processed_count += 1
                print(f"\n[{processed_count}] 이미지 처리 중 (ID: {asset_id[:8]}...)")

                if process_image(asset_id):
                    processed_ids.add(asset_id)
                else:
                    print("  - 건너뜀")
                    processed_ids.add(asset_id)  # 실패한 이미지도 추가해서 무한 반복 방지

                time.sleep(0.5)

        if not found_new:
            scroll_info = get_scroll_info()

            if scroll_info['current'] >= scroll_info['max'] - 10:
                print("\n페이지 끝에 도달했습니다.")
                break

            print("\n스크롤 다운...")
            scroll_down()
            time.sleep(0.5)

    print("\n" + "=" * 50)
    print(f"완료! 총 {processed_count}개 이미지 처리됨")


if __name__ == "__main__":
    main()
